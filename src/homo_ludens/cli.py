"""CLI interface for Homo Ludens."""

import os
import webbrowser
from pathlib import Path

import typer
from dotenv import load_dotenv, set_key
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from homo_ludens.models import Platform
from homo_ludens.recommender import Recommender
from homo_ludens.steam import SteamAPIError, SteamClient
from homo_ludens.psn import PSNAPIError, PSNClient
from homo_ludens.storage import Storage

# Load .env file - try current directory, then home directory
ENV_FILE = Path.home() / ".homo_ludens" / ".env"
load_dotenv(Path.cwd() / ".env")
load_dotenv(ENV_FILE)

app = typer.Typer(
    name="homo-ludens",
    help="Your personal AI game companion",
    no_args_is_help=True,
)
console = Console()

# Default minimum playtime for achievement fetching (in minutes)
DEFAULT_ACHIEVEMENT_MIN_PLAYTIME = 60


def _refresh_library(console: Console, storage: Storage, min_playtime: int = DEFAULT_ACHIEVEMENT_MIN_PLAYTIME):
    """Refresh Steam library with achievements and wishlist. Returns updated profile."""
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
        
        # Fetch wishlist
        console.print("[dim]Fetching wishlist...[/dim]")
        wishlist_items = client.get_wishlist()
        with console.status("[dim]Fetching wishlist details...[/dim]") as status:
            for i, item in enumerate(wishlist_items):
                status.update(f"[dim]{i+1}/{len(wishlist_items)}[/dim]")
                client.enrich_wishlist_item(item)
        
        profile = storage.load_profile()
        profile.games = games
        profile.wishlist = wishlist_items
        profile.steam_id = client.steam_id
        storage.save_profile(profile)
        
        games_with_achievements = [
            g for g in games 
            if g.achievement_stats and g.achievement_stats.total > 0
        ]
        on_sale = [item for item in wishlist_items if item.is_on_sale]
        
        console.print(
            f"[bold green]Done![/bold green] {len(games)} games, "
            f"{len(games_with_achievements)} with achievements, "
            f"{len(wishlist_items)} wishlist items ({len(on_sale)} on sale)."
        )
        return profile
        
    except SteamAPIError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        return storage.load_profile()


def _show_status(console: Console, profile):
    """Show library status inline."""
    console.print("[bold]Library Status:[/bold]")
    
    # Count by platform
    steam_games = [g for g in profile.games if g.platform == Platform.STEAM]
    psn_games = [g for g in profile.games if g.platform == Platform.PLAYSTATION]
    
    console.print(f"  Total games: {len(profile.games)}")
    if steam_games:
        console.print(f"    Steam: {len(steam_games)}")
    if psn_games:
        console.print(f"    PlayStation: {len(psn_games)}")
    
    if profile.games:
        total_playtime = sum(g.playtime_minutes for g in profile.games)
        played = len([g for g in profile.games if g.playtime_minutes > 0])
        games_with_ach = len([
            g for g in profile.games 
            if g.achievement_stats and g.achievement_stats.total > 0
        ])
        
        console.print(f"  Playtime: {total_playtime // 60} hours")
        console.print(f"  Played: {played}/{len(profile.games)}")
        console.print(f"  With achievements/trophies: {games_with_ach}")
    
    if profile.wishlist:
        on_sale = [item for item in profile.wishlist if item.is_on_sale]
        console.print(f"  Wishlist: {len(profile.wishlist)} items ({len(on_sale)} on sale)")


