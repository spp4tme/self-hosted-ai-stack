"""Entry point: python -m jarvis_cli  or  jarvis  (via pyproject.toml)."""

from __future__ import annotations

import argparse
import asyncio
import sys

from . import config as cfg_module
from . import display


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="jarvis",
        description="Jarvis CLI — assistant IA dans le terminal",
    )
    p.add_argument("--model",   "-m", help="Modèle LLM (ex: mistral, deepseek-coder)")
    p.add_argument("--url",     "-u", help="URL LiteLLM (ex: http://mon-pc:4000)")
    p.add_argument("--key",     "-k", help="API key LiteLLM")
    p.add_argument("--version", "-v", action="store_true", help="Afficher la version")
    p.add_argument(
        "prompt", nargs="?",
        help="Exécute un prompt en one-shot (pas de REPL interactif)",
    )
    return p


def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    if args.version:
        from . import __version__
        print(f"Jarvis CLI v{__version__}")
        sys.exit(0)

    cfg = cfg_module.load()

    # Overrides CLI > config
    if args.model:
        cfg["model"] = args.model
    if args.url:
        cfg["litellm_url"] = args.url
    if args.key:
        cfg["litellm_key"] = args.key

    if args.prompt:
        # One-shot mode
        from .agent import JarvisAgent
        agent = JarvisAgent(cfg)

        async def _one_shot() -> None:
            display.print_info(f"[{cfg['model']}] {args.prompt}")
            await agent.step(args.prompt)

        asyncio.run(_one_shot())
    else:
        # Interactive REPL
        from .agent import run_repl
        try:
            asyncio.run(run_repl(cfg))
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
