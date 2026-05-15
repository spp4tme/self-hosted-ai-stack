import subprocess
import os
import time

projet = os.path.expanduser("~/Documents/mon-ia")

print("🔄 Redémarrage du stack IA...")
subprocess.run(["docker", "compose", "down"], cwd=projet)
time.sleep(3)
subprocess.run(["docker", "compose", "up", "-d"], cwd=projet)
print("✅ Stack redémarré !")