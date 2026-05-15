"""Interface Streamlit pour piloter les agents CrewAI Jarvis."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests
import streamlit as st

# ── Config page ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Jarvis — Multi-Agents",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

AGENTS_API = os.getenv("AGENTS_API_URL", "http://localhost:8100")

AGENT_INFO = {
    "research": {
        "icon": "🔍",
        "model": "deepseek-r1:14b",
        "desc": "Recherche web via SearXNG + base de connaissances Qdrant",
    },
    "code": {
        "icon": "💻",
        "model": "qwen2.5-coder:7b",
        "desc": "Génération, debug et review de code Python",
    },
    "rag": {
        "icon": "📚",
        "model": "mistral:7b",
        "desc": "Ingestion de documents et retrieval augmenté",
    },
    "devops": {
        "icon": "🐳",
        "model": "mistral:7b",
        "desc": "Monitoring Docker + métriques Prometheus",
    },
    "security": {
        "icon": "🔒",
        "model": "deepseek-r1:14b",
        "desc": "Audit sécurité, scan vulnérabilités, OWASP",
    },
}

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🤖 Jarvis Agents")
    st.divider()

    # Statut API
    try:
        health = requests.get(f"{AGENTS_API}/health", timeout=3)
        if health.status_code == 200:
            st.success("✅ API Agents connectée")
            data = health.json()
            st.caption(f"Agents: {', '.join(data.get('agents', []))}")
        else:
            st.error("❌ API non disponible")
    except Exception:
        st.warning("⚠️ API inaccessible — démo mode")

    st.divider()
    st.markdown("### Agents disponibles")
    for name, info in AGENT_INFO.items():
        st.markdown(f"{info['icon']} **{name}** — `{info['model']}`")
        st.caption(info["desc"])

    st.divider()
    st.caption("Stack Jarvis · LiteLLM · Ollama")

# ── Tabs principales ──────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["🎯 Agent Unique", "🤝 Multi-Agents", "📊 Statut"])

# ── TAB 1 : Agent Unique ──────────────────────────────────────────────────────
with tab1:
    st.header("Agent Unique")
    st.markdown("Lance une tâche sur un seul agent spécialisé.")

    col1, col2 = st.columns([1, 3])
    with col1:
        selected_agent = st.selectbox(
            "Agent",
            list(AGENT_INFO.keys()),
            format_func=lambda x: f"{AGENT_INFO[x]['icon']} {x}",
        )
        info = AGENT_INFO[selected_agent]
        st.info(f"**Modèle:** {info['model']}\n\n{info['desc']}")

    with col2:
        task_input = st.text_area(
            "Tâche à accomplir",
            placeholder="Ex: Analyse les dernières vulnérabilités de Log4j et leur impact...",
            height=150,
        )

        if st.button("🚀 Lancer", type="primary", disabled=not task_input.strip()):
            with st.spinner(f"Agent {selected_agent} en cours..."):
                start = time.time()
                try:
                    resp = requests.post(
                        f"{AGENTS_API}/run",
                        json={"agent": selected_agent, "task": task_input},
                        timeout=300,
                    )
                    elapsed = time.time() - start
                    if resp.status_code == 200:
                        result = resp.json().get("result", "")
                        st.success(f"✅ Terminé en {elapsed:.1f}s")
                        st.markdown("### Résultat")
                        st.markdown(result)
                    else:
                        st.error(f"Erreur {resp.status_code}: {resp.text}")
                except requests.exceptions.Timeout:
                    st.error("⏱️ Timeout — la tâche prend trop longtemps (>5min)")
                except Exception as e:
                    st.error(f"Erreur: {e}")

# ── TAB 2 : Multi-Agents ──────────────────────────────────────────────────────
with tab2:
    st.header("Pipeline Multi-Agents")
    st.markdown("Les agents collaborent séquentiellement — chacun utilise le résultat du précédent.")

    preset = st.selectbox(
        "Pipeline prédéfini",
        [
            "Analyse technique complète",
            "Audit sécurité",
            "Review de code",
            "État infrastructure",
        ],
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        if preset == "Analyse technique complète":
            topic = st.text_input("Sujet", placeholder="Ex: RAG avec Qdrant et LlamaIndex")
            tasks_config = [
                {"agent": "research", "task": f"Recherche les dernières avancées sur: {topic}"},
                {"agent": "code", "task": f"Génère un exemple de code Python pour: {topic}"},
                {"agent": "security", "task": f"Identifie les risques de sécurité liés à: {topic}"},
            ]
        elif preset == "Audit sécurité":
            target = st.text_input("Cible", value="stack Docker Jarvis")
            tasks_config = [
                {"agent": "devops", "task": f"Liste tous les services et leur état pour: {target}"},
                {"agent": "security", "task": f"Audite la sécurité de: {target}"},
            ]
        elif preset == "Review de code":
            code = st.text_area("Code à analyser", height=200)
            tasks_config = [
                {"agent": "code", "task": f"Review ce code Python:\n```python\n{code}\n```"},
                {"agent": "security", "task": "Vérifie les problèmes de sécurité dans le code précédent"},
            ]
        else:
            tasks_config = [
                {"agent": "devops", "task": "Liste l'état de tous les containers Docker"},
                {"agent": "research", "task": "Cherche des solutions pour optimiser un stack Docker IA"},
            ]

    with col2:
        st.markdown("### Pipeline")
        for i, t in enumerate(tasks_config, 1):
            info = AGENT_INFO[t["agent"]]
            st.markdown(f"{i}. {info['icon']} **{t['agent']}**")

    if st.button("🚀 Lancer le pipeline", type="primary"):
        results_container = st.container()
        with results_container:
            for i, task_cfg in enumerate(tasks_config, 1):
                agent_name = task_cfg["agent"]
                info = AGENT_INFO[agent_name]
                with st.expander(f"{info['icon']} Étape {i} — Agent {agent_name}", expanded=True):
                    with st.spinner(f"Agent {agent_name} en cours..."):
                        try:
                            resp = requests.post(
                                f"{AGENTS_API}/run",
                                json=task_cfg,
                                timeout=300,
                            )
                            if resp.status_code == 200:
                                result = resp.json().get("result", "")
                                st.markdown(result)
                            else:
                                st.error(f"Erreur: {resp.text}")
                        except Exception as e:
                            st.error(f"Erreur: {e}")

# ── TAB 3 : Statut ────────────────────────────────────────────────────────────
with tab3:
    st.header("Statut de la stack")

    if st.button("🔄 Rafraîchir"):
        st.rerun()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("API Agents")
        try:
            h = requests.get(f"{AGENTS_API}/health", timeout=5)
            if h.ok:
                st.json(h.json())
            else:
                st.error(f"HTTP {h.status_code}")
        except Exception as e:
            st.error(str(e))

    with col2:
        st.subheader("Services connectés")
        services = {
            "LiteLLM": os.getenv("LITELLM_URL", "http://litellm:4000") + "/health",
            "Qdrant": os.getenv("QDRANT_URL", "http://qdrant:6333") + "/readiness",
            "SearXNG": os.getenv("SEARXNG_URL", "http://searxng:8888") + "/healthz",
        }
        for name, url in services.items():
            try:
                r = requests.get(url, timeout=3)
                status = "✅" if r.ok else "⚠️"
                st.markdown(f"{status} **{name}** — `{url}`")
            except Exception:
                st.markdown(f"❌ **{name}** — inaccessible")
