"""LLM-based game recommender using OpenAI/Azure OpenAI."""

import os
from datetime import datetime

from openai import AzureOpenAI, OpenAI

from homo_ludens.models import ConversationHistory, Game, Platform, UserProfile

SYSTEM_PROMPT = """You are a personal AI game companion called "Homo Ludens" (Latin for "Playing Human").
Your role is to help the user choose the right game for the right moment based on their preferences,
mood, available time, and gaming history.

You have access to the user's game library across multiple platforms (Steam, PlayStation), play history, 
achievement/trophy data, and wishlist. Use this information to make personalized recommendations. 
Be conversational, friendly, and curious about their gaming preferences.

When recommending games:
1. Ask about their current mood, available time, or what kind of experience they're looking for
2. Consider their play history - games they've spent time on, recently played, or haven't touched
3. Use achievement/trophy completion as a signal of engagement (high % = loved it, low % = might have dropped it)
4. Suggest specific games from their library with brief reasons why
5. When suggesting new games to buy, consider their wishlist and current deals
6. Remember their preferences across conversations
7. Make cross-platform recommendations - if they loved a game on one platform, recommend similar games on another

Keep responses concise but helpful. You're a gaming buddy, not a formal assistant.
"""


def _format_game_with_achievements(game: Game) -> str:
    """Format a game entry with playtime and achievement info."""
    hours = game.playtime_minutes // 60
    mins = game.playtime_minutes % 60
    
    # Platform indicator
    platform_icon = "🎮" if game.platform == Platform.PLAYSTATION else "🖥️"
    base = f"  - {platform_icon} {game.name}: {hours}h {mins}m"
    
    if game.achievement_stats and game.achievement_stats.total > 0:
        stats = game.achievement_stats
        trophy_word = "trophies" if game.platform == Platform.PLAYSTATION else "achievements"
        base += f" ({stats.unlocked}/{stats.total} {trophy_word}, {stats.completion_percent}% complete)"
    
    return base


def build_context_prompt(profile: UserProfile) -> str:
    """Build a context prompt with user's game library info."""
    if not profile.games:
        return "The user hasn't synced their game library yet."

    # Sort by playtime
    sorted_games = sorted(profile.games, key=lambda g: g.playtime_minutes, reverse=True)

    # Top played games with achievement info
    top_played = sorted_games[:10]
    top_played_str = "\n".join(_format_game_with_achievements(g) for g in top_played)

    # Recently played (if we have last_played data)
    recent = [g for g in sorted_games if g.last_played is not None]
    recent = sorted(recent, key=lambda g: g.last_played or datetime.min, reverse=True)[:5]
    recent_str = (
        "\n".join(_format_game_with_achievements(g) for g in recent)
        if recent
        else "  No recent play data available"
    )

    # High achievement completion games (loved games)
    games_with_achievements = [
        g for g in sorted_games 
        if g.achievement_stats and g.achievement_stats.total > 0
    ]
    completed_games = [
        g for g in games_with_achievements 
        if g.achievement_stats and g.achievement_stats.completion_percent >= 50
    ]
    completed_games = sorted(
        completed_games, 
        key=lambda g: g.achievement_stats.completion_percent if g.achievement_stats else 0, 
        reverse=True
    )[:5]
    completed_str = (
        "\n".join(
            f"  - {g.name}: {g.achievement_stats.completion_percent}% {'trophies' if g.platform == Platform.PLAYSTATION else 'achievements'}"
            for g in completed_games
            if g.achievement_stats
        )
        if completed_games
        else "  No achievement data available"
    )

    # Unplayed games
    unplayed = [g for g in sorted_games if g.playtime_minutes == 0][:10]
    unplayed_str = (
        "\n".join(f"  - {g.name}" for g in unplayed)
        if unplayed
        else "  All games have been played!"
    )

    # Preferences
    prefs = profile.preferences
    prefs_str = ""
    if prefs.favorite_genres:
        prefs_str += f"Favorite genres: {', '.join(prefs.favorite_genres)}\n"
    if prefs.favorite_tags:
        prefs_str += f"Favorite tags: {', '.join(prefs.favorite_tags)}\n"
    if prefs.notes:
        prefs_str += f"Notes: {prefs.notes}\n"

    # Platform breakdown
    steam_games = [g for g in profile.games if g.platform == Platform.STEAM]
    psn_games = [g for g in profile.games if g.platform == Platform.PLAYSTATION]
    platform_str = f"Platforms: Steam ({len(steam_games)} games)"
    if psn_games:
        platform_str += f", PlayStation ({len(psn_games)} games)"

    return f"""USER'S GAME LIBRARY ({len(profile.games)} games total):
{platform_str}

Most Played (🖥️ = Steam, 🎮 = PlayStation):
{top_played_str}

Recently Played:
{recent_str}

High Achievement/Trophy Completion (games they likely loved):
{completed_str}

Unplayed Games (backlog):
{unplayed_str}

{prefs_str if prefs_str else "No preference data yet."}
{_build_wishlist_context(profile)}
"""


