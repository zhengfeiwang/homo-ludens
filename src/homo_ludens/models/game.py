"""Core data models for games and user profiles."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator


def _ensure_naive_datetime(dt: datetime) -> datetime:
    """Ensure datetime is naive (no timezone info)."""
    if dt.tzinfo is not None:
        # Convert to UTC then strip timezone
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


class Platform(str, Enum):
    """Gaming platforms."""

    STEAM = "steam"
    PLAYSTATION = "playstation"
    XBOX = "xbox"
    NINTENDO = "nintendo"
    PC_OTHER = "pc_other"


class TrophyTier(str, Enum):
    """PlayStation trophy tiers."""

    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"


class RarityTier(str, Enum):
    """Unified rarity tiers (derived from unlock percentage).
    
    - COMMON: >50% of players unlocked
    - UNCOMMON: 20-50% of players unlocked
    - RARE: 10-20% of players unlocked
    - VERY_RARE: 5-10% of players unlocked
    - ULTRA_RARE: <5% of players unlocked
    """

    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    VERY_RARE = "very_rare"
    ULTRA_RARE = "ultra_rare"


def percent_to_rarity_tier(percent: float | None) -> RarityTier | None:
    """Convert unlock percentage to rarity tier."""
    if percent is None:
        return None
    if percent > 50:
        return RarityTier.COMMON
    elif percent > 20:
        return RarityTier.UNCOMMON
    elif percent > 10:
        return RarityTier.RARE
    elif percent > 5:
        return RarityTier.VERY_RARE
    else:
        return RarityTier.ULTRA_RARE


# =============================================================================
# Platform-Specific Achievement/Trophy Classes
# =============================================================================


class SteamAchievement(BaseModel):
    """Steam achievement with global rarity percentage and localized text."""

    api_name: str = Field(description="Internal achievement identifier")
    name: str | None = None  # Default/English name
    description: str | None = None  # Default/English description
    
    # Localized names and descriptions (key: language code like 'en', 'schinese')
    localized_names: dict[str, str] = Field(default_factory=dict)
    localized_descriptions: dict[str, str] = Field(default_factory=dict)
    
    icon_url: str | None = None
    icon_gray_url: str | None = None
    achieved: bool = False
    unlock_time: datetime | None = None
    global_percent: float | None = None  # Percentage of players who unlocked this

    def get_name(self, language: str = "en") -> str:
        """Get achievement name in specified language, fallback to default."""
        return self.localized_names.get(language) or self.name or "Unknown Achievement"

    def get_description(self, language: str = "en") -> str | None:
        """Get achievement description in specified language, fallback to default."""
        return self.localized_descriptions.get(language) or self.description


class PlayStationTrophy(BaseModel):
    """PlayStation trophy with tier information."""

    trophy_id: int = Field(description="Trophy ID within the game")
    name: str | None = None
    description: str | None = None
    icon_url: str | None = None
    tier: TrophyTier
    achieved: bool = False
    unlock_time: datetime | None = None
    rarity_percent: float | None = None  # Percentage of players who unlocked this
    rarity_tier: RarityTier | None = None  # Derived from rarity_percent or PSN's tier


class XboxAchievement(BaseModel):
    """Xbox achievement with gamerscore value."""

    achievement_id: str = Field(description="Achievement ID")
    name: str | None = None
    description: str | None = None
    icon_url: str | None = None
    gamerscore: int = 0  # Points for this achievement (5, 10, 15, 25, 50, 100, etc.)
    achieved: bool = False
    unlock_time: datetime | None = None
    rarity_percent: float | None = None
    rarity_tier: RarityTier | None = None


# =============================================================================
# Platform-Specific Progress Stats Classes
# =============================================================================


class SteamProgressStats(BaseModel):
    """Steam achievement statistics."""

    type: Literal["steam"] = "steam"
    total: int = 0
    unlocked: int = 0
    achievements: list[SteamAchievement] = Field(default_factory=list)
    raw_data: dict = Field(default_factory=dict)

    @property
    def completion_percent(self) -> float:
        """Calculate completion percentage."""
        if self.total == 0:
            return 0.0
        return round(self.unlocked / self.total * 100, 1)

    @property
    def display_summary(self) -> str:
        """Human-readable summary for display. E.g., '42/50 achievements (84%)'"""
        return f"{self.unlocked}/{self.total} achievements ({self.completion_percent}%)"


class PlayStationProgressStats(BaseModel):
    """PlayStation trophy statistics with tier breakdown."""

    type: Literal["playstation"] = "playstation"
    total: int = 0
    unlocked: int = 0

    # Trophy counts by tier
    bronze_total: int = 0
    bronze_unlocked: int = 0
    silver_total: int = 0
    silver_unlocked: int = 0
    gold_total: int = 0
    gold_unlocked: int = 0
    platinum_total: int = 0  # Usually 0 or 1
    platinum_unlocked: int = 0

    trophies: list[PlayStationTrophy] = Field(default_factory=list)
    raw_data: dict = Field(default_factory=dict)

    @property
    def completion_percent(self) -> float:
        """Calculate completion percentage."""
        if self.total == 0:
            return 0.0
        return round(self.unlocked / self.total * 100, 1)

    @property
    def has_platinum(self) -> bool:
        """Check if the platinum trophy has been earned."""
        return self.platinum_unlocked > 0

    @property
    def display_summary(self) -> str:
        """Human-readable summary with trophy icons. E.g., '🥉12 🥈5 🥇3 🏆'"""
        parts = []
        if self.bronze_unlocked > 0 or self.bronze_total > 0:
            parts.append(f"🥉{self.bronze_unlocked}")
        if self.silver_unlocked > 0 or self.silver_total > 0:
            parts.append(f"🥈{self.silver_unlocked}")
        if self.gold_unlocked > 0 or self.gold_total > 0:
            parts.append(f"🥇{self.gold_unlocked}")
        if self.platinum_total > 0:
            parts.append("🏆" if self.platinum_unlocked > 0 else "")
        if parts:
            return " ".join(p for p in parts if p) + f" ({self.completion_percent}%)"
        return f"{self.unlocked}/{self.total} trophies ({self.completion_percent}%)"


class XboxProgressStats(BaseModel):
    """Xbox achievement statistics with gamerscore."""

    type: Literal["xbox"] = "xbox"
    total: int = 0
    unlocked: int = 0

    # Gamerscore
    total_gamerscore: int = 0
    unlocked_gamerscore: int = 0

    achievements: list[XboxAchievement] = Field(default_factory=list)
    raw_data: dict = Field(default_factory=dict)

    @property
    def completion_percent(self) -> float:
        """Calculate completion percentage based on achievement count."""
        if self.total == 0:
            return 0.0
        return round(self.unlocked / self.total * 100, 1)

    @property
    def gamerscore_percent(self) -> float:
        """Calculate completion percentage based on gamerscore."""
        if self.total_gamerscore == 0:
            return 0.0
        return round(self.unlocked_gamerscore / self.total_gamerscore * 100, 1)

    @property
    def display_summary(self) -> str:
        """Human-readable summary with gamerscore. E.g., '850/1000 GS (85%)'"""
        if self.total_gamerscore > 0:
            return f"{self.unlocked_gamerscore}/{self.total_gamerscore} GS ({self.gamerscore_percent}%)"
        return f"{self.unlocked}/{self.total} achievements ({self.completion_percent}%)"


# Discriminated union for progress stats
ProgressStats = Annotated[
    SteamProgressStats | PlayStationProgressStats | XboxProgressStats,
    Field(discriminator="type"),
]


# =============================================================================
# Legacy Classes (Deprecated - kept for reference during transition)
# =============================================================================


class Achievement(BaseModel):
    """Represents a game achievement. DEPRECATED: Use platform-specific classes."""

    api_name: str = Field(description="Internal achievement identifier")
    name: str | None = None  # Display name (if available)
    description: str | None = None
    achieved: bool = False
    unlock_time: datetime | None = None
    global_percent: float | None = None  # % of players who unlocked this


class AchievementStats(BaseModel):
    """Achievement statistics for a game. DEPRECATED: Use platform-specific classes."""

    total: int = 0
    unlocked: int = 0
    achievements: list[Achievement] = Field(default_factory=list)

    @property
    def completion_percent(self) -> float:
        """Calculate completion percentage."""
        if self.total == 0:
            return 0.0
        return round(self.unlocked / self.total * 100, 1)


# =============================================================================
# Game and Related Models
# =============================================================================


class Game(BaseModel):
    """Represents a game in the user's library."""

    id: str = Field(description="Unique identifier (platform-specific)")
    name: str
    platform: Platform
    playtime_minutes: int = 0
    last_played: datetime | None = None

    # Localized names (key: language code, value: localized name)
    # e.g., {"en": "The Witcher 3", "zh": "巫师3"}
    localized_names: dict[str, str] = Field(default_factory=dict)

    # Metadata (can be enriched later)
    genres: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    release_date: datetime | None = None
    description: str | None = None
    header_image_url: str | None = None

    # Platform-specific progress data
    progress: SteamProgressStats | PlayStationProgressStats | XboxProgressStats | None = None

    def get_name(self, language: str = "en") -> str:
        """Get the game name in the specified language, fallback to default name."""
        return self.localized_names.get(language, self.name)

    @property
    def completion_percent(self) -> float:
        """Get completion percentage from progress stats."""
        if self.progress is None:
            return 0.0
        return self.progress.completion_percent


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
    xbox_gamertag: str | None = None
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

    @field_validator("timestamp", mode="after")
    @classmethod
    def ensure_naive_timestamp(cls, v: datetime) -> datetime:
        return _ensure_naive_datetime(v)


class ConversationHistory(BaseModel):
    """Conversation history for context (legacy, kept for compatibility)."""

    messages: list[ConversationMessage] = Field(default_factory=list)
    max_messages: int = 50  # Keep last N messages for context

    def add_message(self, role: str, content: str) -> None:
        """Add a message and trim if needed."""
        self.messages.append(ConversationMessage(role=role, content=content))
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages :]


class Conversation(BaseModel):
    """A conversation with the AI companion."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "New Conversation"
    messages: list[ConversationMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    max_messages: int = 50  # Keep last N messages for context

    @field_validator("created_at", "updated_at", mode="after")
    @classmethod
    def ensure_naive_datetime(cls, v: datetime) -> datetime:
        return _ensure_naive_datetime(v)

    def add_message(self, role: str, content: str) -> None:
        """Add a message and trim if needed."""
        self.messages.append(ConversationMessage(role=role, content=content))
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages :]
        self.updated_at = datetime.now()


class ConversationMetadata(BaseModel):
    """Lightweight conversation metadata for listing."""

    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
