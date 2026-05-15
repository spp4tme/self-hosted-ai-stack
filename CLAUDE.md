# Jarvis — Self-Hosted AI Stack

## Architecture

Stack IA locale complète tournant sur Windows 11 + Docker Desktop (WSL2), RTX 5070 Ti.

## Services principaux

| Service | URL locale | Container |
|---------|-----------|-----------|
| Ollama | http://localhost:11434 | natif Windows |
| LiteLLM proxy | http://localhost:4000 | litellm |
| Open WebUI | http://localhost:8080 | open-webui |
| Qdrant | http://localhost:6333 | qdrant |
| SearXNG | http://localhost:8888 | searxng |
| n8n | http://localhost:5678 | n8n |
| Langfuse | http://localhost:3000 | langfuse |
| Grafana | http://localhost:3001 | grafana |
| Prometheus | http://localhost:9090 | prometheus |
| Authentik SSO | http://localhost:9000 | authentik |
| ComfyUI | http://localhost:8188 | comfyui |
| Whisper STT | http://localhost:8001 | whisper |

## Services nouveaux (docker-compose.additions.yml)

| Service | Port | Description |
|---------|------|-------------|
| Agents API (CrewAI) | :8100 | POST /run {agent, task} |
| Sandbox API | :8101 | POST /execute {code, packages} |
| Code Reviewer | :8102 | Webhook GitHub PR review |
| Self-Heal Metrics | :9099 | GET /metrics (Prometheus) |

## Modèles Ollama disponibles

- `deepseek-r1:14b` — raisonnement, critique, sécurité
- `mistral:7b` — général, RAG, devops
- `qwen2.5-coder:7b` — code generation et review
- `llava:13b` — vision multimodale
- `moondream` — computer use (actions écran)
- `nomic-embed-text` — embeddings RAG

## Modules Python (src/)

```
memory/store.py          MemoryStore — Mem0 + Qdrant (1 collection/user)
vision/analyzer.py       VisionAnalyzer — LLaVA + Moondream
agents/crew.py           Orchestration CrewAI + FastAPI :8100
agents/constitutional.py Pipeline auto-critique 3 étapes
agents/ensemble.py       Vote majoritaire multi-modèles
agents/code_reviewer.py  Review PR GitHub + webhook :8102
finetune/run_finetune.py Fine-tuning LoRA Unsloth (WSL2/Linux requis)
finetune/prepare_dataset.py Conversion Open WebUI → Alpaca
finetune/eval.py         Évaluation modèle fine-tuné
computer_use/agent.py    Boucle vision→action (screenshot+pyautogui)
sandbox/executor.py      Exécution code isolée Docker
sandbox/api.py           FastAPI sandbox :8101
devops/self_heal.py      Self-healing + métriques Prometheus :9099
```

## Règles de développement

- **Tous les appels LLM via LiteLLM :4000** (sauf vision → Ollama direct, fine-tuning → HuggingFace)
- Python 3.12+, type hints partout, async/await pour les I/O réseau
- Pas de secrets hardcodés → `.env` (voir `.env.example`)
- Tests pytest dans `tests/`
- Lancer les tests : `pytest tests/ -v`

## Agents disponibles

```
research  — deepseek-r1:14b — SearXNG + Qdrant RAG
code      — qwen2.5-coder:7b — génération/debug Python
rag       — mistral:7b — ingestion Docling + retrieval
devops    — mistral:7b — monitoring Docker + Prometheus
security  — deepseek-r1:14b — scan Trivy + audit
```

Appel : `curl -X POST http://localhost:8100/run -d '{"agent":"research","task":"..."}'`

## Jarvis CLI — Terminal AI Assistant

Package installable partout (local ou via Tailscale SSH).

```
jarvis_cli/
├── __main__.py     # entry point CLI
├── agent.py        # boucle REPL + appels LLM avec outils
├── tools.py        # bash, read_file, write_file, edit_file, glob, grep, web_search, memory_*
├── config.py       # ~/.jarvis/config.json
└── display.py      # Rich panels, markdown, spinners
```

### Installation

```bash
# Sur la machine principale (depuis ce dossier)
pip install -e .

# Sur n'importe quelle autre machine (via SSH Tailscale)
pip install -e git+https://github.com/spp4tme/self-hosted-ai-stack#egg=jarvis-cli
# puis pointer vers LiteLLM distant :
jarvis --url http://100.x.x.x:4000
```

### Utilisation

```bash
jarvis                              # REPL interactif
jarvis "liste les fichiers Python"  # one-shot
jarvis --model deepseek-coder       # changer de modèle
jarvis --url http://100.x.x.x:4000 # stack distante via Tailscale

# Commandes REPL :
/help   /clear   /model <nom>   /memory   /remember <texte>   /quit
```

### Config : ~/.jarvis/config.json

```json
{
  "litellm_url": "http://localhost:4000",
  "litellm_key": "sk-local",
  "model": "mistral",
  "searxng_url": "http://localhost:8888"
}
```

### Outils disponibles pour le LLM

| Outil | Description |
|-------|-------------|
| `bash` | Exécute une commande shell (PS ou bash) |
| `read_file` | Lit un fichier (avec offset/limit) |
| `write_file` | Crée ou remplace un fichier |
| `edit_file` | Remplace une chaîne dans un fichier |
| `glob` | Liste des fichiers par pattern |
| `grep` | Recherche regex dans les fichiers |
| `web_search` | SearXNG (local) |
| `memory_search` | Qdrant + Mem0 sémantique |
| `memory_add` | Sauvegarde un souvenir |

## Variables d'environnement clés

Copier `.env.example` → `.env` et remplir :
- `GITHUB_TOKEN` — pour le code reviewer
- `GITHUB_REPO` — format `owner/repo`
- `LITELLM_API_KEY` — clé interne (sk-local par défaut)