def _build_wishlist_context(profile: UserProfile) -> str:
    """Build wishlist section of context."""
    if not profile.wishlist:
        return ""
    
    # Games on sale
    on_sale = [item for item in profile.wishlist if item.is_on_sale]
    on_sale_str = ""
    if on_sale:
        on_sale_str = "WISHLIST - ON SALE:\n" + "\n".join(
            f"  - {item.name}: {item.price.formatted} (-{item.price.discount_percent}%)"
            + (f" - {', '.join(item.genres[:2])}" if item.genres else "")
            for item in on_sale[:10]
            if item.price
        )
    
    # Other wishlist items
    not_on_sale = [item for item in profile.wishlist if not item.is_on_sale][:5]
    other_str = ""
    if not_on_sale:
        other_str = "\nWISHLIST - OTHER ITEMS:\n" + "\n".join(
            f"  - {item.name}"
            + (f": {item.price.formatted}" if item.price else "")
            + (f" - {', '.join(item.genres[:2])}" if item.genres else "")
            for item in not_on_sale
        )
    
    if on_sale_str or other_str:
        return f"\n{on_sale_str}{other_str}"
    return ""


class Recommender:
    """LLM-powered game recommender."""

    def __init__(
        self,
        api_key: str | None = None,
        azure_endpoint: str | None = None,
        azure_deployment: str | None = None,
        model: str = "gpt-4o-mini",
    ):
        """Initialize the recommender.

        For OpenAI: Just set OPENAI_API_KEY env var or pass api_key.
        For Azure OpenAI: Set AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT,
                         and optionally AZURE_OPENAI_DEPLOYMENT env vars.
        """
        self.model = model

        # Check for Azure OpenAI first
        azure_endpoint = azure_endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        azure_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        azure_deployment = azure_deployment or os.getenv(
            "AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini"
        )

        if azure_endpoint and azure_key:
            self.client = AzureOpenAI(
                api_key=azure_key,
                api_version="2024-02-15-preview",
                azure_endpoint=azure_endpoint,
            )
            self.model = azure_deployment
            self._is_azure = True
        else:
            # Fall back to OpenAI
            openai_key = api_key or os.getenv("OPENAI_API_KEY")
            if not openai_key:
                raise ValueError(
                    "No API key found. Set OPENAI_API_KEY or AZURE_OPENAI_API_KEY "
                    "environment variable."
                )
            self.client = OpenAI(api_key=openai_key)
            self._is_azure = False

    def chat(
        self,
        user_message: str,
        profile: UserProfile,
        history: ConversationHistory,
    ) -> str:
        """Send a message and get a response.

        Args:
            user_message: The user's message.
            profile: User's profile with game library.
            history: Conversation history for context.

        Returns:
            The assistant's response.
        """
        # Build messages
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": build_context_prompt(profile)},
        ]

        # Add conversation history
        for msg in history.messages[-20:]:  # Last 20 messages for context
            messages.append({"role": msg.role, "content": msg.content})

        # Add current message
        messages.append({"role": "user", "content": user_message})

        # Call the API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_completion_tokens=500,
        )

        return response.choices[0].message.content or ""
