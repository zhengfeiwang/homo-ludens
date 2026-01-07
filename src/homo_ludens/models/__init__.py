"""Data models for Homo Ludens."""

from homo_ludens.models.game import (
    # Legacy (deprecated but kept for compatibility)
    Achievement,
    AchievementStats,
    # Conversations
    Conversation,
    ConversationHistory,
    ConversationMessage,
    ConversationMetadata,
    # Core models
    Game,
    Platform,
    PlaySession,
    PriceInfo,
    UserPreferences,
    UserProfile,
    WishlistItem,
    # New platform-specific progress models
    TrophyTier,
    RarityTier,
    percent_to_rarity_tier,
    SteamAchievement,
    PlayStationTrophy,
    XboxAchievement,
    SteamProgressStats,
    PlayStationProgressStats,
    XboxProgressStats,
    ProgressStats,
)

__all__ = [
    # Legacy (deprecated)
    "Achievement",
    "AchievementStats",
    # Conversations
    "Conversation",
    "ConversationHistory",
    "ConversationMessage",
    "ConversationMetadata",
    # Core models
    "Game",
    "Platform",
    "PlaySession",
    "PriceInfo",
    "UserPreferences",
    "UserProfile",
    "WishlistItem",
    # New platform-specific progress models
    "TrophyTier",
    "RarityTier",
    "percent_to_rarity_tier",
    "SteamAchievement",
    "PlayStationTrophy",
    "XboxAchievement",
    "SteamProgressStats",
    "PlayStationProgressStats",
    "XboxProgressStats",
    "ProgressStats",
]
