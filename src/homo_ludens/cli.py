"""CLI interface for Homo Ludens."""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from homo_ludens.recommender import Recommender
from homo_ludens.steam import SteamAPIError, SteamClient
from homo_ludens.storage import Storage

app = typer.Typer(
    name="homo-ludens",
    help="Your personal AI game companion",
    no_args_is_help=True,
)
console = Console()


@app.command()
def sync():
    """Sync your Steam library."""
    storage = Storage()
    profile = storage.load_profile()

    console.print("[bold blue]Syncing Steam library...[/bold blue]")

    try:
        client = SteamClient()
        games = client.get_owned_games()

        profile.games = games
        profile.steam_id = client.steam_id
        storage.save_profile(profile)

        console.print(
            f"[bold green]Success![/bold green] Synced {len(games)} games from Steam."
        )

        # Show top 5 by playtime
        top_games = sorted(games, key=lambda g: g.playtime_minutes, reverse=True)[:5]
        if top_games:
            console.print("\n[bold]Your most played games:[/bold]")
            for i, game in enumerate(top_games, 1):
                hours = game.playtime_minutes // 60
                console.print(f"  {i}. {game.name} ({hours}h)")

    except SteamAPIError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@app.command()
def chat():
    """Start a conversation with your game companion."""
    storage = Storage()
    profile = storage.load_profile()
    history = storage.load_conversation()

    if not profile.games:
        console.print(
            "[yellow]No games in your library yet. Run 'homo-ludens sync' first, "
            "or I can still chat without your library data.[/yellow]\n"
        )

    try:
        recommender = Recommender()
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)

    console.print(
        Panel(
            "[bold]Homo Ludens[/bold] - Your AI Game Companion\n"
            "Type 'quit' or 'exit' to end the conversation.\n"
            "Type 'clear' to clear conversation history.",
            style="blue",
        )
    )

    # Initial greeting if no history
    if not history.messages:
        greeting = (
            "Hey! I'm your game companion. I can help you pick something to play "
            "based on your mood, available time, or whatever you're in the mood for. "
            "What's on your mind?"
        )
        console.print(f"\n[bold cyan]Companion:[/bold cyan] {greeting}\n")
        history.add_message("assistant", greeting)
        storage.save_conversation(history)

    while True:
        try:
            user_input = Prompt.ask("[bold green]You[/bold green]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not user_input.strip():
            continue

        if user_input.lower() in ("quit", "exit"):
            console.print("[dim]Goodbye! Happy gaming![/dim]")
            break

        if user_input.lower() == "clear":
            storage.clear_conversation()
            history = storage.load_conversation()
            console.print("[dim]Conversation cleared.[/dim]\n")
            continue

        # Get response from LLM
        with console.status("[dim]Thinking...[/dim]"):
            try:
                response = recommender.chat(user_input, profile, history)
            except Exception as e:
                console.print(f"[bold red]Error:[/bold red] {e}")
                continue

        # Update history
        history.add_message("user", user_input)
        history.add_message("assistant", response)
        storage.save_conversation(history)

        console.print(f"\n[bold cyan]Companion:[/bold cyan] {response}\n")


@app.command()
def status():
    """Show current status and library info."""
    storage = Storage()
    profile = storage.load_profile()

    console.print(Panel("[bold]Homo Ludens Status[/bold]", style="blue"))

    if profile.steam_id:
        console.print(f"Steam ID: {profile.steam_id}")
    else:
        console.print("Steam: [yellow]Not connected[/yellow]")

    console.print(f"Games in library: {len(profile.games)}")

    if profile.games:
        total_playtime = sum(g.playtime_minutes for g in profile.games)
        console.print(f"Total playtime: {total_playtime // 60} hours")

        played = len([g for g in profile.games if g.playtime_minutes > 0])
        console.print(f"Games played: {played}/{len(profile.games)}")

    history = storage.load_conversation()
    console.print(f"Conversation messages: {len(history.messages)}")


@app.command()
def clear():
    """Clear all stored data."""
    if typer.confirm("This will delete your profile and conversation history. Continue?"):
        storage = Storage()
        storage.clear_all()
        console.print("[green]All data cleared.[/green]")


def main():
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
