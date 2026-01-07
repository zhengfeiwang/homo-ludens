"""Xbox Live API client via OpenXBL.

To get your OpenXBL API key:
1. Go to https://xbl.io and sign in with your Xbox/Microsoft account
2. Navigate to your profile/settings
3. Copy your API key
4. Set as environment variable: OPENXBL_API_KEY="your_key"

Note: Free tier allows 150 requests per hour.
"""

import os
from datetime import datetime

import httpx

from homo_ludens.models import Achievement, AchievementStats, Game, Platform


OPENXBL_API_BASE = "https://xbl.io/api/v2"


class XboxAPIError(Exception):
    """Error from Xbox/OpenXBL API."""

    pass


class XboxClient:
    """Client for Xbox Live API via OpenXBL."""

    def __init__(self, api_key: str | None = None):
        """Initialize Xbox client.

        Args:
            api_key: OpenXBL API key. If not provided,
                     reads from OPENXBL_API_KEY environment variable.
        """
        self.api_key = api_key or os.getenv("OPENXBL_API_KEY")

        if not self.api_key:
            raise XboxAPIError(
                "OpenXBL API key not provided. Set OPENXBL_API_KEY environment variable "
                "or pass api_key parameter.\n\n"
                "To get your API key:\n"
                "1. Sign in at https://xbl.io with your Xbox account\n"
                "2. Go to your profile to find your API key"
            )

        self._http_client = httpx.Client(
            timeout=30.0,
            headers={
                "X-Authorization": self.api_key,
                "Accept": "application/json",
            },
        )

        # Fetch account info to validate key and get xuid/gamertag
        try:
            account_info = self._get_account()
            self.xuid = account_info.get("xuid")
            self.gamertag = account_info.get("gamertag")
        except Exception as e:
            raise XboxAPIError(
                f"Failed to authenticate with OpenXBL. Check your API key.\n"
                f"Error: {e}"
            )

    def _get_account(self) -> dict:
        """Get current user's account info."""
        response = self._http_client.get(f"{OPENXBL_API_BASE}/account")
        response.raise_for_status()
        data = response.json()

        # Parse profile data
        profile_users = data.get("profileUsers", [])
        if not profile_users:
            raise XboxAPIError("No profile data returned")

        user = profile_users[0]
        settings = {s["id"]: s["value"] for s in user.get("settings", [])}

        return {
            "xuid": user.get("id"),
            "gamertag": settings.get("Gamertag"),
            "gamerscore": settings.get("Gamerscore"),
            "display_pic": settings.get("GameDisplayPicRaw"),
        }

    def get_owned_games(self) -> list[Game]:
        """Fetch all games from user's title history.

        Returns:
            List of Game objects with achievement information.
        """
        games = []

        try:
            # Get title history (games played)
            response = self._http_client.get(f"{OPENXBL_API_BASE}/player/titleHistory")
            response.raise_for_status()
            data = response.json()

            titles = data.get("titles", [])

            for title in titles:
                # Skip non-games (apps, etc.)
                if title.get("type") != "Game":
                    continue

                title_id = str(title.get("titleId"))
                
                # Parse last played time
                last_played = None
                last_time_str = title.get("titleHistory", {}).get("lastTimePlayed")
                if last_time_str:
                    try:
                        last_played = datetime.fromisoformat(last_time_str.replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        pass

                game = Game(
                    id=f"xbox_{title_id}",
                    name=title.get("name", f"Unknown ({title_id})"),
                    platform=Platform.XBOX,
                    playtime_minutes=0,  # OpenXBL doesn't provide playtime
                    last_played=last_played,
                    header_image_url=title.get("displayImage"),
                )

                # Add achievement stats if available
                achievement_data = title.get("achievement", {})
                if achievement_data:
                    current_ach = achievement_data.get("currentAchievements", 0)
                    total_ach = achievement_data.get("totalAchievements", 0)
                    current_gs = achievement_data.get("currentGamerscore", 0)
                    total_gs = achievement_data.get("totalGamerscore", 0)
                    progress_pct = achievement_data.get("progressPercentage", 0)

                    # OpenXBL often returns totalAchievements=0 but has gamerscore and progress data
                    # Use progressPercentage to determine the correct total
                    if total_ach == 0 and current_ach > 0:
                        if progress_pct == 100:
                            # 100% completion means current = total
                            total_ach = current_ach
                        elif progress_pct > 0:
                            # Calculate total from percentage: if 18% = 9 achievements, total = 50
                            total_ach = max(int(current_ach * 100 / progress_pct), current_ach)
                        elif total_gs > 0:
                            # Fallback: estimate from gamerscore (roughly 20 GS per achievement)
                            total_ach = max(total_gs // 20, current_ach)
                    
                    if total_ach > 0 or current_ach > 0:
                        game.achievement_stats = AchievementStats(
                            total=max(total_ach, current_ach),  # Ensure total >= current
                            unlocked=current_ach,
                            achievements=[],
                        )

                games.append(game)

        except httpx.HTTPStatusError as e:
            raise XboxAPIError(f"Failed to fetch Xbox games: {e}")
        except Exception as e:
            raise XboxAPIError(f"Failed to fetch Xbox games: {e}")

        return games

    def get_achievements(self) -> list[dict]:
        """Fetch all achievements across all games.

        Returns:
            List of achievement data dicts.
        """
        try:
            response = self._http_client.get(f"{OPENXBL_API_BASE}/achievements")
            response.raise_for_status()
            data = response.json()
            return data.get("titles", [])
        except Exception as e:
            raise XboxAPIError(f"Failed to fetch achievements: {e}")

    def get_game_achievements(self, title_id: str) -> AchievementStats | None:
        """Fetch detailed achievements for a specific game.

        Args:
            title_id: Xbox title ID.

        Returns:
            AchievementStats with individual achievements, or None if not found.
        """
        try:
            response = self._http_client.get(
                f"{OPENXBL_API_BASE}/achievements/title/{title_id}"
            )
            response.raise_for_status()
            data = response.json()

            achievements_data = data.get("achievements", [])
            if not achievements_data:
                return None

            achievements = []
            for ach in achievements_data:
                # Check if unlocked
                progress = ach.get("progressState", "")
                achieved = progress == "Achieved"
                
                # Parse unlock time
                unlock_time = None
                if achieved and ach.get("progression", {}).get("timeUnlocked"):
                    try:
                        time_str = ach["progression"]["timeUnlocked"]
                        unlock_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        pass

                achievement = Achievement(
                    api_name=str(ach.get("id", "")),
                    name=ach.get("name"),
                    description=ach.get("description"),
                    achieved=achieved,
                    unlock_time=unlock_time,
                    global_percent=None,
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
        """Fetch recently played games.

        Args:
            limit: Maximum number of games to return.

        Returns:
            List of recently played games sorted by last played date.
        """
        games = self.get_owned_games()

        # Sort by last_played (most recent first)
        games_with_activity = [g for g in games if g.last_played]
        games_with_activity.sort(key=lambda g: g.last_played or datetime.min, reverse=True)

        return games_with_activity[:limit]

    def close(self):
        """Close the HTTP client."""
        self._http_client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
