#!/usr/bin/env bash
# Installation ArgoCD CLI + connexion au serveur local
# NOTE: ArgoCD nécessite Kubernetes. Pour Docker Compose, voir gitops/webhook.py

set -euo pipefail

ARGOCD_SERVER="${ARGOCD_SERVER:-argocd.local}"
ARGOCD_PORT="${ARGOCD_PORT:-8082}"

echo "=== Installation ArgoCD CLI ==="

# Détecte l'OS
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)
[ "$ARCH" = "x86_64" ] && ARCH="amd64"
[ "$ARCH" = "aarch64" ] && ARCH="arm64"

ARGOCD_VERSION=$(curl -s https://api.github.com/repos/argoproj/argo-cd/releases/latest | grep '"tag_name"' | cut -d'"' -f4)
curl -sSL -o /tmp/argocd \
  "https://github.com/argoproj/argo-cd/releases/download/${ARGOCD_VERSION}/argocd-${OS}-${ARCH}"
chmod +x /tmp/argocd
sudo mv /tmp/argocd /usr/local/bin/argocd

echo "→ ArgoCD CLI ${ARGOCD_VERSION} installé"

# Connexion et déploiement de l'app
echo "=== Connexion au serveur ArgoCD ==="
INITIAL_PWD=$(docker exec argocd-server argocd admin initial-password 2>/dev/null | head -1 || echo "admin")
argocd login "${ARGOCD_SERVER}:${ARGOCD_PORT}" \
  --username admin \
  --password "${INITIAL_PWD}" \
  --insecure

echo "=== Création de l'application stack-ia ==="
argocd app create jarvis-ai-stack \
  --repo https://github.com/spp4tme/self-hosted-ai-stack \
  --path . \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace jarvis \
  --sync-policy automated \
  --auto-prune \
  --self-heal \
  --upsert || true

argocd app sync jarvis-ai-stack || true

echo ""
echo "=== ArgoCD configuré ==="
echo "Dashboard: https://${ARGOCD_SERVER}:${ARGOCD_PORT}"
echo "Statut: argocd app get jarvis-ai-stack"
