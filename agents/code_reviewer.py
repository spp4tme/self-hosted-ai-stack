"""Review de code automatique via qwen2.5-coder + GitHub API."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
from typing import Any

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from github import Github
from pydantic import BaseModel

load_dotenv()

_LITELLM_URL      = os.getenv("LITELLM_URL",     "http://localhost:4000")
_LITELLM_KEY      = os.getenv("LITELLM_API_KEY",  "sk-local")
_GITHUB_TOKEN     = os.getenv("GITHUB_TOKEN",     "")
_GITHUB_REPO      = os.getenv("GITHUB_REPO",      "")
_WEBHOOK_SECRET   = os.getenv("GITHUB_WEBHOOK_SECRET", "")
_CODE_MODEL       = "qwen2.5-coder:7b"

REVIEW_SYSTEM = """Tu es un expert code reviewer senior. Analyse le diff et fournis une review structurée.

Pour chaque problème identifié, utilise ce format :
[CRITIQUE] Description — ligne XX : explication
[SÉCURITÉ] Description — ligne XX : explication
[PERFORMANCE] Description — ligne XX : explication
[STYLE] Description — ligne XX : explication

À la fin, donne un verdict : APPROVE | REQUEST_CHANGES | COMMENT
et un score de 0 à 10."""


async def _review_diff(diff: str, filename: str) -> str:
    prompt = f"Fichier : {filename}\n\nDiff :\n```diff\n{diff[:6000]}\n```\n\nFournis une review complète."
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{_LITELLM_URL}/chat/completions",
            json={
                "model": _CODE_MODEL,
                "messages": [
                    {"role": "system", "content": REVIEW_SYSTEM},
                    {"role": "user",   "content": prompt},
                ],
                "temperature": 0.1,
                "stream": False,
            },
            headers={"Authorization": f"Bearer {_LITELLM_KEY}"},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


def _extract_verdict(review_text: str) -> str:
    for verdict in ("APPROVE", "REQUEST_CHANGES", "COMMENT"):
        if verdict in review_text.upper():
            return verdict
    return "COMMENT"


class CodeReviewer:
    def __init__(self) -> None:
        self._gh = Github(_GITHUB_TOKEN) if _GITHUB_TOKEN else None

    async def review_file(self, diff: str, filename: str) -> dict[str, str]:
        review = await _review_diff(diff, filename)
        return {
            "filename": filename,
            "review":   review,
            "verdict":  _extract_verdict(review),
        }

    async def review_pr(self, pr_number: int, repo_name: str | None = None) -> list[dict[str, str]]:
        """Review complète d'une PR GitHub."""
        if not self._gh:
            raise RuntimeError("GITHUB_TOKEN non configuré")
        repo    = self._gh.get_repo(repo_name or _GITHUB_REPO)
        pr      = repo.get_pull(pr_number)
        files   = list(pr.get_files())
        results = []

        for f in files:
            if not f.filename.endswith((".py", ".js", ".ts", ".go", ".rs", ".java")):
                continue
            if not f.patch:
                continue
            review = await self.review_file(f.patch, f.filename)
            results.append(review)

            # Post sur la PR
            if _GITHUB_TOKEN and review["verdict"] in ("REQUEST_CHANGES", "COMMENT"):
                pr.create_review(
                    body=f"### Review automatique — {f.filename}\n\n{review['review']}",
                    event=review["verdict"],
                )

        return results

    async def review_local_file(self, file_path: str) -> dict[str, str]:
        """Review d'un fichier local (sans GitHub)."""
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
        # Simule un diff entier
        diff = "\n".join(f"+ {line}" for line in content.splitlines())
        return await self.review_file(diff, file_path)


# ── FastAPI webhook ───────────────────────────────────────────────────────────

app    = FastAPI(title="Jarvis Code Reviewer", version="1.0")
_reviewer = CodeReviewer()


def _verify_signature(body: bytes, sig_header: str) -> bool:
    if not _WEBHOOK_SECRET:
        return True
    expected = "sha256=" + hmac.new(
        _WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, sig_header)


class LocalReviewRequest(BaseModel):
    file_path: str


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "github": bool(_GITHUB_TOKEN)}


@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    x_github_event:    str = Header(default=""),
    x_hub_signature_256: str = Header(default=""),
) -> dict[str, Any]:
    body = await request.body()
    if not _verify_signature(body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Signature invalide")

    if x_github_event != "pull_request":
        return {"status": "ignored", "event": x_github_event}

    payload   = await request.json()
    action    = payload.get("action", "")
    pr_number = payload["pull_request"]["number"]
    repo_name = payload["repository"]["full_name"]

    if action not in ("opened", "synchronize"):
        return {"status": "ignored", "action": action}

    results = await _reviewer.review_pr(pr_number, repo_name)
    return {"status": "reviewed", "pr": pr_number, "files_reviewed": len(results)}


@app.post("/review/local")
async def review_local(req: LocalReviewRequest) -> dict[str, Any]:
    result = await _reviewer.review_local_file(req.file_path)
    return result


@app.post("/review/pr/{pr_number}")
async def review_pr(pr_number: int) -> list[dict[str, str]]:
    return await _reviewer.review_pr(pr_number)


if __name__ == "__main__":
    port = int(os.getenv("REVIEWER_WEBHOOK_PORT", "8102"))
    uvicorn.run(app, host="0.0.0.0", port=port)
