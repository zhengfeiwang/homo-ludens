"""Local file-based storage for user data."""

import json
from datetime import datetime
from pathlib import Path

from homo_ludens.models import ConversationHistory, UserProfile

DEFAULT_DATA_DIR = Path.home() / ".homo_ludens"


class Storage:
    """File-based storage for user profile and conversation history."""

    def __init__(self, data_dir: Path | str | None = None):
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.profile_path = self.data_dir / "profile.json"
        self.conversation_path = self.data_dir / "conversation.json"

    def load_profile(self) -> UserProfile:
        """Load user profile from disk, or create a new one."""
        if self.profile_path.exists():
            with open(self.profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return UserProfile.model_validate(data)
        return UserProfile()

    def save_profile(self, profile: UserProfile) -> None:
        """Save user profile to disk."""
        profile.updated_at = datetime.now()
        with open(self.profile_path, "w", encoding="utf-8") as f:
            json.dump(profile.model_dump(mode="json"), f, indent=2, default=str)

    def load_conversation(self) -> ConversationHistory:
        """Load conversation history from disk."""
        if self.conversation_path.exists():
            with open(self.conversation_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return ConversationHistory.model_validate(data)
        return ConversationHistory()

    def save_conversation(self, history: ConversationHistory) -> None:
        """Save conversation history to disk."""
        with open(self.conversation_path, "w", encoding="utf-8") as f:
            json.dump(history.model_dump(mode="json"), f, indent=2, default=str)

    def clear_conversation(self) -> None:
        """Clear conversation history."""
        if self.conversation_path.exists():
            self.conversation_path.unlink()

    def clear_all(self) -> None:
        """Clear all stored data."""
        if self.profile_path.exists():
            self.profile_path.unlink()
        self.clear_conversation()
