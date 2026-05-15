"""
Self-Healing Infrastructure — monitoring + auto-restart + métriques Prometheus.
Vérifie les services toutes les 30s, redémarre si nécessaire, expose /metrics :9099.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import aiohttp
import docker
import structlog
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
POLL_INTERVAL  = int(os.getenv("SELFHEAL_POLL_S",   "30"))
METRICS_PORT   = int(os.getenv("SELFHEAL_METRICS_PORT", "9099"))
LOG_PATH       = Path("devops/heal.log")
RESTART_WINDOW = 300   # 5 minutes
RESTART_MAX    = 3     # au-delà → stop auto-restart + alerte

SERVICES: list[dict[str, Any]] = [
    {"name": "ollama",    "url": "http://localhost:11434",     "container": None},
    {"name": "litellm",   "url": "http://localhost:4000/health","container": "litellm"},
    {"name": "qdrant",    "url": "http://localhost:6333/health","container": "qdrant"},
    {"name": "open-webui","url": "http://localhost:8080",      "container": "open-webui"},
    {"name": "searxng",   "url": "http://localhost:8888",      "container": "searxng"},
]

VRAM_ALERT_PCT   = 90
DISK_ALERT_PCT   = 80

# ── Logging structuré ─────────────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)
logger = structlog.get_logger()
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── Métriques (Prometheus text format) ────────────────────────────────────────
_metrics: dict[str, Any] = {}   # service → {up, restarts, last_check}
_restart_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=20))
_blocked_services: set[str] = set()


def _log(event: str, **kwargs: Any) -> None:
    entry = {"ts": datetime.utcnow().isoformat(), "event": event, **kwargs}
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    logger.info(event, **kwargs)


# ── Health checks ─────────────────────────────────────────────────────────────

async def check_service(name: str, url: str, timeout: float = 5.0) -> bool:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                return resp.status < 500
    except Exception:
        return False


async def get_vram_pct() -> float | None:
    """Lit la VRAM via nvidia-smi (si disponible)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "nvidia-smi",
            "--query-gpu=memory.used,memory.total",
            "--format=csv,noheader,nounits",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        out, _ = await proc.communicate()
        used_s, total_s = out.decode().strip().split(",")
        used, total = int(used_s.strip()), int(total_s.strip())
        return used / total * 100 if total > 0 else None
    except Exception:
        return None


async def get_disk_pct() -> float:
    """Usage disque de / (ou C: sur Windows)."""
    import shutil
    total, used, free = shutil.disk_usage("/")
    return used / total * 100


# ── Actions correctives ───────────────────────────────────────────────────────

def _docker_client() -> docker.DockerClient | None:
    try:
        return docker.from_env()
    except Exception:
        return None


async def restart_container(container_name: str) -> bool:
    client = _docker_client()
    if not client:
        return False
    try:
        container = client.containers.get(container_name)
        container.restart(timeout=30)
        _log("container_restarted", container=container_name)
        return True
    except Exception as e:
        _log("restart_failed", container=container_name, error=str(e))
        return False


async def unload_least_used_model() -> None:
    """Décharge les modèles Ollama chargés en VRAM."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:11434/api/ps") as resp:
                data = await resp.json()
        models = data.get("models", [])
        if models:
            # Sort by size_vram (croissant) — décharge le plus petit (le moins utilisé)
            model_to_unload = sorted(models, key=lambda m: m.get("size_vram", 0))[0]
            _log("unloading_model", model=model_to_unload.get("name"))
            async with aiohttp.ClientSession() as session:
                await session.delete(
                    "http://localhost:11434/api/chat",
                    json={"model": model_to_unload["name"], "keep_alive": 0},
                )
    except Exception as e:
        _log("unload_error", error=str(e))


async def docker_prune() -> None:
    client = _docker_client()
    if client:
        try:
            result = client.containers.prune()
            _log("docker_pruned", reclaimed=result.get("SpaceReclaimed", 0))
        except Exception as e:
            _log("prune_error", error=str(e))


# ── Boucle principale ─────────────────────────────────────────────────────────

async def monitor_loop() -> None:
    _log("selfheal_started", poll_interval=POLL_INTERVAL)

    while True:
        now = time.time()

        # ── Services ─────────────────────────────────────────────────────────
        for svc in SERVICES:
            name = svc["name"]
            up   = await check_service(name, svc["url"])
            _metrics[name] = {
                "up": int(up),
                "last_check": now,
                "restarts": len(_restart_history[name]),
            }

            if not up:
                _log("service_down", service=name)

                if name in _blocked_services:
                    _log("restart_blocked", service=name,
                         reason="trop de redémarrages")
                    continue

                # Auto-restart si conteneur Docker connu
                container = svc.get("container")
                if container:
                    # Compte les restarts récents
                    recent = [t for t in _restart_history[name]
                              if now - t < RESTART_WINDOW]
                    if len(recent) >= RESTART_MAX:
                        _log("restart_loop_detected", service=name, count=len(recent))
                        _blocked_services.add(name)
                        continue

                    _restart_history[name].append(now)
                    await restart_container(container)
            else:
                # Service up → on peut débloquer
                if name in _blocked_services:
                    _blocked_services.discard(name)
                    _log("service_recovered", service=name)

        # ── VRAM ─────────────────────────────────────────────────────────────
        vram_pct = await get_vram_pct()
        if vram_pct is not None:
            _metrics["vram_pct"] = vram_pct
            if vram_pct > VRAM_ALERT_PCT:
                _log("vram_high", pct=round(vram_pct, 1))
                await unload_least_used_model()

        # ── Disque ────────────────────────────────────────────────────────────
        disk_pct = await get_disk_pct()
        _metrics["disk_pct"] = disk_pct
        if disk_pct > DISK_ALERT_PCT:
            _log("disk_high", pct=round(disk_pct, 1))
            await docker_prune()

        await asyncio.sleep(POLL_INTERVAL)


# ── FastAPI métriques Prometheus ──────────────────────────────────────────────

app = FastAPI(title="Jarvis Self-Heal Metrics", version="1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> str:
    lines = [
        "# HELP jarvis_service_up Service health (1=up, 0=down)",
        "# TYPE jarvis_service_up gauge",
    ]
    for name, m in _metrics.items():
        if isinstance(m, dict) and "up" in m:
            lines.append(f'jarvis_service_up{{service="{name}"}} {m["up"]}')

    lines += [
        "",
        "# HELP jarvis_service_restarts Total restarts",
        "# TYPE jarvis_service_restarts counter",
    ]
    for name, m in _metrics.items():
        if isinstance(m, dict) and "restarts" in m:
            lines.append(f'jarvis_service_restarts{{service="{name}"}} {m["restarts"]}')

    if "vram_pct" in _metrics:
        lines += [
            "",
            "# HELP jarvis_vram_pct VRAM usage percent",
            "# TYPE jarvis_vram_pct gauge",
            f'jarvis_vram_pct {_metrics["vram_pct"]:.1f}',
        ]
    if "disk_pct" in _metrics:
        lines += [
            "",
            "# HELP jarvis_disk_pct Disk usage percent",
            "# TYPE jarvis_disk_pct gauge",
            f'jarvis_disk_pct {_metrics["disk_pct"]:.1f}',
        ]

    return "\n".join(lines)


@app.get("/status")
async def status() -> dict[str, Any]:
    return {
        "metrics": _metrics,
        "blocked": list(_blocked_services),
    }


@app.on_event("startup")
async def _start_all() -> None:
    asyncio.create_task(monitor_loop())


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=METRICS_PORT)
