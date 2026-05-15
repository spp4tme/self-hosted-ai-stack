"""GitOps Webhook — Docker Compose equivalent of ArgoCD.

Écoute les push GitHub → git pull → docker-compose up -d.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse

app = FastAPI(title="Jarvis GitOps Webhook", version="1.0")

REPO_PATH      = Path(os.getenv("REPO_PATH", "/repo"))
WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")
COMPOSE_FILE   = os.getenv("COMPOSE_FILE", "docker-compose.yaml")
BRANCH         = os.getenv("DEPLOY_BRANCH", "main")

deployments: list[dict[str, Any]] = []


def _verify_signature(payload: bytes, sig_header: str) -> bool:
    if not WEBHOOK_SECRET:
        return True
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, sig_header or "")


def _run_deploy(commit_sha: str, author: str) -> dict[str, Any]:
    start = time.time()
    record: dict[str, Any] = {
        "id": len(deployments) + 1,
        "commit": commit_sha[:8],
        "author": author,
        "started_at": datetime.utcnow().isoformat(),
        "status": "running",
        "logs": [],
    }
    deployments.append(record)

    commands = [
        ["git", "fetch", "--all"],
        ["git", "reset", "--hard", f"origin/{BRANCH}"],
        ["docker", "compose", "-f", COMPOSE_FILE, "up", "-d", "--build", "--remove-orphans"],
    ]

    for cmd in commands:
        try:
            result = subprocess.run(
                cmd,
                cwd=REPO_PATH,
                capture_output=True,
                text=True,
                timeout=600,
            )
            record["logs"].append({
                "cmd": " ".join(cmd),
                "rc": result.returncode,
                "stdout": result.stdout[-2000:],
                "stderr": result.stderr[-1000:],
            })
            if result.returncode != 0:
                record["status"] = "failed"
                record["duration_s"] = round(time.time() - start, 1)
                return record
        except subprocess.TimeoutExpired:
            record["logs"].append({"cmd": " ".join(cmd), "error": "timeout"})
            record["status"] = "timeout"
            record["duration_s"] = round(time.time() - start, 1)
            return record

    record["status"] = "success"
    record["duration_s"] = round(time.time() - start, 1)
    return record


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "repo": str(REPO_PATH),
        "branch": BRANCH,
        "total_deployments": len(deployments),
    }


@app.post("/webhook/github")
async def github_webhook(request: Request) -> dict:
    payload_bytes = await request.body()
    sig = request.headers.get("X-Hub-Signature-256", "")

    if not _verify_signature(payload_bytes, sig):
        raise HTTPException(status_code=401, detail="Signature invalide")

    event = request.headers.get("X-GitHub-Event", "")
    if event != "push":
        return {"message": f"Événement '{event}' ignoré (seul 'push' déclenche un déploiement)"}

    payload = json.loads(payload_bytes)
    ref = payload.get("ref", "")
    if not ref.endswith(f"/{BRANCH}"):
        return {"message": f"Branche '{ref}' ignorée (seule '{BRANCH}' est déployée)"}

    commit_sha = payload.get("after", "unknown")
    author = payload.get("pusher", {}).get("name", "unknown")

    # Lancement en background
    import asyncio
    asyncio.create_task(
        asyncio.to_thread(_run_deploy, commit_sha, author)
    )

    return {
        "message": "Déploiement lancé",
        "commit": commit_sha[:8],
        "author": author,
        "branch": BRANCH,
    }


@app.get("/deployments")
async def list_deployments() -> list[dict]:
    return list(reversed(deployments[-20:]))


@app.get("/deployments/{deploy_id}")
async def get_deployment(deploy_id: int) -> dict:
    for d in deployments:
        if d["id"] == deploy_id:
            return d
    raise HTTPException(status_code=404, detail="Déploiement introuvable")


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    recent = list(reversed(deployments[-10:]))
    rows = ""
    for d in recent:
        color = {"success": "#22c55e", "failed": "#ef4444", "running": "#f59e0b", "timeout": "#f97316"}.get(d["status"], "#94a3b8")
        rows += f"""
        <tr>
          <td>#{d['id']}</td>
          <td><code>{d['commit']}</code></td>
          <td>{d['author']}</td>
          <td>{d['started_at'][:19]}</td>
          <td style="color:{color};font-weight:bold">{d['status'].upper()}</td>
          <td>{d.get('duration_s','—')}s</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html><head><title>GitOps — Jarvis</title>
<style>
  body{{font-family:monospace;background:#0f172a;color:#e2e8f0;padding:2rem}}
  h1{{color:#38bdf8}}
  table{{width:100%;border-collapse:collapse;margin-top:1rem}}
  th,td{{padding:.5rem 1rem;border:1px solid #334155;text-align:left}}
  th{{background:#1e293b}}
  tr:hover{{background:#1e293b}}
  .badge{{padding:.2rem .5rem;border-radius:4px;font-size:.8rem}}
</style></head>
<body>
  <h1>🚀 Jarvis GitOps</h1>
  <p>Branche surveillée: <strong>{BRANCH}</strong> | Repo: <strong>{REPO_PATH}</strong></p>
  <p><a href="/docs" style="color:#38bdf8">→ API Docs</a></p>
  <h2>Déploiements récents</h2>
  <table>
    <tr><th>#</th><th>Commit</th><th>Auteur</th><th>Date</th><th>Statut</th><th>Durée</th></tr>
    {rows or '<tr><td colspan="6">Aucun déploiement</td></tr>'}
  </table>
</body></html>"""


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("GITOPS_PORT", "9100"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
