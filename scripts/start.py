import subprocess
import os
import time

projet = os.path.expanduser("~/Documents/mon-ia")

print("🚀 Démarrage de Docker Desktop...")
subprocess.Popen(["C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe"])

print("⏳ Attente que Docker soit prêt...")
while True:
    result = subprocess.run(
        ["docker", "info"],
        capture_output=True
    )
    if result.returncode == 0:
        break
    time.sleep(3)
    print("   ...toujours en attente")

print("✅ Docker prêt ! Démarrage du stack...")
subprocess.run(["docker", "compose", "up", "-d"], cwd=projet)
time.sleep(5)

print("🚀 Vérification d'Ollama...")
result = subprocess.run(["ollama", "list"], capture_output=True)
if result.returncode != 0:
    print("   Démarrage d'Ollama...")
    subprocess.Popen(["ollama", "serve"])
    time.sleep(3)
else:
    print("   Ollama déjà actif ✅")

print("🔒 Vérification de Caddy (HTTPS)...")
result = subprocess.run(
    ["docker", "inspect", "--format", "{{.State.Running}}", "caddy"],
    capture_output=True,
    text=True
)
if result.stdout.strip() == "true":
    print("   Caddy actif ✅")
else:
    print("   ⚠️  Caddy ne tourne pas — vérifie le Caddyfile")

print("\n✅ Stack IA démarrée !")
print("─" * 45)
print("   Open WebUI  → https://webui.local")
print("   LiteLLM     → https://litellm.local")
print("   SearXNG     → https://searxng.local")
print("   Qdrant      → https://qdrant.local")
print("   n8n         → https://n8n.local")
print("   Langfuse    → https://langfuse.local")
print("   Grafana     → https://grafana.local")
print("   Prometheus  → https://prometheus.local")
print("   Authentik   → https://authentik.local")
print("─" * 45)
print("   (accès local HTTP toujours disponible)")
print("   Open WebUI  → http://localhost:8080")
print("   LiteLLM     → http://localhost:4000")
print("   SearXNG     → http://localhost:8888")
print("   Qdrant      → http://localhost:6333")
print("   n8n         → http://localhost:5678")
print("   Langfuse    → http://localhost:3000")
print("   Grafana     → http://localhost:3001")
print("   Prometheus  → http://localhost:9090")
print("   Authentik   → http://localhost:9000")
print("─" * 45)