#!/usr/bin/env bash
# Installation de Jarvis CLI — fonctionne sur n'importe quelle machine
# Usage:  curl -fsSL https://<ton-domaine>/install.sh | bash
#     ou: bash install.sh

set -euo pipefail

REPO_URL="${JARVIS_REPO:-}"
LITELLM_URL="${LITELLM_URL:-http://localhost:4000}"
MODEL="${JARVIS_MODEL:-mistral}"

echo "=== Jarvis CLI Installer ==="

# Vérifie Python 3.11+
if ! command -v python3 &>/dev/null; then
    echo "Python3 requis. Installe-le et relance."
    exit 1
fi

PY_VER=$(python3 -c "import sys; print(sys.version_info >= (3,11))")
if [ "$PY_VER" != "True" ]; then
    echo "Python 3.11+ requis (version actuelle trop ancienne)."
    exit 1
fi

# Installation depuis le répertoire courant (si pyproject.toml présent)
if [ -f "pyproject.toml" ]; then
    echo "→ Installation locale depuis $(pwd)"
    pip install -e . --quiet
else
    # Installation depuis pip (quand le package sera publié)
    echo "→ Installation depuis PyPI"
    pip install jarvis-cli --quiet
fi

# Config initiale
JARVIS_DIR="$HOME/.jarvis"
JARVIS_CFG="$JARVIS_DIR/config.json"
mkdir -p "$JARVIS_DIR"

if [ ! -f "$JARVIS_CFG" ]; then
    cat > "$JARVIS_CFG" <<JSON
{
  "litellm_url": "$LITELLM_URL",
  "litellm_key": "sk-local",
  "model": "$MODEL",
  "qdrant_url": "http://localhost:6333",
  "ollama_url": "http://localhost:11434",
  "embed_model": "nomic-embed-text",
  "searxng_url": "http://localhost:8888",
  "max_tokens": 4096,
  "temperature": 0.7,
  "memory_limit": 5
}
JSON
    echo "→ Config créée: $JARVIS_CFG"
    echo ""
    echo "  Edite $JARVIS_CFG pour changer l'URL LiteLLM si tu es sur une autre machine."
else
    echo "→ Config existante conservée: $JARVIS_CFG"
fi

echo ""
echo "=== Installation terminée ==="
echo "Lance 'jarvis' pour démarrer."
echo ""
echo "Exemples :"
echo "  jarvis                          # REPL interactif"
echo "  jarvis 'liste les fichiers py'  # one-shot"
echo "  jarvis --url http://192.168.x.x:4000 --model deepseek-coder"
