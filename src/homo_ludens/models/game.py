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


class Achievement(BaseModel):
    """Represents a game achievement."""

    api_name: str = Field(description="Internal achievement identifier")
    name: str | None = None  # Display name (if available)
    description: str | None = None
    achieved: bool = False
    unlock_time: datetime | None = None
    global_percent: float | None = None  # % of players who unlocked this


class AchievementStats(BaseModel):
    """Achievement statistics for a game."""

    total: int = 0
    unlocked: int = 0
    achievements: list[Achievement] = Field(default_factory=list)

    @property
    def completion_percent(self) -> float:
        """Calculate completion percentage."""
        if self.total == 0:
            return 0.0
        return round(self.unlocked / self.total * 100, 1)


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

    # Achievement data
    achievement_stats: AchievementStats | None = None


class PriceInfo(BaseModel):
    """Price information for a game."""

    currency: str = "USD"
    initial_price: float = 0.0  # Original price
    final_price: float = 0.0  # Current price (after discount)
    discount_percent: int = 0
    formatted: str | None = None  # e.g., "$3.99"


class WishlistItem(BaseModel):
    """A game on the user's wishlist."""

    id: str = Field(description="Unique identifier (platform-specific)")
    app_id: int = Field(description="Steam app ID")
    name: str
    added_on: datetime | None = None
    priority: int = 0  # 0 = default, lower = higher priority
    
    # Metadata
    genres: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    release_date: datetime | None = None
    description: str | None = None
    header_image_url: str | None = None
    
    # Price info
    price: PriceInfo | None = None
    
    @property
    def is_on_sale(self) -> bool:
        """Check if the game is currently on sale."""
        return self.price is not None and self.price.discount_percent > 0


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
    psn_online_id: str | None = None
    games: list[Game] = Field(default_factory=list)
    wishlist: list[WishlistItem] = Field(default_factory=list)
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
