import subprocess
import os

projet = os.path.expanduser("~/Documents/mon-ia")

print("🛑 Arrêt du stack IA...")
subprocess.run(["docker", "compose", "down"], cwd=projet)
print("✅ Tout est éteint proprement.")