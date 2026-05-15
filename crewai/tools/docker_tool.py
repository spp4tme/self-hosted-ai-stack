"""Outil CrewAI — Statut et gestion des containers Docker."""

from __future__ import annotations

from typing import Type

import docker
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class DockerContainerInput(BaseModel):
    container_name: str = Field(default="", description="Nom du container (vide = tous)")


class DockerStatusTool(BaseTool):
    name: str = "Docker Container Status"
    description: str = (
        "Liste l'état de tous les containers Docker ou d'un container spécifique. "
        "Retourne: nom, image, état, ports, uptime."
    )
    args_schema: Type[BaseModel] = DockerContainerInput

    def _run(self, container_name: str = "") -> str:
        try:
            client = docker.from_env()
            containers = client.containers.list(all=True)
            if container_name:
                containers = [c for c in containers if container_name in c.name]
                if not containers:
                    return f"Container '{container_name}' introuvable."
            lines = [f"{'NOM':<30} {'IMAGE':<35} {'ÉTAT':<12} {'PORTS'}"]
            lines.append("-" * 100)
            for c in containers:
                ports = ", ".join(
                    f"{h[0]['HostPort']}→{p}"
                    for p, h in (c.ports or {}).items()
                    if h
                ) or "—"
                image_name = c.image.tags[0] if c.image.tags else c.image.short_id
                lines.append(f"{c.name:<30} {image_name:<35} {c.status:<12} {ports}")
            return "\n".join(lines)
        except Exception as e:
            return f"Erreur Docker: {e}"


class DockerLogsInput(BaseModel):
    container_name: str = Field(..., description="Nom du container")
    lines: int = Field(default=50, description="Nombre de lignes de logs à retourner")


class DockerLogsTool(BaseTool):
    name: str = "Docker Container Logs"
    description: str = "Récupère les logs récents d'un container Docker."
    args_schema: Type[BaseModel] = DockerLogsInput

    def _run(self, container_name: str, lines: int = 50) -> str:
        try:
            client = docker.from_env()
            container = client.containers.get(container_name)
            logs = container.logs(tail=lines).decode(errors="replace")
            return logs or "(aucun log)"
        except docker.errors.NotFound:
            return f"Container '{container_name}' introuvable."
        except Exception as e:
            return f"Erreur logs Docker: {e}"
