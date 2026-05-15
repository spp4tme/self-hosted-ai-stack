"""Outil CrewAI — Requêtes Prometheus pour l'infrastructure."""

from __future__ import annotations

import os
from typing import Type

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

_PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")


class PrometheusQueryInput(BaseModel):
    query: str = Field(..., description="Requête PromQL")
    description: str = Field(default="", description="Description de ce qu'on cherche à mesurer")


class PrometheusQueryTool(BaseTool):
    name: str = "Prometheus Metrics Query"
    description: str = (
        "Interroge Prometheus pour obtenir des métriques de l'infrastructure. "
        "Utilise des requêtes PromQL. Exemples: "
        "'up' (services actifs), "
        "'container_memory_usage_bytes' (mémoire), "
        "'container_cpu_usage_seconds_total' (CPU)."
    )
    args_schema: Type[BaseModel] = PrometheusQueryInput

    def _run(self, query: str, description: str = "") -> str:
        try:
            resp = requests.get(
                f"{_PROMETHEUS_URL}/api/v1/query",
                params={"query": query},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "success":
                return f"Erreur Prometheus: {data.get('error', 'Inconnue')}"
            results = data.get("data", {}).get("result", [])
            if not results:
                return f"Aucune donnée pour: {query}"
            lines = [f"Résultats pour `{query}`" + (f" ({description})" if description else "") + ":"]
            for r in results[:20]:
                metric = r.get("metric", {})
                value = r.get("value", [None, "N/A"])[1]
                label = metric.get("job") or metric.get("container") or metric.get("instance") or str(metric)
                lines.append(f"  • {label}: {value}")
            return "\n".join(lines)
        except Exception as e:
            return f"Erreur Prometheus: {e}"


class PrometheusAlertsTool(BaseTool):
    name: str = "Prometheus Active Alerts"
    description: str = "Récupère les alertes actives dans Prometheus/Alertmanager."
    args_schema: Type[BaseModel] = BaseModel

    def _run(self) -> str:
        try:
            resp = requests.get(f"{_PROMETHEUS_URL}/api/v1/alerts", timeout=10)
            resp.raise_for_status()
            alerts = resp.json().get("data", {}).get("alerts", [])
            if not alerts:
                return "✅ Aucune alerte active."
            lines = [f"⚠️ {len(alerts)} alerte(s) active(s) :"]
            for a in alerts:
                name = a.get("labels", {}).get("alertname", "?")
                severity = a.get("labels", {}).get("severity", "?")
                state = a.get("state", "?")
                lines.append(f"  • [{severity.upper()}] {name} — état: {state}")
            return "\n".join(lines)
        except Exception as e:
            return f"Erreur alertes: {e}"
