"""Orchestration CrewAI — agents spécialisés exposés via FastAPI :8100."""

from __future__ import annotations

import os
from typing import Any

from crewai import Agent, Crew, Process, Task
from crewai_tools import SerperDevTool
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

_LITELLM_URL = os.getenv("LITELLM_URL",   "http://localhost:4000")
_LITELLM_KEY = os.getenv("LITELLM_API_KEY","sk-local")
_SEARXNG_URL = os.getenv("SEARXNG_URL",   "http://localhost:8888")
_QDRANT_URL  = os.getenv("QDRANT_URL",    "http://localhost:6333")


def _llm(model: str) -> ChatOpenAI:
    """LLM via LiteLLM (OpenAI-compatible)."""
    return ChatOpenAI(
        model=model,
        openai_api_base=_LITELLM_URL,
        openai_api_key=_LITELLM_KEY,
        temperature=0.1,
    )


# ── Agent factories ───────────────────────────────────────────────────────────

def make_research_agent() -> Agent:
    return Agent(
        role="Chercheur IA",
        goal="Rechercher, synthétiser et présenter des informations fiables sur n'importe quel sujet",
        backstory=(
            "Expert en recherche d'information. Tu utilises SearXNG pour chercher sur le web, "
            "consultes la base de connaissance locale (Qdrant) et synthétises des résultats complets."
        ),
        llm=_llm("deepseek"),
        verbose=True,
        allow_delegation=False,
    )


def make_code_agent() -> Agent:
    return Agent(
        role="Développeur Python Senior",
        goal="Générer, debugger et tester du code Python de haute qualité",
        backstory=(
            "Expert Python avec 10 ans d'expérience. Tu écris du code propre, typé, "
            "avec des tests pytest. Tu identifies les bugs et proposes des corrections."
        ),
        llm=_llm("qwen2.5-coder:7b"),
        verbose=True,
        allow_delegation=False,
    )


def make_rag_agent() -> Agent:
    return Agent(
        role="Spécialiste RAG",
        goal="Ingérer des documents et répondre à des questions via retrieval augmenté",
        backstory=(
            "Expert en RAG hybride. Tu charges des documents, les vectorises dans Qdrant "
            "et les retrouves avec précision pour répondre aux questions."
        ),
        llm=_llm("mistral"),
        verbose=True,
        allow_delegation=False,
    )


def make_devops_agent() -> Agent:
    return Agent(
        role="DevOps & SRE",
        goal="Monitorer l'infrastructure Docker, analyser les métriques Prometheus et résoudre les incidents",
        backstory=(
            "Ingénieur SRE expérimenté. Tu surveilles les conteneurs Docker, lis les métriques "
            "Prometheus, identifies les anomalies et proposes des actions correctives."
        ),
        llm=_llm("mistral"),
        verbose=True,
        allow_delegation=False,
    )


def make_security_agent() -> Agent:
    return Agent(
        role="Expert Sécurité",
        goal="Auditer le code, scanner les vulnérabilités et détecter les anomalies de sécurité",
        backstory=(
            "Spécialiste cybersécurité. Tu analyses le code pour injection, secrets hardcodés, "
            "vulnérabilités OWASP, et tu interprètes les résultats de Trivy."
        ),
        llm=_llm("deepseek"),
        verbose=True,
        allow_delegation=False,
    )


# ── Crew orchestration ────────────────────────────────────────────────────────

AGENT_MAP = {
    "research": make_research_agent,
    "code":     make_code_agent,
    "rag":      make_rag_agent,
    "devops":   make_devops_agent,
    "security": make_security_agent,
}


def run_agent(agent_name: str, task_description: str) -> str:
    """Exécute un agent pour une tâche donnée. Retourne le résultat."""
    if agent_name not in AGENT_MAP:
        raise ValueError(f"Agent inconnu: {agent_name}. Disponibles: {list(AGENT_MAP)}")

    agent = AGENT_MAP[agent_name]()
    task  = Task(
        description=task_description,
        expected_output="Réponse détaillée et structurée à la demande.",
        agent=agent,
    )
    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
    )
    result = crew.kickoff()
    return str(result)


def run_multi_agent(tasks: list[dict[str, str]]) -> list[str]:
    """Exécute plusieurs agents séquentiellement avec mémoire partagée."""
    agents_list, tasks_list = [], []
    for t in tasks:
        agent = AGENT_MAP[t["agent"]]()
        task  = Task(
            description=t["task"],
            expected_output="Résultat structuré.",
            agent=agent,
        )
        agents_list.append(agent)
        tasks_list.append(task)

    crew = Crew(
        agents=agents_list,
        tasks=tasks_list,
        process=Process.sequential,
        verbose=True,
    )
    result = crew.kickoff()
    return [str(result)]


# ── FastAPI ───────────────────────────────────────────────────────────────────

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Jarvis Agents API", version="1.0")


class RunRequest(BaseModel):
    agent: str
    task: str


class RunResponse(BaseModel):
    agent: str
    result: str


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "agents": list(AGENT_MAP)}


@app.post("/run", response_model=RunResponse)
async def run(req: RunRequest) -> RunResponse:
    try:
        result = run_agent(req.agent, req.task)
        return RunResponse(agent=req.agent, result=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agents")
async def list_agents() -> dict[str, list[str]]:
    return {"agents": list(AGENT_MAP)}


if __name__ == "__main__":
    port = int(os.getenv("AGENTS_API_PORT", "8100"))
    uvicorn.run(app, host="0.0.0.0", port=port)
