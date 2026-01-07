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
from psnawp_api.models.trophies.trophy_constants import TrophyType

from homo_ludens.models import (
    Game,
    Platform,
    TrophyTier,
    RarityTier,
    PlayStationTrophy,
    PlayStationProgressStats,
    percent_to_rarity_tier,
)


class PSNAPIError(Exception):
    """Error from PlayStation Network API."""

    pass


def _map_trophy_type_to_tier(trophy_type: TrophyType) -> TrophyTier:
    """Convert psnawp TrophyType to our TrophyTier enum."""
    mapping = {
        TrophyType.BRONZE: TrophyTier.BRONZE,
        TrophyType.SILVER: TrophyTier.SILVER,
        TrophyType.GOLD: TrophyTier.GOLD,
        TrophyType.PLATINUM: TrophyTier.PLATINUM,
    }
    return mapping.get(trophy_type, TrophyTier.BRONZE)


def _map_psn_rarity_to_tier(rarity_value: str | None) -> RarityTier | None:
    """Convert PSN rarity string to our RarityTier enum."""
    if rarity_value is None:
        return None
    rarity_lower = str(rarity_value).lower()
    if "ultra" in rarity_lower:
        return RarityTier.ULTRA_RARE
    elif "very" in rarity_lower:
        return RarityTier.VERY_RARE
    elif "rare" in rarity_lower:
        return RarityTier.RARE
    elif "uncommon" in rarity_lower:
        return RarityTier.UNCOMMON
    else:
        return RarityTier.COMMON


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

                # Build trophy stats
                if trophy_title.defined_trophies:
                    bronze_total = trophy_title.defined_trophies.bronze
                    silver_total = trophy_title.defined_trophies.silver
                    gold_total = trophy_title.defined_trophies.gold
                    platinum_total = trophy_title.defined_trophies.platinum
                    total = bronze_total + silver_total + gold_total + platinum_total

                    bronze_unlocked = 0
                    silver_unlocked = 0
                    gold_unlocked = 0
                    platinum_unlocked = 0
                    if trophy_title.earned_trophies:
                        bronze_unlocked = trophy_title.earned_trophies.bronze
                        silver_unlocked = trophy_title.earned_trophies.silver
                        gold_unlocked = trophy_title.earned_trophies.gold
                        platinum_unlocked = trophy_title.earned_trophies.platinum
                    unlocked = bronze_unlocked + silver_unlocked + gold_unlocked + platinum_unlocked

                    # Fetch individual trophies with progress
                    trophies = []
                    raw_data = {
                        "defined_trophies": {
                            "bronze": bronze_total,
                            "silver": silver_total,
                            "gold": gold_total,
                            "platinum": platinum_total,
                        },
                        "earned_trophies": {
                            "bronze": bronze_unlocked,
                            "silver": silver_unlocked,
                            "gold": gold_unlocked,
                            "platinum": platinum_unlocked,
                        },
                        "progress": trophy_title.progress,
                    }

                    try:
                        # Get platform for trophy fetch
                        platform = None
                        if trophy_title.title_platform:
                            platform = list(trophy_title.title_platform)[0]
                        
                        if platform:
                            trophy_list = list(self._client.trophies(
                                np_communication_id=trophy_title.np_communication_id,
                                platform=platform,
                                include_progress=True,
                            ))
                            
                            for trophy in trophy_list:
                                # Parse rarity percentage from string
                                rarity_percent = None
                                if hasattr(trophy, 'trophy_earn_rate') and trophy.trophy_earn_rate:
                                    try:
                                        rarity_percent = float(trophy.trophy_earn_rate)
                                    except (ValueError, TypeError):
                                        pass

                                # Get rarity tier from PSN or calculate from percentage
                                rarity_tier = None
                                if hasattr(trophy, 'trophy_rarity') and trophy.trophy_rarity:
                                    rarity_tier = _map_psn_rarity_to_tier(str(trophy.trophy_rarity.name))
                                if rarity_tier is None and rarity_percent is not None:
                                    rarity_tier = percent_to_rarity_tier(rarity_percent)

                                ps_trophy = PlayStationTrophy(
                                    trophy_id=trophy.trophy_id,
                                    name=trophy.trophy_name,
                                    description=trophy.trophy_detail,
                                    icon_url=getattr(trophy, 'trophy_icon_url', None),
                                    tier=_map_trophy_type_to_tier(trophy.trophy_type),
                                    achieved=getattr(trophy, 'earned', False) or False,
                                    unlock_time=getattr(trophy, 'earned_date_time', None),
                                    rarity_percent=rarity_percent,
                                    rarity_tier=rarity_tier,
                                )
                                trophies.append(ps_trophy)
                    except Exception:
                        # Failed to fetch individual trophies, continue with counts only
                        pass

                    game.progress = PlayStationProgressStats(
                        total=total,
                        unlocked=unlocked,
                        bronze_total=bronze_total,
                        bronze_unlocked=bronze_unlocked,
                        silver_total=silver_total,
                        silver_unlocked=silver_unlocked,
                        gold_total=gold_total,
                        gold_unlocked=gold_unlocked,
                        platinum_total=platinum_total,
                        platinum_unlocked=platinum_unlocked,
                        trophies=trophies,
                        raw_data=raw_data,
                    )

                games.append(game)

        except PSNAWPNotFoundError:
            # User has no trophy titles
            pass
        except Exception as e:
            raise PSNAPIError(f"Failed to fetch PSN games: {e}")

        return games

    def get_game_trophies(self, np_communication_id: str) -> PlayStationProgressStats | None:
        """Fetch detailed trophy info for a specific game.

        Args:
            np_communication_id: The game's trophy communication ID.

        Returns:
            PlayStationProgressStats with individual trophies, or None if not found.
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

            # Get platform
            platform = None
            if trophy_title.title_platform:
                platform = list(trophy_title.title_platform)[0]
            
            if not platform:
                return None

            # Get individual trophies with progress
            trophies = []
            trophy_list = list(self._client.trophies(
                np_communication_id=np_communication_id,
                platform=platform,
                include_progress=True,
            ))

            # Count by tier
            tier_counts = {
                TrophyTier.BRONZE: {"total": 0, "unlocked": 0},
                TrophyTier.SILVER: {"total": 0, "unlocked": 0},
                TrophyTier.GOLD: {"total": 0, "unlocked": 0},
                TrophyTier.PLATINUM: {"total": 0, "unlocked": 0},
            }

            for trophy in trophy_list:
                tier = _map_trophy_type_to_tier(trophy.trophy_type)
                tier_counts[tier]["total"] += 1
                
                achieved = getattr(trophy, 'earned', False) or False
                if achieved:
                    tier_counts[tier]["unlocked"] += 1

                # Parse rarity
                rarity_percent = None
                if hasattr(trophy, 'trophy_earn_rate') and trophy.trophy_earn_rate:
                    try:
                        rarity_percent = float(trophy.trophy_earn_rate)
                    except (ValueError, TypeError):
                        pass

                rarity_tier = None
                if hasattr(trophy, 'trophy_rarity') and trophy.trophy_rarity:
                    rarity_tier = _map_psn_rarity_to_tier(str(trophy.trophy_rarity.name))
                if rarity_tier is None and rarity_percent is not None:
                    rarity_tier = percent_to_rarity_tier(rarity_percent)

                ps_trophy = PlayStationTrophy(
                    trophy_id=trophy.trophy_id,
                    name=trophy.trophy_name,
                    description=trophy.trophy_detail,
                    icon_url=getattr(trophy, 'trophy_icon_url', None),
                    tier=tier,
                    achieved=achieved,
                    unlock_time=getattr(trophy, 'earned_date_time', None),
                    rarity_percent=rarity_percent,
                    rarity_tier=rarity_tier,
                )
                trophies.append(ps_trophy)

            total = len(trophies)
            unlocked = len([t for t in trophies if t.achieved])

            return PlayStationProgressStats(
                total=total,
                unlocked=unlocked,
                bronze_total=tier_counts[TrophyTier.BRONZE]["total"],
                bronze_unlocked=tier_counts[TrophyTier.BRONZE]["unlocked"],
                silver_total=tier_counts[TrophyTier.SILVER]["total"],
                silver_unlocked=tier_counts[TrophyTier.SILVER]["unlocked"],
                gold_total=tier_counts[TrophyTier.GOLD]["total"],
                gold_unlocked=tier_counts[TrophyTier.GOLD]["unlocked"],
                platinum_total=tier_counts[TrophyTier.PLATINUM]["total"],
                platinum_unlocked=tier_counts[TrophyTier.PLATINUM]["unlocked"],
                trophies=trophies,
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
