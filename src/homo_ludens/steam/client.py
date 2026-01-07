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

from homo_ludens.models import (
    Game,
    Platform,
    PriceInfo,
    WishlistItem,
    SteamAchievement,
    SteamProgressStats,
    percent_to_rarity_tier,
)

STEAM_API_BASE = "https://api.steampowered.com"
STEAM_STORE_API = "https://store.steampowered.com/api"

# Supported languages for localization
SUPPORTED_LANGUAGES = ["english", "schinese"]  # English and Simplified Chinese


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

    def get_owned_games(self, steam_id: str | None = None, fetch_localized: bool = False) -> list[Game]:
        """Fetch all games owned by the user with playtime info.

        Args:
            steam_id: Steam ID to fetch games for. Defaults to configured steam_id.
            fetch_localized: If True, fetch localized names (slower, makes extra API calls).

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
            app_id = game_data['appid']
            name = game_data.get("name", f"Unknown ({app_id})")
            
            # Initialize localized_names with English name from API
            localized_names = {"en": name}
            
            game = Game(
                id=f"steam_{app_id}",
                name=name,
                platform=Platform.STEAM,
                playtime_minutes=game_data.get("playtime_forever", 0),
                last_played=self._unix_to_datetime(game_data.get("rtime_last_played")),
                header_image_url=f"https://steamcdn-a.akamaihd.net/steam/apps/{app_id}/header.jpg",
                localized_names=localized_names,
            )
            games.append(game)

        return games

    def enrich_game_with_localized_names(self, game: Game) -> Game:
        """Add localized names to a game.

        Args:
            game: Game object to enrich.

        Returns:
            Game with localized_names populated.
        """
        if not game.id.startswith("steam_"):
            return game

        app_id = int(game.id.replace("steam_", ""))
        localized_names = self.get_localized_game_name(app_id)
        
        if localized_names:
            game.localized_names.update(localized_names)

        return game

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

    def get_game_details(self, app_id: int, language: str = "english") -> dict | None:
        """Fetch detailed game info from Steam Store API.

        Note: This API is rate-limited and doesn't require an API key.

        Args:
            app_id: Steam application ID.
            language: Language for localized content (e.g., 'english', 'schinese').

        Returns:
            Game details dict or None if not found.
        """
        url = f"{STEAM_STORE_API}/appdetails"
        params = {"appids": app_id, "l": language}

        response = self._http_client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        app_data = data.get(str(app_id), {})
        if not app_data.get("success"):
            return None

        return app_data.get("data")

    def get_localized_game_name(self, app_id: int) -> dict[str, str]:
        """Fetch game name in multiple languages.

        Args:
            app_id: Steam application ID.

        Returns:
            Dict mapping language code to localized name.
        """
        localized_names = {}
        
        for lang in SUPPORTED_LANGUAGES:
            try:
                details = self.get_game_details(app_id, language=lang)
                if details and details.get("name"):
                    # Map Steam language codes to our shorter codes
                    lang_code = "en" if lang == "english" else "schinese"
                    localized_names[lang_code] = details["name"]
            except Exception:
                pass
        
        return localized_names

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

    def get_achievement_schema(self, app_id: int, language: str = "english") -> dict[str, dict]:
        """Fetch achievement schema (names, descriptions, icons) for a game.

        Args:
            app_id: Steam application ID.
            language: Language code (e.g., 'english', 'schinese').

        Returns:
            Dict mapping api_name to achievement info (displayName, description, icon, icongray).
        """
        url = f"{STEAM_API_BASE}/ISteamUserStats/GetSchemaForGame/v2/"
        params = {"key": self.api_key, "appid": app_id, "l": language}

        try:
            response = self._http_client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        except Exception:
            return {}

        schema = {}
        achievements = data.get("game", {}).get("availableGameStats", {}).get("achievements", [])
        for ach in achievements:
            schema[ach.get("name", "")] = {
                "displayName": ach.get("displayName"),
                "description": ach.get("description"),
                "icon": ach.get("icon"),
                "icongray": ach.get("icongray"),
            }

        return schema

    def get_achievement_schema_multilang(self, app_id: int) -> dict[str, dict[str, dict]]:
        """Fetch achievement schema in multiple languages.

        Args:
            app_id: Steam application ID.

        Returns:
            Dict mapping language code to schema dict.
            Schema dict maps api_name to achievement info.
        """
        schemas = {}
        for lang in SUPPORTED_LANGUAGES:
            schema = self.get_achievement_schema(app_id, language=lang)
            if schema:
                # Map Steam language codes to our shorter codes
                lang_code = "en" if lang == "english" else lang
                schemas[lang_code] = schema
        return schemas

    def get_player_achievements(
        self, app_id: int, steam_id: str | None = None, fetch_localized: bool = True
    ) -> SteamProgressStats | None:
        """Fetch player's achievements for a specific game.

        Args:
            app_id: Steam application ID.
            steam_id: Steam ID to fetch achievements for.
            fetch_localized: If True, fetch achievement names in multiple languages.

        Returns:
            SteamProgressStats or None if game has no achievements.
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

        # Get achievement schema for names, descriptions, icons
        if fetch_localized:
            # Fetch schemas in all supported languages
            schemas = self.get_achievement_schema_multilang(app_id)
            schema_en = schemas.get("en", {})
            schema_zh = schemas.get("schinese", {})
        else:
            schema_en = self.get_achievement_schema(app_id, language="english")
            schema_zh = {}

        # Get global achievement percentages for rarity info
        global_stats = self.get_global_achievement_stats(app_id)

        # Store raw data for debugging/future use
        raw_data = {
            "player_stats": player_stats,
            "schema_en": schema_en,
            "schema_zh": schema_zh,
            "global_stats": global_stats,
        }

        achievements = []
        unlocked_count = 0

        for ach_data in achievements_data:
            api_name = ach_data.get("apiname", "")
            achieved = ach_data.get("achieved", 0) == 1
            if achieved:
                unlocked_count += 1

            # Get info from English schema (for icons and default name)
            ach_schema_en = schema_en.get(api_name, {})
            ach_schema_zh = schema_zh.get(api_name, {})
            global_percent = global_stats.get(api_name)

            # Build localized names and descriptions
            localized_names = {}
            localized_descriptions = {}
            
            if ach_schema_en.get("displayName"):
                localized_names["en"] = ach_schema_en["displayName"]
            if ach_schema_en.get("description"):
                localized_descriptions["en"] = ach_schema_en["description"]
            
            if ach_schema_zh.get("displayName"):
                localized_names["schinese"] = ach_schema_zh["displayName"]
            if ach_schema_zh.get("description"):
                localized_descriptions["schinese"] = ach_schema_zh["description"]

            achievement = SteamAchievement(
                api_name=api_name,
                name=ach_schema_en.get("displayName"),  # Default to English
                description=ach_schema_en.get("description"),
                localized_names=localized_names,
                localized_descriptions=localized_descriptions,
                icon_url=ach_schema_en.get("icon"),
                icon_gray_url=ach_schema_en.get("icongray"),
                achieved=achieved,
                unlock_time=self._unix_to_datetime(ach_data.get("unlocktime")),
                global_percent=global_percent,
            )
            achievements.append(achievement)

        return SteamProgressStats(
            total=len(achievements),
            unlocked=unlocked_count,
            achievements=achievements,
            raw_data=raw_data,
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
            Game with progress populated.
        """
        if not game.id.startswith("steam_"):
            return game

        app_id = int(game.id.replace("steam_", ""))
        progress = self.get_player_achievements(app_id, steam_id)

        if progress:
            game.progress = progress

        return game

    def get_wishlist(self, steam_id: str | None = None) -> list[WishlistItem]:
        """Fetch user's Steam wishlist.

        Args:
            steam_id: Steam ID to fetch wishlist for.

        Returns:
            List of WishlistItem objects.
        """
        steam_id = steam_id or self.steam_id
        if not steam_id:
            raise SteamAPIError("Steam ID not provided.")

        url = f"{STEAM_API_BASE}/IWishlistService/GetWishlist/v1/"
        params = {
            "key": self.api_key,
            "steamid": steam_id,
        }

        try:
            response = self._http_client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            raise SteamAPIError(f"Failed to fetch wishlist: {e}")

        items = []
        for item_data in data.get("response", {}).get("items", []):
            app_id = item_data.get("appid")
            item = WishlistItem(
                id=f"steam_{app_id}",
                app_id=app_id,
                name=f"Unknown ({app_id})",  # Will be enriched later
                added_on=self._unix_to_datetime(item_data.get("date_added")),
                priority=item_data.get("priority", 0),
            )
            items.append(item)

        return items

    def get_price_info(self, app_id: int, country_code: str = "us") -> PriceInfo | None:
        """Fetch current price info for a game.

        Args:
            app_id: Steam application ID.
            country_code: Country code for pricing (e.g., 'us', 'gb', 'cn').

        Returns:
            PriceInfo or None if not available (e.g., free games).
        """
        url = f"{STEAM_STORE_API}/appdetails"
        params = {
            "appids": app_id,
            "cc": country_code,
            "filters": "price_overview",
        }

        try:
            response = self._http_client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        except Exception:
            return None

        app_data = data.get(str(app_id), {})
        if not app_data.get("success"):
            return None

        price_data = app_data.get("data", {}).get("price_overview")
        if not price_data:
            return None

        return PriceInfo(
            currency=price_data.get("currency", "USD"),
            initial_price=price_data.get("initial", 0) / 100,  # Convert cents to dollars
            final_price=price_data.get("final", 0) / 100,
            discount_percent=price_data.get("discount_percent", 0),
            formatted=price_data.get("final_formatted"),
        )

    def enrich_wishlist_item(
        self, item: WishlistItem, country_code: str = "us"
    ) -> WishlistItem:
        """Enrich a wishlist item with game details and price.

        Args:
            item: WishlistItem to enrich.
            country_code: Country code for pricing.

        Returns:
            Enriched WishlistItem.
        """
        try:
            # Get game details
            details = self.get_game_details(item.app_id)
            if details:
                item.name = details.get("name", item.name)
                item.description = details.get("short_description")
                item.genres = [g["description"] for g in details.get("genres", [])]
                item.header_image_url = details.get("header_image")

                # Release date
                release = details.get("release_date", {})
                if release.get("date") and not release.get("coming_soon"):
                    for fmt in ["%b %d, %Y", "%d %b, %Y", "%Y"]:
                        try:
                            item.release_date = datetime.strptime(release["date"], fmt)
                            break
                        except ValueError:
                            continue

            # Get price info
            item.price = self.get_price_info(item.app_id, country_code)
        except Exception:
            # Silently skip enrichment failures - item will have partial data
            pass

        return item

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
