# Jarvis — Self-Hosted AI Stack

> Stack IA locale complète, souveraine et extensible — tournant sur Windows 11 + Docker Desktop (WSL2) avec GPU NVIDIA RTX 5070 Ti.

[![CI](https://github.com/spp4tme/self-hosted-ai-stack/actions/workflows/ci.yml/badge.svg)](https://github.com/spp4tme/self-hosted-ai-stack/actions/workflows/ci.yml)
[![Security](https://github.com/spp4tme/self-hosted-ai-stack/actions/workflows/security.yml/badge.svg)](https://github.com/spp4tme/self-hosted-ai-stack/actions/workflows/security.yml)

Jarvis est un écosystème IA self-hosted qui regroupe : un proxy LLM unifié, des agents intelligents collaboratifs (CrewAI), une mémoire long terme, de la vision multimodale, un sandbox d'exécution de code, du fine-tuning LoRA, un contrôle PC par gestes, un assistant CLI type Claude Code, un reverse proxy Traefik, un CI/CD GitHub Actions, et un GitOps webhook — le tout orchestré localement, sans aucun cloud obligatoire.

---

## Table des matières

- [Architecture](#architecture)
- [Services Docker](#services-docker)
- [Modules Python](#modules-python)
- [Jarvis CLI](#jarvis-cli)
- [Jarvis Gesture Control](#jarvis-gesture-control)
- [Démarrage rapide](#démarrage-rapide)
- [Configuration](#configuration)
- [Agents IA](#agents-ia)
- [Traefik — Reverse Proxy](#traefik--reverse-proxy)
- [CI/CD GitHub Actions](#cicd-github-actions)
- [GitOps Webhook](#gitops-webhook)
- [API Reference](#api-reference)
- [Fine-tuning](#fine-tuning)
- [Tests](#tests)
- [Structure du projet](#structure-du-projet)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          JARVIS STACK                               │
│                                                                     │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────┐    │
│  │  Ollama  │   │ LiteLLM  │   │Open WebUI│   │   Langfuse   │    │
│  │ :11434   │──▶│  :4000   │──▶│  :8080   │   │  (tracing)   │    │
│  │ (natif)  │   │ (proxy)  │   │(chat UI) │   │    :3000     │    │
│  └──────────┘   └──────────┘   └──────────┘   └──────────────┘    │
│       │                                                             │
│  ┌────▼─────┐   ┌──────────┐   ┌──────────┐   ┌──────────────┐    │
│  │  Agents  │   │ Sandbox  │   │  Memory  │   │   Vision     │    │
│  │  CrewAI  │   │  Docker  │   │Mem0+Qdrant│  │LLaVA+Moon-  │    │
│  │  :8100   │   │  :8101   │   │  :6333   │   │  dream      │    │
│  └──────────┘   └──────────┘   └──────────┘   └──────────────┘    │
│                                                                     │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────┐    │
│  │ SearXNG  │   │   n8n    │   │ Grafana  │   │  Authentik   │    │
│  │  :8888   │   │  :5678   │   │  :3001   │   │    SSO       │    │
│  │(recherche│   │(workflow)│   │(métriques│   │    :9000     │    │
│  └──────────┘   └──────────┘   └──────────┘   └──────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

**Modèles Ollama disponibles :**

| Modèle | Usage |
|--------|-------|
| `deepseek-r1:14b` | Raisonnement, critique, sécurité |
| `mistral:7b` | Général, RAG, DevOps |
| `qwen2.5-coder:7b` | Génération et review de code |
| `llava:13b` | Vision multimodale |
| `moondream` | Computer use (actions écran) |
| `nomic-embed-text` | Embeddings RAG |

---

## Services Docker

### Stack principale (`docker-compose.yaml`)

| Service | URL | Description |
|---------|-----|-------------|
| **Open WebUI** | http://localhost:8080 | Interface chat principale (type ChatGPT) |
| **LiteLLM** | http://localhost:4000 | Proxy OpenAI-compatible vers tous les modèles |
| **Ollama** | http://localhost:11434 | Serveur de modèles LLM local (natif Windows) |
| **Qdrant** | http://localhost:6333 | Base vectorielle pour RAG et mémoire |
| **SearXNG** | http://localhost:8888 | Moteur de recherche web privé |
| **n8n** | http://localhost:5678 | Automatisation workflows IA |
| **Langfuse** | http://localhost:3000 | Observabilité et tracing LLM |
| **Grafana** | http://localhost:3001 | Dashboards métriques |
| **Prometheus** | http://localhost:9090 | Collecte de métriques |
| **Authentik SSO** | http://localhost:9000 | Authentification centralisée |
| **ComfyUI** | http://localhost:8188 | Génération d'images Stable Diffusion |
| **Whisper STT** | http://localhost:8001 | Transcription vocale locale |

### Services additionnels (`docker-compose.additions.yml`)

| Service | Port | Description |
|---------|------|-------------|
| **Agents API** | :8100 | API CrewAI — 5 agents spécialisés |
| **Sandbox API** | :8101 | Exécution de code isolée en Docker |
| **Code Reviewer** | :8102 | Review automatique de PR GitHub |
| **Self-Heal Metrics** | :9099 | Monitoring + auto-restart + Prometheus |

---

## Modules Python

### `memory/store.py` — Mémoire long terme

Mémoire persistante par utilisateur via **Mem0 + Qdrant**. Stockage vectoriel sémantique, recherche par proximité, injection automatique dans le contexte système.

```python
from memory.store import MemoryStore

store = MemoryStore(user_id="prénom")
store.add("Je préfère Python à JavaScript")
results = store.search("quel langage utiliser ?", limit=5)
context = store.build_context("choix technologique")  # → injecte dans system prompt
```

**Méthodes :** `add()` · `search()` · `get_all()` · `delete()` · `delete_all()` · `build_context()`

---

### `vision/analyzer.py` — Vision multimodale

Analyse d'images via **LLaVA:13b** (description) et **Moondream** (computer use). Appels directs à Ollama pour les modèles vision.

```python
from vision.analyzer import VisionAnalyzer

analyzer = VisionAnalyzer()
result = await analyzer.analyze_bytes(image_bytes, mode="error")
action = await analyzer.analyze_for_action(Path("screenshot.png"), "clique sur OK")
```

**Modes disponibles :** `general` · `error` · `dashboard` · `code` · `ui` · `security` · `document`

---

### `agents/crew.py` — Orchestration multi-agents

**5 agents CrewAI** spécialisés exposés via FastAPI sur `:8100` :

| Agent | Modèle | Capacités |
|-------|--------|-----------|
| `research` | deepseek-r1:14b | SearXNG + Qdrant RAG |
| `code` | qwen2.5-coder:7b | Génération, debug, refactoring Python |
| `rag` | mistral:7b | Ingestion Docling + retrieval documentaire |
| `devops` | mistral:7b | Monitoring Docker + Prometheus |
| `security` | deepseek-r1:14b | Scan Trivy + audit sécurité |

```bash
curl -X POST http://localhost:8100/run \
  -H "Content-Type: application/json" \
  -d '{"agent": "research", "task": "Meilleures pratiques RAG en 2025 ?"}'
```

---

### `agents/constitutional.py` — IA Constitutionnelle

Pipeline **3 étapes** garantissant des réponses éthiques et de qualité :

1. **Génération** — réponse initiale (mistral)
2. **Critique** — identification des violations de principes (deepseek-r1:14b)
3. **Révision** — réécriture en corrigeant les problèmes détectés

```python
from agents.constitutional import constitutional_pipeline

result = await constitutional_pipeline("Comment contourner une sécurité ?")
# → Réponse révisée, éthique et constructive
```

---

### `agents/ensemble.py` — Vote majoritaire multi-modèles

Interroge **2 modèles en parallèle** (deepseek + mistral) et fusionne les réponses :
- Divergence < 0.45 → fusion des deux réponses
- Divergence ≥ 0.45 → arbitrage par un 3ème modèle

```python
from agents.ensemble import ensemble_query

result = await ensemble_query("Explique les transformers")
# → Réponse de consensus, plus robuste qu'un seul modèle
```

---

### `agents/code_reviewer.py` — Review automatique de PR

Webhook GitHub qui déclenche une review automatique à chaque **Pull Request** :
- Analyse via `qwen2.5-coder:7b`
- Commente directement sur la PR GitHub
- Vérification HMAC-SHA256 de la signature webhook

**Setup GitHub :**
```
Webhook URL  : http://ton-domaine:8102/webhook
Secret       : valeur de GITHUB_WEBHOOK_SECRET dans .env
Content-type : application/json
Événements   : Pull requests
```

---

### `sandbox/executor.py` + `sandbox/api.py` — Sandbox d'exécution

Exécution de code Python **totalement isolée** dans Docker :
- Réseau coupé (`--network none`)
- Mémoire limitée à 512 MB
- Filesystem en lecture seule + tmpfs `/tmp` 64 MB
- Timeout configurable (défaut 30s)
- Détection AST des imports dangereux avant exécution

```bash
curl -X POST http://localhost:8101/execute \
  -H "Content-Type: application/json" \
  -d '{"code": "import math\nprint(math.pi)", "timeout": 10}'
```

**Réponse :**
```json
{
  "success": true,
  "stdout": "3.141592653589793",
  "stderr": "",
  "duration_s": 2.1,
  "blocked": []
}
```

---

### `devops/self_heal.py` — Infrastructure auto-réparatrice

Monitoring en boucle toutes les **30 secondes** :
- Health check HTTP sur tous les services de la stack
- Vérification VRAM GPU et espace disque
- **Auto-restart** des containers en échec via Docker SDK
- Métriques Prometheus exposées sur `:9099/metrics`

```bash
# Métriques Prometheus
curl http://localhost:9099/metrics

# État de santé global
curl http://localhost:9099/health
```

---

### `finetune/` — Fine-tuning LoRA

Fine-tuning de modèles Ollama avec **Unsloth** (LoRA, 4-bit, bf16).

> ⚠️ Nécessite WSL2 / Linux avec CUDA.

```bash
# 1. Préparer le dataset depuis les conversations Open WebUI
python finetune/prepare_dataset.py \
  --input conversations.json \
  --output dataset.jsonl

# 2. Fine-tuner (détection VRAM automatique, batch size adaptatif)
python finetune/run_finetune.py \
  --model mistral:7b \
  --dataset finetune/dataset.jsonl \
  --epochs 3

# 3. Évaluer le modèle fine-tuné
python finetune/eval.py --model ./outputs/model-finetuned

# Export GGUF q4_k_m automatique + Modelfile Ollama généré
```

---

### `computer_use/agent.py` — Contrôle PC par IA

Boucle **vision → action** autonome : capture l'écran → analyse avec Moondream → exécute des actions pyautogui.

```python
from computer_use.agent import ComputerUseAgent

agent = ComputerUseAgent()
await agent.run(goal="Ouvre Firefox et va sur github.com")
# → screenshot → moondream → click/type/scroll → repeat (max 20 iter, 300s timeout)
```

**Sécurité :** failsafe pyautogui activé (coin haut-gauche = arrêt d'urgence), log JSONL de chaque action.

---

## Jarvis CLI

Assistant IA interactif dans le terminal, installable sur n'importe quelle machine.

### Installation

```bash
# Sur la machine principale
git clone https://github.com/spp4tme/self-hosted-ai-stack
cd self-hosted-ai-stack
pip install -e .

# Sur une machine distante (SSH / Tailscale)
pip install -e git+https://github.com/spp4tme/self-hosted-ai-stack#egg=jarvis-cli
jarvis --url http://100.x.x.x:4000
```

### Utilisation

```bash
jarvis                                # REPL interactif
jarvis "liste les fichiers Python"    # one-shot
jarvis --model deepseek-coder         # changer de modèle
jarvis --url http://192.168.1.10:4000 # stack distante
```

**Commandes REPL :**

| Commande | Description |
|----------|-------------|
| `/help` | Afficher l'aide |
| `/clear` | Effacer l'historique de conversation |
| `/model <nom>` | Changer de modèle LLM |
| `/memory` | Voir les souvenirs mémorisés |
| `/remember <texte>` | Sauvegarder un souvenir manuellement |
| `/config` | Voir la configuration actuelle |
| `/quit` | Quitter |

**Outils disponibles pour le LLM :**

| Outil | Description |
|-------|-------------|
| `bash` | Exécute une commande shell (PowerShell ou bash) |
| `read_file` | Lit un fichier avec offset/limit |
| `write_file` | Crée ou remplace un fichier |
| `edit_file` | Remplace une chaîne exacte dans un fichier |
| `glob` | Liste des fichiers par pattern glob |
| `grep` | Recherche regex dans les fichiers |
| `web_search` | Recherche via SearXNG local |
| `memory_search` | Recherche sémantique dans Mem0 + Qdrant |
| `memory_add` | Sauvegarde un souvenir long terme |

### Config (`~/.jarvis/config.json`)

```json
{
  "litellm_url": "http://localhost:4000",
  "litellm_key": "sk-local",
  "model": "mistral",
  "qdrant_url": "http://localhost:6333",
  "searxng_url": "http://localhost:8888",
  "max_tokens": 4096,
  "temperature": 0.7
}
```

---

## Jarvis Gesture Control

Contrôle du PC à la main, sans souris ni clavier, via webcam. Interface AR transparente par-dessus le bureau.

### Lancement

```bash
cd jarvis
python desktop.py
```

### Gestes

| Geste | Action |
|-------|--------|
| ☝️ Index levé | Mode pointeur — déplace le curseur |
| 👆 Pousser vers la caméra (Z-press) | Clic gauche virtuel |
| ✊ Poing fermé | Drag & drop (maintenu) |
| ✌️ Victoire | Clic droit |
| 🤚 Main ouverte | Arrêt / freeze curseur |
| 🖐️ 2 doigts verticaux | Scroll |

### Fonctionnalités techniques

- **Filtre de Kalman** sur X, Y, Z — curseur stable, sans tremblements
- **Zone active** : centre 76%×84% du champ caméra → plein écran (amplitude réduite)
- **Z-press** : profondeur relative de l'index vs baseline lente pour détecter un appui virtuel
- **Overlay AR transparent** : fenêtre tkinter click-through via Win32 `WS_EX_TRANSPARENT`
- **Feedback visuel** : anneau rétractable lors d'un appui, bip sonore au clic confirmé

---

## Démarrage rapide

### Prérequis

- Windows 11 + Docker Desktop (WSL2 activé)
- GPU NVIDIA (recommandé — RTX 3080+ pour les gros modèles)
- [Ollama](https://ollama.ai/) installé nativement sur Windows
- Python 3.12+

### 1. Cloner et configurer

```bash
git clone https://github.com/spp4tme/self-hosted-ai-stack
cd self-hosted-ai-stack
cp .env.example .env
# Édite .env avec tes valeurs (GitHub token, webhook secret, etc.)
```

### 2. Télécharger les modèles Ollama

```bash
ollama pull mistral:7b
ollama pull deepseek-r1:14b
ollama pull qwen2.5-coder:7b
ollama pull llava:13b
ollama pull moondream
ollama pull nomic-embed-text
```

### 3. Démarrer la stack

```bash
# Stack principale (12 services)
docker-compose up -d

# Services additionnels (agents, sandbox, code reviewer, self-heal)
docker-compose -f docker-compose.additions.yml up -d
```

### 4. Installer Jarvis CLI

```bash
pip install -e .
jarvis   # REPL interactif
```

### 5. Accéder aux interfaces

| Interface | URL |
|-----------|-----|
| Chat principal | http://localhost:8080 |
| LiteLLM API | http://localhost:4000 |
| n8n workflows | http://localhost:5678 |
| Langfuse tracing | http://localhost:3000 |
| Grafana dashboards | http://localhost:3001 |
| Authentik SSO | http://localhost:9000 |

---

## Configuration

### `.env`

```env
# LiteLLM
LITELLM_API_KEY=sk-local

# GitHub Code Reviewer
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
GITHUB_REPO=owner/repo
GITHUB_WEBHOOK_SECRET=mon_secret_webhook

# Mémoire
QDRANT_URL=http://localhost:6333
EMBED_MODEL=nomic-embed-text

# Modèles par défaut
DEFAULT_MODEL=mistral
OLLAMA_URL=http://localhost:11434
```

### Ajouter un modèle à LiteLLM (`litellm/config.yaml`)

```yaml
model_list:
  - model_name: mon-modele
    litellm_params:
      model: ollama/mon-modele
      api_base: http://localhost:11434
```

---

## API Reference

### Agents API `:8100`

| Méthode | Route | Body | Réponse |
|---------|-------|------|---------|
| GET | `/health` | — | `{"status": "ok"}` |
| POST | `/run` | `{"agent": str, "task": str}` | `{"result": str}` |

### Sandbox API `:8101`

| Méthode | Route | Body | Réponse |
|---------|-------|------|---------|
| GET | `/health` | — | `{"status": "ok"}` |
| POST | `/execute` | `{"code": str, "packages": list, "timeout": int}` | `{"success": bool, "stdout": str, "stderr": str, "duration_s": float, "blocked": list}` |

### Code Reviewer `:8102`

| Méthode | Route | Description |
|---------|-------|-------------|
| POST | `/webhook` | GitHub PR webhook (HMAC-SHA256 vérifié) |
| GET | `/health` | `{"status": "ok"}` |

### Self-Heal `:9099`

| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/health` | État de santé de tous les services |
| GET | `/metrics` | Métriques Prometheus |

---

## Tests

```bash
# Tous les tests (27 tests, asyncio_mode=auto)
pytest tests/ -v

# Par module
pytest tests/test_memory.py -v
pytest tests/test_vision.py -v
pytest tests/test_sandbox.py -v
pytest tests/test_constitutional.py -v
pytest tests/test_ensemble.py -v
pytest tests/test_self_heal.py -v

# Test sandbox live (Docker requis)
python tests/run_sandbox.py
```

---

## Structure du projet

```
self-hosted-ai-stack/
│
├── docker-compose.yaml            # Stack principale (12 services)
├── docker-compose.additions.yml   # Services IA additionnels (4 services)
├── pyproject.toml                 # Package jarvis-cli installable via pip
├── pytest.ini                     # Config tests (asyncio_mode=auto)
├── install.sh                     # One-liner d'installation multi-machine
├── .env.example                   # Template variables d'environnement
│
├── agents/                        # Agents IA
│   ├── crew.py                    # CrewAI 5 agents + FastAPI :8100
│   ├── constitutional.py          # Pipeline IA constitutionnelle (3 étapes)
│   ├── ensemble.py                # Vote majoritaire multi-modèles
│   └── code_reviewer.py           # Webhook GitHub PR review :8102
│
├── memory/
│   └── store.py                   # MemoryStore — Mem0 + Qdrant
│
├── vision/
│   └── analyzer.py                # VisionAnalyzer — LLaVA + Moondream
│
├── sandbox/
│   ├── executor.py                # Exécution code isolée Docker
│   └── api.py                     # FastAPI :8101
│
├── devops/
│   └── self_heal.py               # Monitoring + auto-restart + Prometheus :9099
│
├── finetune/
│   ├── run_finetune.py            # Fine-tuning LoRA Unsloth
│   ├── prepare_dataset.py         # Conversion conversations → Alpaca
│   └── eval.py                    # Évaluation du modèle fine-tuné
│
├── computer_use/
│   └── agent.py                   # Boucle vision → action (screenshot + pyautogui)
│
├── jarvis/                        # Contrôle par gestes (webcam)
│   ├── desktop.py                 # Détection gestes MediaPipe + overlay AR
│   ├── launch.ps1                 # Script de lancement Windows
│   └── models/
│       └── hand_landmarker.task   # Modèle MediaPipe (7.5 MB)
│
├── jarvis_cli/                    # CLI assistant terminal
│   ├── __main__.py                # Entry point (jarvis / python -m jarvis_cli)
│   ├── agent.py                   # Boucle REPL + tool calling (max 12 rounds)
│   ├── tools.py                   # 9 outils (bash, fichiers, web, mémoire)
│   ├── config.py                  # ~/.jarvis/config.json
│   └── display.py                 # Rich panels, markdown, spinners
│
├── litellm/
│   └── config.yaml                # Proxy LiteLLM — tous les modèles Ollama
│
├── grafana/                       # Dashboards Grafana provisionnés
├── prometheus/                    # Config Prometheus
├── n8n/                           # Workflows n8n exportés
├── caddy/                         # Config reverse proxy Caddy
├── dashy/                         # Dashboard unifié (toutes les apps)
├── scripts/                       # Scripts utilitaires (start, stop, restart)
└── tests/                         # Tests pytest (27 tests)
```

---

---

## Traefik — Reverse Proxy

Traefik remplace Caddy comme reverse proxy. Il découvre automatiquement les services via les labels Docker — aucune config manuelle à chaque ajout de service.

### Dashboard

```
http://localhost:8081    # Direct
https://traefik.local    # Via Traefik lui-même
```

### Ajouter un nouveau service

Il suffit d'ajouter des labels Docker au service :

```yaml
  mon-service:
    image: mon-image:latest
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.mon-service.rule=Host(`mon-service.local`)"
      - "traefik.http.routers.mon-service.entrypoints=websecure"
      - "traefik.http.routers.mon-service.tls=true"
      - "traefik.http.services.mon-service.loadbalancer.server.port=PORT_INTERNE"
      - "traefik.http.routers.mon-service.middlewares=allow-iframe@file"
```

Puis ajouter `127.0.0.1 mon-service.local` au fichier hosts.

### Rollback vers Caddy

```bash
# Dans docker-compose.yaml :
# 1. Commenter le service traefik
# 2. Décommenter le service caddy (commenté en bas du fichier)
docker-compose up -d caddy
docker-compose stop traefik
```

### Regénérer les certificats mkcert (nouveaux domaines)

```powershell
# En administrateur, dans le dossier certs/
mkcert -cert-file cert.pem -key-file key.pem `
  webui.local litellm.local n8n.local searxng.local `
  qdrant.local langfuse.local grafana.local prometheus.local `
  authentik.local comfyui.local whisper.local dashboard.local `
  traefik.local crewai.local gitops.local localhost 127.0.0.1
```

### Ajouter les nouveaux domaines au hosts file (en administrateur)

```powershell
# PowerShell en administrateur
$hosts = "C:\Windows\System32\drivers\etc\hosts"
@("127.0.0.1 traefik.local","127.0.0.1 crewai.local","127.0.0.1 gitops.local","127.0.0.1 comfyui.local","127.0.0.1 whisper.local") |
  ForEach-Object { Add-Content $hosts "`n$_" }
```

### Middlewares disponibles

| Middleware | Effet |
|-----------|-------|
| `allow-iframe@file` | Supprime X-Frame-Options et CSP (iframes Dashy) |
| `rate-limit@file` | Limite à 200 req/s (burst 100) |
| `secure-headers@file` | HSTS + SSL redirect |
| `authentik-sso@file` | Forward auth SSO Authentik |

---

## CI/CD GitHub Actions

Deux workflows automatisés à chaque push sur `main`.

### `ci.yml` — Tests et build

| Job | Description |
|-----|-------------|
| `validate` | Valide `docker-compose.yaml`, configs Traefik, lint YAML |
| `test-python` | `ruff` lint + `pytest` (27 tests) |
| `build-images` | Build images agents, sandbox, crewai-ui, gitops |
| `deploy-status` | Confirme que tout est prêt au déploiement |

### `security.yml` — Scan quotidien (3h UTC)

| Job | Description |
|-----|-------------|
| `trivy-fs` | Scan filesystem (secrets, configs) → GitHub Security tab |
| `trivy-images` | Scan images Docker (Traefik, LiteLLM, Open WebUI, Qdrant) |
| `check-secrets` | Trufflehog — détection secrets hardcodés |

### Ajouter un job CI

```yaml
# Dans .github/workflows/ci.yml
  mon-job:
    runs-on: ubuntu-latest
    needs: validate
    steps:
      - uses: actions/checkout@v4
      - name: Mon test
        run: mon-commande
```

---

## GitOps Webhook

Service Python FastAPI qui écoute les push GitHub et redéploie automatiquement la stack. C'est l'équivalent Docker Compose d'ArgoCD (ArgoCD est Kubernetes-natif — fichiers dans `argocd/` pour future migration K8s).

### Fonctionnement

```
Push GitHub main → Webhook → git pull → docker-compose up -d --build
```

### Setup GitHub Webhook

```
URL     : https://gitops.local/webhook/github (ou http://IP:9100/webhook/github)
Secret  : valeur de GITHUB_WEBHOOK_SECRET dans .env
Content : application/json
Events  : Just the push event
```

### Dashboard déploiements

```
http://localhost:9100         # Dashboard web
http://localhost:9100/docs    # API Swagger
GET /deployments              # Liste des 20 derniers déploiements
GET /deployments/{id}         # Détails d'un déploiement (logs inclus)
```

### Fichiers ArgoCD (future migration Kubernetes)

```
argocd/
├── applications/stack-ia.yaml    # Application ArgoCD avec sync auto
└── install.sh                    # Script d'installation ArgoCD CLI
```

Pour migrer vers K8s (k3s, minikube) : `bash argocd/install.sh`

---

## Accès distant via Tailscale

La stack est accessible depuis n'importe quelle machine via Tailscale :

```bash
# Sur la machine distante
pip install -e git+https://github.com/spp4tme/self-hosted-ai-stack#egg=jarvis-cli
jarvis --url http://<tailscale-ip>:4000
```

LiteLLM sur `:4000` expose une API **100% compatible OpenAI** — toute app supportant l'API OpenAI peut pointer dessus directement.

---

## Licence

Usage personnel — tous droits réservés.
