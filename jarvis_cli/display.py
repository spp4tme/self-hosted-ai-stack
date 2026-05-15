"""Rich terminal rendering — panels, markdown, tool call display."""

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich import box

console = Console()


def print_welcome(model: str, url: str) -> None:
    console.print(Panel(
        f"[bold cyan]Jarvis CLI[/bold cyan]  [dim]powered by {model}[/dim]\n"
        f"[dim]{url}[/dim]\n\n"
        "[dim]Tape [bold]/help[/bold] pour les commandes, [bold]/quit[/bold] pour quitter.[/dim]",
        box=box.DOUBLE_EDGE,
        border_style="cyan",
        padding=(0, 2),
    ))


def print_help() -> None:
    console.print(Panel(
        "[bold]Commandes spéciales :[/bold]\n"
        "  [cyan]/help[/cyan]            Afficher cette aide\n"
        "  [cyan]/quit[/cyan] [dim]ou /exit[/dim]  Quitter\n"
        "  [cyan]/clear[/cyan]           Effacer l'historique de conversation\n"
        "  [cyan]/config[/cyan]          Voir la configuration actuelle\n"
        "  [cyan]/model <nom>[/cyan]     Changer de modèle\n"
        "  [cyan]/memory[/cyan]          Voir les souvenirs sauvegardés\n"
        "  [cyan]/remember <texte>[/cyan] Sauvegarder un souvenir manuellement\n\n"
        "[bold]Outils disponibles :[/bold]\n"
        "  bash · read_file · write_file · edit_file\n"
        "  glob · grep · web_search · memory_search · memory_add",
        title="Aide",
        border_style="green",
    ))


def print_assistant(content: str) -> None:
    if "```" in content:
        console.print(Panel(Markdown(content), border_style="blue", padding=(0, 1)))
    else:
        console.print(Panel(content, border_style="blue", padding=(0, 1)))


def print_tool_call(name: str, args: dict) -> None:
    import json
    args_str = json.dumps(args, ensure_ascii=False, indent=2)
    console.print(Panel(
        Syntax(args_str, "json", theme="monokai", word_wrap=True),
        title=f"[yellow]Tool: {name}[/yellow]",
        border_style="yellow",
        padding=(0, 1),
    ))


def print_tool_result(name: str, result: str, success: bool = True) -> None:
    color  = "green" if success else "red"
    prefix = "OK" if success else "ERR"
    lines  = result.strip()
    if len(lines) > 2000:
        lines = lines[:1980] + "\n[...tronqué...]"
    console.print(Panel(
        lines or "[dim](vide)[/dim]",
        title=f"[{color}]{prefix}: {name}[/{color}]",
        border_style=color,
        padding=(0, 1),
    ))


def print_error(msg: str) -> None:
    console.print(f"[bold red]Erreur:[/bold red] {msg}")


def print_info(msg: str) -> None:
    console.print(f"[dim cyan]{msg}[/dim cyan]")


def spinner(msg: str):
    """Context manager — returns a Rich Live spinner."""
    from rich.spinner import Spinner
    from rich.live import Live
    return Live(Spinner("dots", text=f"[dim]{msg}[/dim]"), refresh_per_second=12, transient=True)
