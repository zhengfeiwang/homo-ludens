"""PlayStation Network API client.

To get your NPSSO token:
1. Log in to PlayStation Store: https://store.playstation.com
2. Visit: https://ca.account.sony.com/api/v1/ssocookie
3. Copy the "npsso" value from the JSON response
4. Set as environment variable: PSN_NPSSO_TOKEN="your_token"

Note: The token expires after ~60 days and needs to be refreshed.
"""

import os
from datetime import datetime

from psnawp_api import PSNAWP
from psnawp_api.core.psnawp_exceptions import PSNAWPNotFoundError, PSNAWPAuthenticationError

from homo_ludens.models import Achievement, AchievementStats, Game, Platform


class PSNAPIError(Exception):
    """Error from PlayStation Network API."""

    pass


class PSNClient:
    """Client for PlayStation Network API."""

    def __init__(self, npsso_token: str | None = None):
        """Initialize PSN client.

        Args:
            npsso_token: NPSSO authentication token. If not provided,
                         reads from PSN_NPSSO_TOKEN environment variable.
        """
        self.npsso_token = npsso_token or os.getenv("PSN_NPSSO_TOKEN")

        if not self.npsso_token:
            raise PSNAPIError(
                "PSN NPSSO token not provided. Set PSN_NPSSO_TOKEN environment variable "
                "or pass npsso_token parameter.\n\n"
                "To get your token:\n"
                "1. Log in at https://store.playstation.com\n"
                "2. Visit https://ca.account.sony.com/api/v1/ssocookie\n"
                "3. Copy the 'npsso' value"
            )

        try:
            self._psnawp = PSNAWP(self.npsso_token)
            self._client = self._psnawp.me()
            self.online_id = self._client.online_id
            self.account_id = self._client.account_id
        except PSNAWPAuthenticationError as e:
            raise PSNAPIError(
                f"PSN authentication failed. Your token may have expired.\n"
                f"Please get a new token from https://ca.account.sony.com/api/v1/ssocookie\n"
                f"Error: {e}"
            )

    def get_owned_games(self) -> list[Game]:
        """Fetch all games from user's trophy list (indicates ownership/played).

        Returns:
            List of Game objects with trophy information.
        """
        games = []

        try:
            # Get all trophy titles (games the user has played)
            for trophy_title in self._client.trophy_titles():
                game = Game(
                    id=f"psn_{trophy_title.np_communication_id}",
                    name=trophy_title.title_name or f"Unknown ({trophy_title.np_communication_id})",
                    platform=Platform.PLAYSTATION,
                    playtime_minutes=0,  # PSN doesn't expose playtime via API
                    last_played=trophy_title.last_updated_datetime,
                    header_image_url=trophy_title.title_icon_url,
                )

                # Add trophy stats as achievement stats
                if trophy_title.defined_trophies:
                    total = (
                        trophy_title.defined_trophies.bronze +
                        trophy_title.defined_trophies.silver +
                        trophy_title.defined_trophies.gold +
                        trophy_title.defined_trophies.platinum
                    )
                    unlocked = 0
                    if trophy_title.earned_trophies:
                        unlocked = (
                            trophy_title.earned_trophies.bronze +
                            trophy_title.earned_trophies.silver +
                            trophy_title.earned_trophies.gold +
                            trophy_title.earned_trophies.platinum
                        )

                    game.achievement_stats = AchievementStats(
                        total=total,
                        unlocked=unlocked,
                        achievements=[],  # Don't fetch individual trophies for now
                    )

                games.append(game)

        except PSNAWPNotFoundError:
            # User has no trophy titles
            pass
        except Exception as e:
            raise PSNAPIError(f"Failed to fetch PSN games: {e}")

        return games

    def get_game_trophies(self, np_communication_id: str) -> AchievementStats | None:
        """Fetch detailed trophy info for a specific game.

        Args:
            np_communication_id: The game's trophy communication ID.

        Returns:
            AchievementStats with individual trophies, or None if not found.
        """
        try:
            # Get the trophy title
            trophy_titles = list(self._client.trophy_titles())
            trophy_title = None
            for tt in trophy_titles:
                if tt.np_communication_id == np_communication_id:
                    trophy_title = tt
                    break

            if not trophy_title:
                return None

            # Get individual trophies with progress
            achievements = []
            trophies_iter = self._client.trophies(
                np_communication_id=np_communication_id,
                platform=list(trophy_title.title_platform)[0] if trophy_title.title_platform else None,
            )
            
            for trophy in trophies_iter:
                achievement = Achievement(
                    api_name=str(trophy.trophy_id),
                    name=trophy.trophy_name,
                    description=trophy.trophy_detail,
                    achieved=getattr(trophy, 'earned', False) or False,
                    unlock_time=getattr(trophy, 'earned_date_time', None),
                    global_percent=getattr(trophy, 'trophy_earn_rate', None),
                )
                achievements.append(achievement)

            total = len(achievements)
            unlocked = len([a for a in achievements if a.achieved])

            return AchievementStats(
                total=total,
                unlocked=unlocked,
                achievements=achievements,
            )

        except Exception:
            return None

    def get_recently_played(self, limit: int = 10) -> list[Game]:
        """Fetch recently played games based on trophy activity.

        Args:
            limit: Maximum number of games to return.

        Returns:
            List of recently played games sorted by last trophy date.
        """
        games = self.get_owned_games()

        # Sort by last_played (most recent first)
        games_with_activity = [g for g in games if g.last_played]
        games_with_activity.sort(key=lambda g: g.last_played or datetime.min, reverse=True)

        return games_with_activity[:limit]

    def close(self):
        """Close the client (no-op for psnawp, but matches SteamClient interface)."""
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
