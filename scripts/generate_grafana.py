"""Génère le dashboard Grafana JSON pour le stack IA."""
import json, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(BASE, "grafana", "provisioning", "dashboards", "jarvis.json")

DS = {"type": "prometheus", "uid": "prometheus"}

def ts_panel(pid, title, targets, unit, x, y, w=12, h=8):
    return {
        "id": pid, "type": "timeseries", "title": title,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "datasource": DS,
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "custom": {"lineWidth": 2, "fillOpacity": 8, "spanNulls": True},
                "color": {"mode": "palette-classic"},
            },
            "overrides": [],
        },
        "options": {
            "tooltip": {"mode": "multi", "sort": "desc"},
            "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
        },
        "targets": [
            {"datasource": DS, "expr": t["expr"],
             "legendFormat": t.get("leg", "{{name}}"), "refId": chr(65+i)}
            for i, t in enumerate(targets)
        ],
    }

def stat_panel(pid, title, expr, unit, x, y, w=6, h=4, color="blue"):
    return {
        "id": pid, "type": "stat", "title": title,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "datasource": DS,
        "fieldConfig": {
            "defaults": {
                "unit": unit, "decimals": 1,
                "color": {"mode": "fixed", "fixedColor": color},
                "thresholds": {"mode": "absolute",
                               "steps": [{"color": color, "value": None}]},
            },
            "overrides": [],
        },
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "orientation": "auto", "textMode": "auto",
            "colorMode": "background", "graphMode": "area",
        },
        "targets": [{"datasource": DS, "expr": expr,
                     "legendFormat": "", "refId": "A"}],
    }

def row_panel(pid, title, y):
    return {"id": pid, "type": "row", "title": title,
            "gridPos": {"x": 0, "y": y, "w": 24, "h": 1},
            "collapsed": False, "panels": []}

panels = []
y = 0

# ── Ligne stats ───────────────────────────────────────────────────────────────
panels.append(stat_panel(1, "Conteneurs actifs",
    'count(container_last_seen{name!="",name!~".*_.*_.*"} > 0)',
    "short", 0, y, 4, 4, "green"))

panels.append(stat_panel(2, "CPU total",
    'sum(rate(container_cpu_usage_seconds_total{name!=""}[2m])) * 100',
    "percent", 4, y, 4, 4, "orange"))

panels.append(stat_panel(3, "RAM totale (Docker)",
    'sum(container_memory_usage_bytes{name!=""}) / 1024 / 1024 / 1024',
    "decgbytes", 8, y, 4, 4, "purple"))

panels.append(stat_panel(4, "Requêtes LiteLLM (1h)",
    'increase(litellm_requests_metric_total[1h])',
    "short", 12, y, 4, 4, "blue"))

panels.append(stat_panel(5, "Tokens (1h)",
    'increase(litellm_total_tokens_metric_total[1h])',
    "short", 16, y, 4, 4, "teal"))

panels.append(stat_panel(6, "Erreurs LiteLLM (1h)",
    'increase(litellm_llm_api_failed_requests_metric_total[1h])',
    "short", 20, y, 4, 4, "red"))

y += 4

# ── Conteneurs ────────────────────────────────────────────────────────────────
panels.append(row_panel(10, "Conteneurs Docker", y)); y += 1

panels.append(ts_panel(11, "CPU par conteneur (%)",
    [{"expr": 'sum(rate(container_cpu_usage_seconds_total{name!="",image!=""}[2m])) by (name) * 100'}],
    "percent", 0, y, 12, 8))

panels.append(ts_panel(12, "Mémoire par conteneur (MB)",
    [{"expr": 'container_memory_usage_bytes{name!="",image!=""} / 1024 / 1024'}],
    "megabytes", 12, y, 12, 8))

y += 8

panels.append(ts_panel(13, "Réseau entrant (KB/s)",
    [{"expr": 'sum(rate(container_network_receive_bytes_total{name!=""}[2m])) by (name) / 1024',
      "leg": "{{name}} ↓"}],
    "KBs", 0, y, 12, 8))

panels.append(ts_panel(14, "Réseau sortant (KB/s)",
    [{"expr": 'sum(rate(container_network_transmit_bytes_total{name!=""}[2m])) by (name) / 1024',
      "leg": "{{name}} ↑"}],
    "KBs", 12, y, 12, 8))

y += 8

# ── LiteLLM ───────────────────────────────────────────────────────────────────
panels.append(row_panel(20, "LiteLLM — Requêtes", y)); y += 1

panels.append(ts_panel(21, "Requêtes / minute",
    [{"expr": 'rate(litellm_requests_metric_total[1m]) * 60', "leg": "req/min"}],
    "reqpm", 0, y, 12, 8))

panels.append(ts_panel(22, "Latence p50 / p95 / p99 (s)",
    [{"expr": 'histogram_quantile(0.50, rate(litellm_llm_api_latency_metric_bucket[5m]))', "leg": "p50"},
     {"expr": 'histogram_quantile(0.95, rate(litellm_llm_api_latency_metric_bucket[5m]))', "leg": "p95"},
     {"expr": 'histogram_quantile(0.99, rate(litellm_llm_api_latency_metric_bucket[5m]))', "leg": "p99"}],
    "s", 12, y, 12, 8))

y += 8

panels.append(ts_panel(23, "Tokens / minute (input + output)",
    [{"expr": 'rate(litellm_input_tokens_metric_total[1m]) * 60', "leg": "input"},
     {"expr": 'rate(litellm_output_tokens_metric_total[1m]) * 60', "leg": "output"}],
    "short", 0, y, 12, 8))

panels.append(ts_panel(24, "Erreurs par modèle",
    [{"expr": 'rate(litellm_llm_api_failed_requests_metric_total[5m]) * 60',
      "leg": "{{model}}"}],
    "short", 12, y, 12, 8))

y += 8

# ── Dashboard ─────────────────────────────────────────────────────────────────
dashboard = {
    "__inputs": [],
    "__requires": [],
    "annotations": {"list": []},
    "editable": True,
    "fiscalYearStartMonth": 0,
    "graphTooltip": 1,
    "id": None,
    "links": [],
    "panels": panels,
    "refresh": "30s",
    "schemaVersion": 39,
    "tags": ["jarvis", "mon-ia", "bts"],
    "templating": {"list": []},
    "time": {"from": "now-1h", "to": "now"},
    "timepicker": {},
    "timezone": "browser",
    "title": "Jarvis — Stack IA",
    "uid": "jarvis-stack-ia",
    "version": 1,
}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(dashboard, f, ensure_ascii=False, indent=2)

print(f"OK  {OUT}")
