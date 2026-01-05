"""Core data models for games and user profiles."""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class Platform(str, Enum):
    """Gaming platforms."""

    STEAM = "steam"
    PLAYSTATION = "playstation"
    XBOX = "xbox"
    NINTENDO = "nintendo"
    PC_OTHER = "pc_other"


class Game(BaseModel):
    """Represents a game in the user's library."""

    id: str = Field(description="Unique identifier (platform-specific)")
    name: str
    platform: Platform
    playtime_minutes: int = 0
    last_played: datetime | None = None

    # Metadata (can be enriched later)
    genres: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    release_date: datetime | None = None
    description: str | None = None
    header_image_url: str | None = None


class PlaySession(BaseModel):
    """Represents a single play session."""

    game_id: str
    platform: Platform
    started_at: datetime
    duration_minutes: int
    notes: str | None = None


class UserPreferences(BaseModel):
    """User's gaming preferences learned over time."""

    favorite_genres: list[str] = Field(default_factory=list)
    favorite_tags: list[str] = Field(default_factory=list)
    preferred_session_length_minutes: int | None = None
    notes: str = ""  # Free-form notes from conversations


class UserProfile(BaseModel):
    """Complete user profile."""

    steam_id: str | None = None
    games: list[Game] = Field(default_factory=list)
    play_history: list[PlaySession] = Field(default_factory=list)
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ConversationMessage(BaseModel):
    """A message in the conversation history."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)


class ConversationHistory(BaseModel):
    """Conversation history for context."""

    messages: list[ConversationMessage] = Field(default_factory=list)
    max_messages: int = 50  # Keep last N messages for context

    def add_message(self, role: str, content: str) -> None:
        """Add a message and trim if needed."""
        self.messages.append(ConversationMessage(role=role, content=content))
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages :]
