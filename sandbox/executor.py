"""Exécution de code Python isolée dans Docker (réseau coupé, mémoire limitée)."""

from __future__ import annotations

import ast
import re
import subprocess
import textwrap
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import docker

DANGEROUS_IMPORTS = {
    "subprocess", "os", "sys", "shutil", "socket", "ctypes",
    "multiprocessing", "threading", "signal", "pty", "fcntl",
    "importlib", "__builtins__", "eval", "exec", "compile",
    "open",  # contrôlé par --read-only + tmpfs
}

SANDBOX_IMAGE   = "python:3.12-slim"
TIMEOUT_SEC     = 30
MEMORY_LIMIT    = "512m"
CPU_LIMIT       = 1.0
TMPFS_PATH      = "/tmp"
WORK_DIR        = Path("sandbox/tmp")


@dataclass
class ExecutionResult:
    success:    bool
    stdout:     str
    stderr:     str
    duration_s: float
    blocked:    list[str]    # imports dangereux détectés


def check_dangerous_imports(code: str) -> list[str]:
    """Détecte les imports dangereux avant exécution."""
    found: list[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in DANGEROUS_IMPORTS:
                    found.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                if root in DANGEROUS_IMPORTS:
                    found.append(node.module)
    return found


def _detect_packages(code: str) -> list[str]:
    """Détecte les packages tiers nécessaires (pas stdlib)."""
    stdlib = {
        "math", "random", "json", "re", "time", "datetime", "collections",
        "itertools", "functools", "pathlib", "typing", "dataclasses",
        "abc", "copy", "io", "string", "struct", "base64", "hashlib",
    }
    packages: set[str] = set()
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in stdlib:
                    packages.add(root)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                if root not in stdlib:
                    packages.add(root)
    return sorted(packages)


class SandboxExecutor:
    def __init__(self) -> None:
        self._client = docker.from_env()
        WORK_DIR.mkdir(parents=True, exist_ok=True)

    def execute(
        self,
        code: str,
        extra_packages: list[str] | None = None,
        timeout: int = TIMEOUT_SEC,
    ) -> ExecutionResult:
        start = time.time()

        # ── Vérification sécurité ─────────────────────────────────────────────
        blocked = check_dangerous_imports(code)
        if blocked:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Imports dangereux refusés : {', '.join(blocked)}",
                duration_s=0.0,
                blocked=blocked,
            )

        # ── Détection packages ────────────────────────────────────────────────
        detected  = _detect_packages(code)
        all_pkgs  = list(set((extra_packages or []) + detected))
        safe_pkgs = [p for p in all_pkgs if p not in DANGEROUS_IMPORTS]

        # ── Écriture du code dans un fichier temporaire ───────────────────────
        run_id   = uuid.uuid4().hex[:8]
        code_dir = WORK_DIR / run_id
        code_dir.mkdir(parents=True, exist_ok=True)
        code_file = code_dir / "run.py"
        code_file.write_text(code, encoding="utf-8")

        # ── Commande ──────────────────────────────────────────────────────────
        install_cmd = ""
        if safe_pkgs:
            pkgs = " ".join(safe_pkgs)
            install_cmd = f"pip install -q {pkgs} && "

        cmd = f'sh -c "{install_cmd}python /code/run.py"'

        container = None
        try:
            container = self._client.containers.run(
                SANDBOX_IMAGE,
                command=cmd,
                volumes={str(code_dir.resolve()): {"bind": "/code", "mode": "ro"}},
                network_disabled=True,
                mem_limit=MEMORY_LIMIT,
                nano_cpus=int(CPU_LIMIT * 1e9),
                tmpfs={TMPFS_PATH: "size=64m,mode=1777"},
                read_only=True,
                remove=False,
                detach=True,
                stdout=True,
                stderr=True,
            )
            exit_status = container.wait(timeout=timeout)
            stdout = container.logs(stdout=True, stderr=False).decode()
            stderr_raw = container.logs(stdout=False, stderr=True).decode()
            success = exit_status.get("StatusCode", 1) == 0
            stderr = stderr_raw if not success else ""
        except Exception as e:
            stdout = ""
            stderr = str(e)
            success = False
        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass
            import shutil
            shutil.rmtree(code_dir, ignore_errors=True)

        duration = time.time() - start
        return ExecutionResult(
            success=success,
            stdout=stdout[:4096],
            stderr=stderr[:2048],
            duration_s=round(duration, 2),
            blocked=[],
        )