@app.command()
def sync(
    achievements: bool = typer.Option(
        False, "--achievements", "-a", help="Also fetch achievement data (slower)"
    ),
    min_playtime: int = typer.Option(
        60, "--min-playtime", "-m", 
        help="Only fetch achievements for games with at least this many minutes played"
    ),
    wishlist: bool = typer.Option(
        True, "--wishlist/--no-wishlist", "-w", help="Fetch wishlist with prices"
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

        # Fetch wishlist
        wishlist_items = []
        if wishlist:
            console.print("\n[bold blue]Fetching wishlist...[/bold blue]")
            wishlist_items = client.get_wishlist()
            
            if wishlist_items:
                with console.status("[dim]Fetching wishlist details and prices...[/dim]") as status:
                    for i, item in enumerate(wishlist_items):
                        status.update(f"[dim]{i+1}/{len(wishlist_items)} - App {item.app_id}[/dim]")
                        client.enrich_wishlist_item(item)
                
                on_sale = [item for item in wishlist_items if item.is_on_sale]
                console.print(
                    f"[green]Fetched {len(wishlist_items)} wishlist items, "
                    f"{len(on_sale)} on sale![/green]"
                )
                
                # Show items on sale
                if on_sale:
                    console.print("\n[bold yellow]Games on sale:[/bold yellow]")
                    for item in on_sale[:5]:
                        if item.price:  # Type guard
                            console.print(
                                f"  - {item.name}: {item.price.formatted} "
                                f"([green]-{item.price.discount_percent}%[/green])"
                            )
            else:
                console.print("[dim]Wishlist is empty.[/dim]")

        profile.games = games
        profile.wishlist = wishlist_items
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


@app.command("sync-psn")
def sync_psn():
    """Sync your PlayStation library."""
    storage = Storage()
    profile = storage.load_profile()

    # Check if PSN token is configured
    if not os.getenv("PSN_NPSSO_TOKEN"):
        console.print(
            "[yellow]PSN not configured. Run 'homo-ludens config --psn' to set up.[/yellow]"
        )
        raise typer.Exit(1)

    console.print("[bold blue]Syncing PlayStation library...[/bold blue]")

    try:
        client = PSNClient()
        console.print(f"[dim]Logged in as: {client.online_id}[/dim]")
        
        with console.status("[dim]Fetching games and trophies...[/dim]"):
            games = client.get_owned_games()

        console.print(
            f"[bold green]Success![/bold green] Synced {len(games)} games from PlayStation."
        )

        # Merge with existing games (keep Steam games, add PSN games)
        existing_non_psn = [g for g in profile.games if g.platform != Platform.PLAYSTATION]
        profile.games = existing_non_psn + games
        profile.psn_online_id = client.online_id
        storage.save_profile(profile)

        # Show games with highest trophy completion
        games_with_trophies = [
            g for g in games 
            if g.achievement_stats and g.achievement_stats.total > 0
        ]
        games_with_trophies.sort(
            key=lambda g: g.achievement_stats.completion_percent if g.achievement_stats else 0, 
            reverse=True
        )

        if games_with_trophies:
            console.print("\n[bold]Your top trophy games:[/bold]")
            for i, game in enumerate(games_with_trophies[:5], 1):
                if game.achievement_stats:
                    console.print(
                        f"  {i}. {game.name} - {game.achievement_stats.completion_percent}% "
                        f"({game.achievement_stats.unlocked}/{game.achievement_stats.total} trophies)"
                    )

    except PSNAPIError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@app.command()
def config(
    psn: bool = typer.Option(False, "--psn", help="Configure PlayStation Network"),
    steam: bool = typer.Option(False, "--steam", help="Configure Steam"),
    show: bool = typer.Option(False, "--show", help="Show current configuration"),
):
    """Configure platform connections."""
    if show:
        console.print(Panel("[bold]Current Configuration[/bold]", style="blue"))
        
        steam_key = os.getenv("STEAM_API_KEY")
        steam_id = os.getenv("STEAM_ID")
        psn_token = os.getenv("PSN_NPSSO_TOKEN")
        
        if steam_key:
            console.print(f"Steam API Key: [green]configured[/green] ({steam_key[:8]}...)")
        else:
            console.print("Steam API Key: [yellow]not set[/yellow]")
            
        if steam_id:
            console.print(f"Steam ID: [green]{steam_id}[/green]")
        else:
            console.print("Steam ID: [yellow]not set[/yellow]")
            
        if psn_token:
            console.print(f"PSN Token: [green]configured[/green] ({psn_token[:8]}...)")
        else:
            console.print("PSN Token: [yellow]not set[/yellow]")
        return

    if psn:
        console.print(Panel(
            "[bold]PlayStation Network Setup[/bold]\n\n"
            "To connect your PlayStation account:\n\n"
            "[bold]Step 1:[/bold] Log in to PlayStation Store first:\n"
            "         [link]https://store.playstation.com[/link]\n\n"
            "[bold]Step 2:[/bold] After logging in, visit:\n"
            "         [link]https://ca.account.sony.com/api/v1/ssocookie[/link]\n\n"
            "[bold]Step 3:[/bold] Copy the 'npsso' value from the JSON response\n"
            "         (It looks like a long string of letters and numbers)\n\n"
            "[yellow]Note:[/yellow] You MUST be logged in first, otherwise you'll get an error.\n"
            "The token expires after ~60 days.",
            style="blue",
        ))
        
        if typer.confirm("Open PlayStation Store login page first?", default=True):
            webbrowser.open("https://store.playstation.com")
            console.print("\n[dim]Log in to PlayStation Store, then press Enter to continue...[/dim]")
            input()
        
        if typer.confirm("Now open the SSO cookie page?", default=True):
            webbrowser.open("https://ca.account.sony.com/api/v1/ssocookie")
        
        token = Prompt.ask("\nPaste your NPSSO token")
        if token.strip():
            # Ensure directory exists
            ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
            ENV_FILE.touch(exist_ok=True)
            set_key(str(ENV_FILE), "PSN_NPSSO_TOKEN", token.strip())
            console.print("[green]PSN token saved![/green]")
            console.print("Run 'homo-ludens sync-psn' to sync your PlayStation library.")
        else:
            console.print("[yellow]No token provided.[/yellow]")
        return

    if steam:
        console.print(Panel(
            "[bold]Steam Setup[/bold]\n\n"
            "To connect your Steam account:\n"
            "1. Get your API key at [link]https://steamcommunity.com/dev/apikey[/link]\n"
            "2. Find your Steam ID at [link]https://steamid.io[/link]",
            style="blue",
        ))
        
        api_key = Prompt.ask("Steam API Key")
        if api_key.strip():
            ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
            ENV_FILE.touch(exist_ok=True)
            set_key(str(ENV_FILE), "STEAM_API_KEY", api_key.strip())
        
        steam_id = Prompt.ask("Steam ID (64-bit)")
        if steam_id.strip():
            set_key(str(ENV_FILE), "STEAM_ID", steam_id.strip())
        
        if api_key.strip() or steam_id.strip():
            console.print("[green]Steam configuration saved![/green]")
            console.print("Run 'homo-ludens sync' to sync your Steam library.")
        return

    # No flags - show help
    console.print("Use --psn to configure PlayStation, --steam for Steam, or --show to view config.")


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

    # Platform connections
    if profile.steam_id:
        console.print(f"Steam: [green]connected[/green] ({profile.steam_id})")
    else:
        console.print("Steam: [yellow]not connected[/yellow]")

    if profile.psn_online_id:
        console.print(f"PlayStation: [green]connected[/green] ({profile.psn_online_id})")
    else:
        console.print("PlayStation: [yellow]not connected[/yellow]")

    # Game stats by platform
    steam_games = [g for g in profile.games if g.platform == Platform.STEAM]
    psn_games = [g for g in profile.games if g.platform == Platform.PLAYSTATION]
    
    console.print(f"\nGames in library: {len(profile.games)}")
    if steam_games:
        console.print(f"  Steam: {len(steam_games)}")
    if psn_games:
        console.print(f"  PlayStation: {len(psn_games)}")

    if profile.games:
        total_playtime = sum(g.playtime_minutes for g in profile.games)
        console.print(f"Total playtime: {total_playtime // 60} hours")

        played = len([g for g in profile.games if g.playtime_minutes > 0])
        console.print(f"Games played: {played}/{len(profile.games)}")

    # Wishlist info
    if profile.wishlist:
        on_sale = [item for item in profile.wishlist if item.is_on_sale]
        console.print(f"Wishlist items: {len(profile.wishlist)} ({len(on_sale)} on sale)")

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
