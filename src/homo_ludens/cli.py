"""CLI interface for Homo Ludens."""

from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from homo_ludens.recommender import Recommender
from homo_ludens.steam import SteamAPIError, SteamClient
from homo_ludens.storage import Storage

# Load .env file - try current directory, then home directory
load_dotenv(Path.cwd() / ".env")
load_dotenv(Path.home() / ".homo_ludens" / ".env")

app = typer.Typer(
    name="homo-ludens",
    help="Your personal AI game companion",
    no_args_is_help=True,
)
console = Console()

# Default minimum playtime for achievement fetching (in minutes)
DEFAULT_ACHIEVEMENT_MIN_PLAYTIME = 60


def _refresh_library(console: Console, storage: Storage, min_playtime: int = DEFAULT_ACHIEVEMENT_MIN_PLAYTIME):
    """Refresh Steam library with achievements. Returns updated profile."""
    console.print("[bold blue]Refreshing Steam library...[/bold blue]")
    
    try:
        client = SteamClient()
        games = client.get_owned_games()
        
        # Fetch achievements for played games
        played_games = [g for g in games if g.playtime_minutes >= min_playtime]
        console.print(f"[dim]Fetching achievements for {len(played_games)} games...[/dim]")
        
        with console.status("[dim]Fetching achievements...[/dim]") as status:
            for i, game in enumerate(played_games):
                status.update(f"[dim]{i+1}/{len(played_games)} - {game.name}[/dim]")
                client.enrich_game_with_achievements(game)
        
        profile = storage.load_profile()
        profile.games = games
        profile.steam_id = client.steam_id
        storage.save_profile(profile)
        
        games_with_achievements = [
            g for g in games 
            if g.achievement_stats and g.achievement_stats.total > 0
        ]
        console.print(
            f"[bold green]Done![/bold green] {len(games)} games, "
            f"{len(games_with_achievements)} with achievement data."
        )
        return profile
        
    except SteamAPIError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        return storage.load_profile()


def _show_status(console: Console, profile):
    """Show library status inline."""
    console.print("[bold]Library Status:[/bold]")
    console.print(f"  Games: {len(profile.games)}")
    
    if profile.games:
        total_playtime = sum(g.playtime_minutes for g in profile.games)
        played = len([g for g in profile.games if g.playtime_minutes > 0])
        games_with_ach = len([
            g for g in profile.games 
            if g.achievement_stats and g.achievement_stats.total > 0
        ])
        
        console.print(f"  Playtime: {total_playtime // 60} hours")
        console.print(f"  Played: {played}/{len(profile.games)}")
        console.print(f"  With achievements: {games_with_ach}")


@app.command()
def sync(
    achievements: bool = typer.Option(
        False, "--achievements", "-a", help="Also fetch achievement data (slower)"
    ),
    min_playtime: int = typer.Option(
        60, "--min-playtime", "-m", 
        help="Only fetch achievements for games with at least this many minutes played"
    ),
):
    """Sync your Steam library."""
    storage = Storage()
    profile = storage.load_profile()

    console.print("[bold blue]Syncing Steam library...[/bold blue]")

    try:
        client = SteamClient()
        games = client.get_owned_games()

        console.print(
            f"[bold green]Success![/bold green] Synced {len(games)} games from Steam."
        )

        # Fetch achievements if requested
        if achievements:
            played_games = [g for g in games if g.playtime_minutes >= min_playtime]
            console.print(
                f"\n[bold blue]Fetching achievements for {len(played_games)} games "
                f"(with >= {min_playtime} min playtime)...[/bold blue]"
            )
            
            with console.status("[dim]Fetching achievements...[/dim]") as status:
                for i, game in enumerate(played_games):
                    status.update(f"[dim]Fetching achievements... {i+1}/{len(played_games)} - {game.name}[/dim]")
                    client.enrich_game_with_achievements(game)
            
            # Count games with achievements
            games_with_achievements = [
                g for g in games 
                if g.achievement_stats and g.achievement_stats.total > 0
            ]
            console.print(
                f"[green]Fetched achievements for {len(games_with_achievements)} games.[/green]"
            )

        profile.games = games
        profile.steam_id = client.steam_id
        storage.save_profile(profile)

        # Show top 5 by playtime
        top_games = sorted(games, key=lambda g: g.playtime_minutes, reverse=True)[:5]
        if top_games:
            console.print("\n[bold]Your most played games:[/bold]")
            for i, game in enumerate(top_games, 1):
                hours = game.playtime_minutes // 60
                ach_str = ""
                if game.achievement_stats and game.achievement_stats.total > 0:
                    ach_str = f" - {game.achievement_stats.completion_percent}% achievements"
                console.print(f"  {i}. {game.name} ({hours}h){ach_str}")

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
            "Type 'clear' to clear conversation history.\n"
            "Type '/refresh' to sync latest Steam data.\n"
            "Type '/status' to view library stats.",
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

        if user_input.lower() == "/refresh":
            profile = _refresh_library(console, storage)
            console.print()
            continue

        if user_input.lower() == "/status":
            _show_status(console, profile)
            console.print()
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

        console.print(f"\n[bold cyan]Companion:[/bold cyan]")
        console.print(Markdown(response))
        console.print()


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
