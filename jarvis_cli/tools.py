"""Tool implementations exposed to the LLM via function calling."""

from __future__ import annotations

import asyncio
import glob as _glob
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import aiohttp

# ── Tool schemas (OpenAI function-calling format) ────────────────────────────

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Exécute une commande shell (PowerShell sur Windows, bash sur Linux/Mac). Timeout 30s.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "La commande à exécuter"},
                    "timeout": {"type": "integer", "description": "Timeout en secondes (défaut 30)", "default": 30},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Lit le contenu d'un fichier texte.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Chemin absolu ou relatif du fichier"},
                    "offset": {"type": "integer", "description": "Ligne de départ (0 = début)", "default": 0},
                    "limit":  {"type": "integer", "description": "Nombre max de lignes à lire", "default": 300},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Crée ou remplace un fichier avec le contenu fourni.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path":    {"type": "string", "description": "Chemin du fichier"},
                    "content": {"type": "string", "description": "Contenu à écrire"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Remplace une chaîne exacte dans un fichier (première occurrence).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path":       {"type": "string", "description": "Chemin du fichier"},
                    "old_string": {"type": "string", "description": "Texte à remplacer (exact)"},
                    "new_string": {"type": "string", "description": "Texte de remplacement"},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "glob",
            "description": "Liste les fichiers correspondant à un pattern glob.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Pattern glob, ex: src/**/*.py"},
                    "root":    {"type": "string", "description": "Répertoire racine (défaut: répertoire courant)"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Recherche un pattern regex dans des fichiers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern":  {"type": "string", "description": "Pattern regex à chercher"},
                    "path":     {"type": "string", "description": "Répertoire ou fichier (défaut: .)"},
                    "glob":     {"type": "string", "description": "Filtre de fichiers, ex: *.py"},
                    "context":  {"type": "integer", "description": "Lignes de contexte autour des matches", "default": 2},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Recherche sur le web via SearXNG.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query":  {"type": "string", "description": "Requête de recherche"},
                    "limit":  {"type": "integer", "description": "Nombre de résultats (défaut 5)", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_search",
            "description": "Cherche dans la mémoire long terme de Jarvis (Mem0 + Qdrant).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query":   {"type": "string", "description": "Requête de recherche sémantique"},
                    "limit":   {"type": "integer", "description": "Nombre de souvenirs retournés", "default": 5},
                    "user_id": {"type": "string", "description": "ID utilisateur (défaut: default)", "default": "default"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_add",
            "description": "Sauvegarde un souvenir dans la mémoire long terme.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text":    {"type": "string", "description": "Texte à mémoriser"},
                    "user_id": {"type": "string", "description": "ID utilisateur (défaut: default)", "default": "default"},
                },
                "required": ["text"],
            },
        },
    },
]


# ── Tool implementations ─────────────────────────────────────────────────────

