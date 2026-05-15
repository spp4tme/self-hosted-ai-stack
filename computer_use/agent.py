"""
Computer Use Agent — Vision (Moondream) + pyautogui.
Boucle : screenshot → analyse → action → répète.

Usage: python computer_use/agent.py "ouvre Firefox sur localhost:8080"
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import mss
import mss.tools
import pyautogui
from dotenv import load_dotenv

from vision.analyzer import VisionAnalyzer

load_dotenv()

pyautogui.FAILSAFE    = True      # coin haut-gauche = stop d'urgence
pyautogui.PAUSE       = 0.5       # 500ms entre chaque action

log = logging.getLogger("computer_use")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

MAX_ITER    = 20
TIMEOUT_SEC = 300
SCREENSHOT_DIR = Path("computer_use/screenshots")
LOG_DIR        = Path("computer_use/logs")


@dataclass
class Action:
    type: str            # click | type | scroll | done | error
    args: dict[str, Any] = field(default_factory=dict)
    raw:  str = ""


def parse_action(raw: str) -> Action:
    """Parse la réponse du modèle en action structurée."""
    raw = raw.strip()

    # click(x, y)
    m = re.search(r"click\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)", raw, re.I)
    if m:
        return Action("click", {"x": int(m.group(1)), "y": int(m.group(2))}, raw)

    # type("texte") ou type('texte')
    m = re.search(r'type\s*\(["\'](.+?)["\']\)', raw, re.I | re.DOTALL)
    if m:
        return Action("type", {"text": m.group(1)}, raw)

    # scroll(dy)
    m = re.search(r"scroll\s*\(\s*(-?\d+)\s*\)", raw, re.I)
    if m:
        return Action("scroll", {"dy": int(m.group(1))}, raw)

    # done
    if re.search(r"\bdone\b", raw, re.I):
        return Action("done", {}, raw)

    return Action("error", {"raw": raw}, raw)


def take_screenshot(idx: int) -> Path:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOT_DIR / f"step_{idx:03d}.png"
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # moniteur principal
        sct_img = sct.grab(monitor)
        mss.tools.to_png(sct_img.rgb, sct_img.size, output=str(path))
    return path


def execute_action(action: Action) -> str:
    """Exécute l'action physiquement et retourne un log."""
    if action.type == "click":
        x, y = action.args["x"], action.args["y"]
        pyautogui.click(x, y)
        return f"click({x}, {y})"

    if action.type == "type":
        text = action.args["text"]
        pyautogui.write(text, interval=0.05)
        return f'type("{text[:30]}{"..." if len(text) > 30 else ""}")'

    if action.type == "scroll":
        dy = action.args["dy"]
        pyautogui.scroll(dy)
        return f"scroll({dy})"

    if action.type == "done":
        return "done"

    return f"error: {action.args}"


async def run(task: str, max_iter: int = MAX_ITER) -> list[dict[str, Any]]:
    """Boucle principale du computer use agent."""
    analyzer = VisionAnalyzer()
    history: list[dict[str, Any]] = []
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"session_{int(time.time())}.jsonl"

    start = time.time()
    log.info(f"[CU] Tâche : {task}")
    log.info(f"[CU] Failsafe : coin haut-gauche pour arrêter d'urgence")

    for step in range(max_iter):
        if time.time() - start > TIMEOUT_SEC:
            log.warning("[CU] Timeout atteint")
            break

        # 1. Screenshot
        img_path = take_screenshot(step)
        log.info(f"[CU] Étape {step+1} — screenshot {img_path}")

        # 2. Analyse
        try:
            raw = await analyzer.analyze_for_action(img_path, task)
        except Exception as e:
            log.error(f"[CU] Erreur vision: {e}")
            break

        log.info(f"[CU] Modèle répond: {raw}")

        # 3. Parse
        action = parse_action(raw)

        # 4. Log
        entry = {
            "step": step,
            "screenshot": str(img_path),
            "model_output": raw,
            "action": action.type,
            "args": action.args,
        }

        # 5. Execute
        if action.type == "done":
            log.info("[CU] Tâche terminée ✓")
            entry["result"] = "done"
            history.append(entry)
            break

        if action.type == "error":
            log.warning(f"[CU] Action non parsée: {raw}")
            history.append(entry)
            continue

        try:
            result = execute_action(action)
            entry["result"] = result
            log.info(f"[CU] Exécuté: {result}")
        except pyautogui.FailSafeException:
            log.critical("[CU] FAILSAFE ACTIVÉ — arrêt d'urgence")
            break
        except Exception as e:
            log.error(f"[CU] Erreur exécution: {e}")
            entry["result"] = f"error: {e}"

        history.append(entry)

        # Log JSON
        with open(log_file, "a", encoding="utf-8") as f:
            import json
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        await asyncio.sleep(0.5)

    log.info(f"[CU] Session terminée. {len(history)} actions. Log: {log_file}")
    return history


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python computer_use/agent.py \"<tâche>\"")
        sys.exit(1)
    task = " ".join(sys.argv[1:])
    asyncio.run(run(task))
