"""Main agent loop — reads input, calls LLM with tools, executes tools, loops."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from openai import AsyncOpenAI

from . import config as cfg_module
from . import display
from .tools import TOOL_SCHEMAS, dispatch

SYSTEM_PROMPT = """Tu es Jarvis, un assistant IA expert en développement logiciel, DevOps, et systèmes.
Tu es dans un terminal interactif. Tu peux utiliser des outils pour lire/écrire des fichiers, exécuter des commandes, rechercher sur le web et accéder à ta mémoire long terme.

RÈGLES STRICTES :
- N'utilise les outils QUE si la tâche le requiert vraiment (fichiers, commandes, recherche).
- Pour une simple conversation ou question générale : réponds DIRECTEMENT en texte, sans aucun outil.
- Ne mets JAMAIS en mémoire les messages de conversation banale (salutations, etc.).
- Ne confirme jamais une action avec bash echo — exécute directement ou réponds en texte.
- Une fois la tâche accomplie, réponds en texte et ARRÊTE de faire des appels d'outils.
- Réponds toujours en français sauf si l'utilisateur parle anglais.
- Sois concis dans tes explications, verbeux dans ton code.
- Si une commande bash échoue, analyse l'erreur et propose une correction."""


class JarvisAgent:
    def __init__(self, cfg: dict[str, Any]) -> None:
        self.cfg = cfg
        self.history: list[dict[str, Any]] = []
        self.client = AsyncOpenAI(
            base_url=cfg["litellm_url"] + "/v1",
            api_key=cfg["litellm_key"],
        )
        self.model = cfg["model"]

    def reset(self) -> None:
        self.history = []

    async def _call_llm(self) -> Any:
        return await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + self.history,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            max_tokens=self.cfg.get("max_tokens", 4096),
            temperature=self.cfg.get("temperature", 0.7),
        )

    async def step(self, user_input: str) -> None:
        self.history.append({"role": "user", "content": user_input})
        _tool_rounds = 0

        while True:
            if _tool_rounds >= 12:
                display.print_error("Limite d'appels d'outils atteinte (12). Arrêt de la boucle.")
                break
            with display.spinner("Jarvis réfléchit..."):
                try:
                    response = await self._call_llm()
                except Exception as e:
                    display.print_error(f"LLM inaccessible: {e}")
                    self.history.pop()
                    return

            msg = response.choices[0].message

            # ── Réponse texte ─────────────────────────────────────────────────
            if msg.content:
                display.print_assistant(msg.content)

            # ── Appels d'outils ───────────────────────────────────────────────
            tool_calls = msg.tool_calls or []
            if not tool_calls:
                self.history.append({"role": "assistant", "content": msg.content or ""})
                break

            # Ajoute l'assistant message avec tool_calls
            self.history.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in tool_calls
                ],
            })

            _tool_rounds += 1
            # Exécute chaque tool call
            for tc in tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                display.print_tool_call(name, args)

                result, success = await dispatch(name, args, self.cfg)
                display.print_tool_result(name, result, success)

                self.history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })


async def run_repl(cfg: dict[str, Any]) -> None:
    agent = JarvisAgent(cfg)
    display.print_welcome(cfg["model"], cfg["litellm_url"])

    while True:
        try:
            user_input = display.console.input("[bold cyan]Vous >[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            display.print_info("\nAu revoir.")
            break

        if not user_input:
            continue

        # ── Commandes spéciales ───────────────────────────────────────────────
        if user_input.lower() in ("/quit", "/exit", "quit", "exit"):
            display.print_info("Au revoir.")
            break

        elif user_input.lower() == "/help":
            display.print_help()

        elif user_input.lower() == "/clear":
            agent.reset()
            display.print_info("Historique effacé.")

        elif user_input.lower() == "/config":
            display.console.print_json(json.dumps(cfg, indent=2, ensure_ascii=False))

        elif user_input.lower().startswith("/model "):
            new_model = user_input[7:].strip()
            agent.model = new_model
            cfg["model"] = new_model
            cfg_module.save(cfg)
            display.print_info(f"Modèle changé: {new_model}")

        elif user_input.lower() == "/memory":
            result, _ = await dispatch("memory_search", {"query": "tout", "limit": 10}, cfg)
            display.print_tool_result("memory", result)

        elif user_input.lower().startswith("/remember "):
            text = user_input[10:].strip()
            result, success = await dispatch("memory_add", {"text": text}, cfg)
            display.print_tool_result("memory_add", result, success)

        else:
            await agent.step(user_input)
