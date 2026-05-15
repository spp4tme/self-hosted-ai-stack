"""API FastAPI :8101 — exécution de code sécurisée."""

from __future__ import annotations

import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from sandbox.executor import SandboxExecutor, ExecutionResult

load_dotenv()

app = FastAPI(title="Jarvis Sandbox API", version="1.0")
_executor = SandboxExecutor()


class ExecuteRequest(BaseModel):
    code:     str
    packages: list[str] = []
    timeout:  int = 30


class ExecuteResponse(BaseModel):
    success:    bool
    stdout:     str
    stderr:     str
    duration_s: float
    blocked:    list[str]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/execute", response_model=ExecuteResponse)
async def execute(req: ExecuteRequest) -> ExecuteResponse:
    if len(req.code) > 32_000:
        raise HTTPException(status_code=400, detail="Code trop long (max 32 000 chars)")
    try:
        result: ExecutionResult = _executor.execute(
            req.code, req.packages, req.timeout
        )
        return ExecuteResponse(**result.__dict__)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    port = int(os.getenv("SANDBOX_API_PORT", "8101"))
    uvicorn.run(app, host="0.0.0.0", port=port)