async def bash(command: str, timeout: int = 30) -> str:
    import platform
    if platform.system() == "Windows":
        proc = await asyncio.create_subprocess_exec(
            "powershell", "-NonInteractive", "-Command", command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    else:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return f"[TIMEOUT après {timeout}s]"
    out = stdout.decode(errors="replace").strip()
    err = stderr.decode(errors="replace").strip()
    parts = []
    if out:
        parts.append(out)
    if err:
        parts.append(f"[stderr]\n{err}")
    return "\n".join(parts) or "(pas de sortie)"


def read_file(path: str, offset: int = 0, limit: int = 300) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"Fichier introuvable: {path}"
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        chunk = lines[offset: offset + limit]
        result = "\n".join(f"{offset+i+1:4}: {l}" for i, l in enumerate(chunk))
        if offset + limit < len(lines):
            result += f"\n[...{len(lines) - offset - limit} lignes restantes...]"
        return result or "(fichier vide)"
    except Exception as e:
        return f"Erreur lecture: {e}"


def write_file(path: str, content: str) -> str:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Fichier écrit: {path} ({len(content)} caractères)"


def edit_file(path: str, old_string: str, new_string: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"Fichier introuvable: {path}"
    content = p.read_text(encoding="utf-8")
    if old_string not in content:
        return f"Chaîne non trouvée dans {path}"
    new_content = content.replace(old_string, new_string, 1)
    p.write_text(new_content, encoding="utf-8")
    return f"Modification appliquée dans {path}"


def glob(pattern: str, root: str | None = None) -> str:
    base = Path(root).expanduser() if root else Path.cwd()
    matches = sorted(str(p) for p in base.glob(pattern))
    if not matches:
        return "(aucun fichier trouvé)"
    return "\n".join(matches[:200])


def grep(pattern: str, path: str = ".", glob_filter: str | None = None, context: int = 2) -> str:
    import platform
    cmd_parts = ["rg", "--color=never", f"-C{context}", pattern, path]
    if glob_filter:
        cmd_parts += ["-g", glob_filter]
    try:
        result = subprocess.run(
            cmd_parts, capture_output=True, text=True, timeout=15,
            encoding="utf-8", errors="replace",
        )
        out = result.stdout.strip()
        return out[:8000] if out else "(aucun résultat)"
    except FileNotFoundError:
        # fallback: Python regex search
        lines_out: list[str] = []
        base = Path(path)
        files = list(base.rglob(glob_filter or "*")) if base.is_dir() else [base]
        rx = re.compile(pattern)
        for f in files:
            if not f.is_file():
                continue
            try:
                file_lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            for i, line in enumerate(file_lines):
                if rx.search(line):
                    start = max(0, i - context)
                    end   = min(len(file_lines), i + context + 1)
                    lines_out.append(f"\n=== {f} (ligne {i+1}) ===")
                    lines_out.extend(file_lines[start:end])
                    if len("\n".join(lines_out)) > 8000:
                        break
        return "\n".join(lines_out)[:8000] or "(aucun résultat)"


async def web_search(query: str, limit: int = 5, searxng_url: str = "http://localhost:8888") -> str:
    url = f"{searxng_url}/search"
    params = {"q": query, "format": "json", "engines": "google,bing,duckduckgo"}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    return f"SearXNG error {resp.status}"
                data = await resp.json(content_type=None)
        results = data.get("results", [])[:limit]
        if not results:
            return "Aucun résultat trouvé."
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.get('title','')}\n   {r.get('url','')}\n   {r.get('content','')[:200]}")
        return "\n\n".join(lines)
    except Exception as e:
        return f"Erreur web_search: {e}"


async def memory_search(query: str, limit: int = 5, user_id: str = "default") -> str:
    try:
        import sys, os
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from memory.store import MemoryStore
        store = MemoryStore(user_id=user_id)
        results = store.search(query, limit=limit)
        if not results:
            return "Aucun souvenir trouvé."
        return "\n".join(f"- {r.get('memory','')}" for r in results if "memory" in r)
    except Exception as e:
        return f"Mémoire indisponible: {e}"


async def memory_add(text: str, user_id: str = "default") -> str:
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from memory.store import MemoryStore
        store = MemoryStore(user_id=user_id)
        store.add(text)
        return "Souvenir sauvegardé."
    except Exception as e:
        return f"Erreur mémoire: {e}"


# ── Dispatcher ────────────────────────────────────────────────────────────────

async def dispatch(name: str, args: dict[str, Any], cfg: dict[str, Any]) -> tuple[str, bool]:
    """Returns (result_str, success)."""
    try:
        if name == "bash":
            return await bash(args["command"], args.get("timeout", 30)), True
        elif name == "read_file":
            return read_file(args["path"], args.get("offset", 0), args.get("limit", 300)), True
        elif name == "write_file":
            return write_file(args["path"], args["content"]), True
        elif name == "edit_file":
            return edit_file(args["path"], args["old_string"], args["new_string"]), True
        elif name == "glob":
            return glob(args["pattern"], args.get("root")), True
        elif name == "grep":
            return grep(args["pattern"], args.get("path", "."), args.get("glob"), args.get("context", 2)), True
        elif name == "web_search":
            return await web_search(args["query"], args.get("limit", 5), cfg.get("searxng_url", "http://localhost:8888")), True
        elif name == "memory_search":
            return await memory_search(args["query"], args.get("limit", 5), args.get("user_id", "default")), True
        elif name == "memory_add":
            return await memory_add(args["text"], args.get("user_id", "default")), True
        else:
            return f"Outil inconnu: {name}", False
    except Exception as e:
        return f"Erreur dans {name}: {e}", False
