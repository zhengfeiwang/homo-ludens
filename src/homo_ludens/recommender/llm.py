"""LLM-based game recommender using OpenAI/Azure OpenAI."""

import os
from datetime import datetime

from openai import AzureOpenAI, OpenAI

from homo_ludens.models import ConversationHistory, Game, UserProfile

SYSTEM_PROMPT = """You are a personal AI game companion called "Homo Ludens" (Latin for "Playing Human").
Your role is to help the user choose the right game for the right moment based on their preferences,
mood, available time, and gaming history.

You have access to the user's game library and play history. Use this information to make
personalized recommendations. Be conversational, friendly, and curious about their gaming preferences.

When recommending games:
1. Ask about their current mood, available time, or what kind of experience they're looking for
2. Consider their play history - games they've spent time on, recently played, or haven't touched
3. Suggest specific games from their library with brief reasons why
4. Remember their preferences across conversations

Keep responses concise but helpful. You're a gaming buddy, not a formal assistant.
"""


def build_context_prompt(profile: UserProfile) -> str:
    """Build a context prompt with user's game library info."""
    if not profile.games:
        return "The user hasn't synced their game library yet."

    # Sort by playtime
    sorted_games = sorted(profile.games, key=lambda g: g.playtime_minutes, reverse=True)

    # Top played games
    top_played = sorted_games[:10]
    top_played_str = "\n".join(
        f"  - {g.name}: {g.playtime_minutes // 60}h {g.playtime_minutes % 60}m"
        for g in top_played
    )

    # Recently played (if we have last_played data)
    recent = [g for g in sorted_games if g.last_played is not None]
    recent = sorted(recent, key=lambda g: g.last_played or datetime.min, reverse=True)[:5]
    recent_str = (
        "\n".join(f"  - {g.name}" for g in recent)
        if recent
        else "  No recent play data available"
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

    return f"""USER'S GAME LIBRARY ({len(profile.games)} games total):

Most Played:
{top_played_str}

Recently Played:
{recent_str}

Unplayed Games (backlog):
{unplayed_str}

{prefs_str if prefs_str else "No preference data yet."}
"""


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
            temperature=0.7,
            max_tokens=500,
        )

        return response.choices[0].message.content or ""
