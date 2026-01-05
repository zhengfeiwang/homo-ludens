"""Steam Web API client.

To get a Steam API key:
1. Go to https://steamcommunity.com/dev/apikey
2. Log in with your Steam account
3. Enter a domain name (can be "localhost" for personal use)
4. Copy the API key

To find your Steam ID:
1. Go to your Steam profile
2. If you have a custom URL, go to https://steamid.io and enter your profile URL
3. Copy the "steamID64" value (17-digit number)

Set these as environment variables:
    export STEAM_API_KEY="your_api_key"
    export STEAM_ID="your_steam_id_64"
"""

import os
from datetime import datetime

import httpx

from homo_ludens.models import Achievement, AchievementStats, Game, Platform

STEAM_API_BASE = "https://api.steampowered.com"
STEAM_STORE_API = "https://store.steampowered.com/api"


class SteamAPIError(Exception):
    """Error from Steam API."""

    pass


class SteamClient:
    """Client for Steam Web API."""

    def __init__(self, api_key: str | None = None, steam_id: str | None = None):
        self.api_key = api_key or os.getenv("STEAM_API_KEY")
        self.steam_id = steam_id or os.getenv("STEAM_ID")
        self._http_client = httpx.Client(timeout=30.0)

        if not self.api_key:
            raise SteamAPIError(
                "Steam API key not provided. Set STEAM_API_KEY environment variable "
                "or pass api_key parameter. Get your key at: "
                "https://steamcommunity.com/dev/apikey"
            )

    def get_owned_games(self, steam_id: str | None = None) -> list[Game]:
        """Fetch all games owned by the user with playtime info.

        Args:
            steam_id: Steam ID to fetch games for. Defaults to configured steam_id.

        Returns:
            List of Game objects with playtime information.
        """
        steam_id = steam_id or self.steam_id
        if not steam_id:
            raise SteamAPIError(
                "Steam ID not provided. Set STEAM_ID environment variable "
                "or pass steam_id parameter. Find your ID at: https://steamid.io"
            )

        url = f"{STEAM_API_BASE}/IPlayerService/GetOwnedGames/v1/"
        params = {
            "key": self.api_key,
            "steamid": steam_id,
            "include_appinfo": True,
            "include_played_free_games": True,
        }

        response = self._http_client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        games = []
        for game_data in data.get("response", {}).get("games", []):
            game = Game(
                id=f"steam_{game_data['appid']}",
                name=game_data.get("name", f"Unknown ({game_data['appid']})"),
                platform=Platform.STEAM,
                playtime_minutes=game_data.get("playtime_forever", 0),
                last_played=self._unix_to_datetime(game_data.get("rtime_last_played")),
                header_image_url=f"https://steamcdn-a.akamaihd.net/steam/apps/{game_data['appid']}/header.jpg",
            )
            games.append(game)

        return games

    def get_recently_played(
        self, steam_id: str | None = None, count: int = 10
    ) -> list[Game]:
        """Fetch recently played games.

        Args:
            steam_id: Steam ID to fetch games for.
            count: Number of recent games to fetch.

        Returns:
            List of recently played Game objects.
        """
        steam_id = steam_id or self.steam_id
        if not steam_id:
            raise SteamAPIError("Steam ID not provided.")

        url = f"{STEAM_API_BASE}/IPlayerService/GetRecentlyPlayedGames/v1/"
        params = {
            "key": self.api_key,
            "steamid": steam_id,
            "count": count,
        }

        response = self._http_client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        games = []
        for game_data in data.get("response", {}).get("games", []):
            game = Game(
                id=f"steam_{game_data['appid']}",
                name=game_data.get("name", f"Unknown ({game_data['appid']})"),
                platform=Platform.STEAM,
                playtime_minutes=game_data.get("playtime_forever", 0),
                header_image_url=f"https://steamcdn-a.akamaihd.net/steam/apps/{game_data['appid']}/header.jpg",
            )
            games.append(game)

        return games

    def get_game_details(self, app_id: int) -> dict | None:
        """Fetch detailed game info from Steam Store API.

        Note: This API is rate-limited and doesn't require an API key.

        Args:
            app_id: Steam application ID.

        Returns:
            Game details dict or None if not found.
        """
        url = f"{STEAM_STORE_API}/appdetails"
        params = {"appids": app_id}

        response = self._http_client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        app_data = data.get(str(app_id), {})
        if not app_data.get("success"):
            return None

        return app_data.get("data")

    def enrich_game(self, game: Game) -> Game:
        """Enrich a game with additional details from Steam Store.

        Args:
            game: Game object to enrich.

        Returns:
            Enriched Game object.
        """
        # Extract app_id from our id format "steam_12345"
        if not game.id.startswith("steam_"):
            return game

        app_id = int(game.id.replace("steam_", ""))
        details = self.get_game_details(app_id)

        if not details:
            return game

        # Update game with additional info
        game.description = details.get("short_description")
        game.genres = [g["description"] for g in details.get("genres", [])]

        # Release date
        release = details.get("release_date", {})
        if release.get("date") and not release.get("coming_soon"):
            try:
                # Steam uses various date formats, try common ones
                for fmt in ["%b %d, %Y", "%d %b, %Y", "%Y"]:
                    try:
                        game.release_date = datetime.strptime(release["date"], fmt)
                        break
                    except ValueError:
                        continue
            except Exception:
                pass

        return game

    def get_player_achievements(
        self, app_id: int, steam_id: str | None = None
    ) -> AchievementStats | None:
        """Fetch player's achievements for a specific game.

        Args:
            app_id: Steam application ID.
            steam_id: Steam ID to fetch achievements for.

        Returns:
            AchievementStats or None if game has no achievements.
        """
        steam_id = steam_id or self.steam_id
        if not steam_id:
            raise SteamAPIError("Steam ID not provided.")

        url = f"{STEAM_API_BASE}/ISteamUserStats/GetPlayerAchievements/v1/"
        params = {
            "key": self.api_key,
            "steamid": steam_id,
            "appid": app_id,
        }

        try:
            response = self._http_client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        except Exception:
            return None

        player_stats = data.get("playerstats", {})
        if not player_stats.get("success", False):
            return None

        achievements_data = player_stats.get("achievements", [])
        if not achievements_data:
            return None

        # Get global achievement percentages for rarity info
        global_stats = self.get_global_achievement_stats(app_id)

        achievements = []
        unlocked_count = 0

        for ach_data in achievements_data:
            achieved = ach_data.get("achieved", 0) == 1
            if achieved:
                unlocked_count += 1

            achievement = Achievement(
                api_name=ach_data.get("apiname", ""),
                name=ach_data.get("name"),
                description=ach_data.get("description"),
                achieved=achieved,
                unlock_time=self._unix_to_datetime(ach_data.get("unlocktime")),
                global_percent=global_stats.get(ach_data.get("apiname", "")),
            )
            achievements.append(achievement)

        return AchievementStats(
            total=len(achievements),
            unlocked=unlocked_count,
            achievements=achievements,
        )

    def get_global_achievement_stats(self, app_id: int) -> dict[str, float]:
        """Fetch global achievement unlock percentages.

        Args:
            app_id: Steam application ID.

        Returns:
            Dict mapping achievement api_name to unlock percentage.
        """
        url = f"{STEAM_API_BASE}/ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/"
        params = {"gameid": app_id}

        try:
            response = self._http_client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        except Exception:
            return {}

        result = {}
        achievements = (
            data.get("achievementpercentages", {}).get("achievements", [])
        )
        for ach in achievements:
            percent = ach.get("percent", 0)
            if isinstance(percent, str):
                try:
                    percent = float(percent)
                except ValueError:
                    percent = 0.0
            result[ach.get("name", "")] = round(percent, 2)

        return result

    def enrich_game_with_achievements(
        self, game: Game, steam_id: str | None = None
    ) -> Game:
        """Add achievement stats to a game.

        Args:
            game: Game object to enrich.
            steam_id: Steam ID to fetch achievements for.

        Returns:
            Game with achievement_stats populated.
        """
        if not game.id.startswith("steam_"):
            return game

        app_id = int(game.id.replace("steam_", ""))
        achievement_stats = self.get_player_achievements(app_id, steam_id)

        if achievement_stats:
            game.achievement_stats = achievement_stats

        return game

    def _unix_to_datetime(self, timestamp: int | None) -> datetime | None:
        """Convert Unix timestamp to datetime."""
        if not timestamp or timestamp == 0:
            return None
        return datetime.fromtimestamp(timestamp)

    def close(self):
        """Close the HTTP client."""
        self._http_client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
