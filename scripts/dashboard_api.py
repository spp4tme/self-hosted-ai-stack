#!/usr/bin/env python3
"""
Dashboard Metrics API — port 9200
Expose GPU/CPU/RAM + proxy Ollama pour le Jarvis Command Center.
Lance avec : python scripts/dashboard_api.py
"""
import http.server
import json
import subprocess
import urllib.request
from urllib.parse import urlparse

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def gpu_metrics() -> dict:
    try:
        r = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3,
        )
        parts = [x.strip() for x in r.stdout.strip().split(",")]
        return {
            "vram_used_mb":  int(parts[0]),
            "vram_total_mb": int(parts[1]),
            "gpu_util":      int(parts[2]),
            "gpu_temp":      int(parts[3]),
        }
    except Exception:
        return {"vram_used_mb": 0, "vram_total_mb": 16384, "gpu_util": 0, "gpu_temp": 0}


def cpu_ram_metrics() -> dict:
    if HAS_PSUTIL:
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        return {
            "cpu_pct":      round(cpu, 1),
            "ram_used_gb":  round(ram.used / 1e9, 1),
            "ram_total_gb": round(ram.total / 1e9, 1),
            "ram_pct":      round(ram.percent, 1),
        }
    try:
        r = subprocess.run(
            ["wmic", "cpu", "get", "loadpercentage", "/format:value"],
            capture_output=True, text=True, timeout=3,
        )
        cpu = float(r.stdout.strip().split("=")[1])
    except Exception:
        cpu = 0.0
    return {"cpu_pct": cpu, "ram_used_gb": 0, "ram_total_gb": 64, "ram_pct": 0}


def proxy(url: str):
    try:
        with urllib.request.urlopen(url, timeout=4) as resp:
            return json.load(resp)
    except Exception:
        return None


class Handler(http.server.BaseHTTPRequestHandler):

    def _json(self, data: object, status: int = 200) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        for k, v in CORS.items():
            self.send_header(k, v)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        for k, v in CORS.items():
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path

        if path == "/api/metrics":
            self._json({**gpu_metrics(), **cpu_ram_metrics()})

        elif path == "/api/ollama/tags":
            data = proxy("http://localhost:11434/api/tags")
            self._json(data if data else {"models": []})

        elif path == "/api/ollama/ps":
            data = proxy("http://localhost:11434/api/ps")
            self._json(data if data else {"models": []})

        elif path == "/health":
            self._json({"status": "ok"})

        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):  # noqa: silence
        pass


if __name__ == "__main__":
    port = 9200
    server = http.server.HTTPServer(("localhost", port), Handler)
    print(f"Dashboard API → http://localhost:{port}")
    print("  /api/metrics      GPU + CPU + RAM (nvidia-smi + psutil)")
    print("  /api/ollama/tags  modèles Ollama (proxied)")
    print("  /api/ollama/ps    modèles actifs + VRAM (proxied)")
    print("  /health           keepalive")
    server.serve_forever()
