"""Local file-based storage for user data."""

import json
from datetime import datetime
from pathlib import Path

from homo_ludens.models import (
    Conversation,
    ConversationHistory,
    ConversationMetadata,
    UserProfile,
)

DEFAULT_DATA_DIR = Path.home() / ".homo_ludens"


class Storage:
    """File-based storage for user profile and conversation history."""

    def __init__(self, data_dir: Path | str | None = None):
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.profile_path = self.data_dir / "profile.json"
        self.conversation_path = self.data_dir / "conversation.json"  # Legacy
        self.conversations_dir = self.data_dir / "conversations"
        self.conversations_dir.mkdir(parents=True, exist_ok=True)

    def load_profile(self) -> UserProfile:
        """Load user profile from disk, or create a new one.
        
        If the profile schema has changed (e.g., achievement_stats -> progress),
        returns an empty profile. User will need to re-sync.
        """
        if self.profile_path.exists():
            try:
                with open(self.profile_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return UserProfile.model_validate(data)
            except Exception:
                # Schema changed or corrupted file, return empty profile
                # User will need to re-sync their library
                return UserProfile()
        return UserProfile()

    def save_profile(self, profile: UserProfile) -> None:
        """Save user profile to disk."""
        profile.updated_at = datetime.now()
        with open(self.profile_path, "w", encoding="utf-8") as f:
            json.dump(profile.model_dump(mode="json"), f, indent=2, default=str)

    # =========================================================================
    # Multi-conversation support
    # =========================================================================

    def list_conversations(self) -> list[ConversationMetadata]:
        """List all conversations, sorted by updated_at (newest first)."""
        conversations = []
        for file_path in self.conversations_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    conv = Conversation.model_validate(data)
                    # Ensure updated_at is naive (strip timezone if present)
                    updated_at = conv.updated_at
                    if updated_at.tzinfo is not None:
                        updated_at = updated_at.replace(tzinfo=None)
                    created_at = conv.created_at
                    if created_at.tzinfo is not None:
                        created_at = created_at.replace(tzinfo=None)
                    conversations.append(
                        ConversationMetadata(
                            id=conv.id,
                            title=conv.title,
                            created_at=created_at,
                            updated_at=updated_at,
                            message_count=len(conv.messages),
                        )
                    )
            except (json.JSONDecodeError, Exception):
                # Skip corrupted files
                continue
        # Sort by updated_at descending
        conversations.sort(key=lambda c: c.updated_at, reverse=True)
        return conversations

    def get_conversation(self, conv_id: str) -> Conversation | None:
        """Load a specific conversation by ID."""
        file_path = self.conversations_dir / f"{conv_id}.json"
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return Conversation.model_validate(data)
        return None

    def save_conversation_v2(self, conversation: Conversation) -> None:
        """Save a conversation to disk."""
        conversation.updated_at = datetime.now()
        file_path = self.conversations_dir / f"{conversation.id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(conversation.model_dump(mode="json"), f, indent=2, default=str)

    def create_conversation(self, title: str = "New Conversation") -> Conversation:
        """Create a new conversation and save it."""
        conversation = Conversation(title=title)
        self.save_conversation_v2(conversation)
        return conversation

    def delete_conversation(self, conv_id: str) -> bool:
        """Delete a conversation by ID. Returns True if deleted."""
        file_path = self.conversations_dir / f"{conv_id}.json"
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def rename_conversation(self, conv_id: str, new_title: str) -> Conversation | None:
        """Rename a conversation. Returns updated conversation or None."""
        conversation = self.get_conversation(conv_id)
        if conversation:
            conversation.title = new_title
            self.save_conversation_v2(conversation)
            return conversation
        return None

    def migrate_legacy_conversation(self) -> Conversation | None:
        """Migrate legacy conversation.json to new format if it exists."""
        if not self.conversation_path.exists():
            return None

        try:
            with open(self.conversation_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                legacy = ConversationHistory.model_validate(data)

            if legacy.messages:
                # Create new conversation with legacy messages
                conversation = Conversation(
                    title="Imported Conversation",
                    messages=legacy.messages,
                )
                self.save_conversation_v2(conversation)

                # Remove legacy file after successful migration
                self.conversation_path.unlink()
                return conversation
        except (json.JSONDecodeError, Exception):
            pass

        return None

    # =========================================================================
    # Legacy methods (kept for CLI compatibility)
    # =========================================================================

    def load_conversation(self) -> ConversationHistory:
        """Load conversation history from disk (legacy method)."""
        if self.conversation_path.exists():
            with open(self.conversation_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return ConversationHistory.model_validate(data)
        return ConversationHistory()

    def save_conversation(self, history: ConversationHistory) -> None:
        """Save conversation history to disk (legacy method)."""
        with open(self.conversation_path, "w", encoding="utf-8") as f:
            json.dump(history.model_dump(mode="json"), f, indent=2, default=str)

    def clear_conversation(self) -> None:
        """Clear conversation history (legacy method)."""
        if self.conversation_path.exists():
            self.conversation_path.unlink()

    def clear_all(self) -> None:
        """Clear all stored data."""
        if self.profile_path.exists():
            self.profile_path.unlink()
        self.clear_conversation()
        # Also clear all conversations
        for file_path in self.conversations_dir.glob("*.json"):
            file_path.unlink()
