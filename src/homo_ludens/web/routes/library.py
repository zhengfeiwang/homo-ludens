"""Library route - browse games."""

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Query

from homo_ludens.models import Platform


def _safe_datetime(dt: datetime | None) -> datetime:
    """Convert datetime to a comparable format (handles timezone-aware/naive mix)."""
    if dt is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

router = APIRouter(prefix="/library")


@router.get("")
async def library(
    request: Request,
    platform: str | None = Query(None, description="Filter by platform"),
    sort: str = Query("recent", description="Sort by: recent, playtime, name, completion"),
    search: str | None = Query(None, description="Search games"),
    show_unplayed: bool = Query(False, description="Show unplayed games"),
):
    """Render the library page."""
    templates = request.app.state.templates
    storage = request.app.state.storage
    profile = storage.load_profile()

    games = profile.games

    # Filter unplayed games first (this affects all counts)
    if not show_unplayed:
        games = [g for g in games if g.playtime_minutes > 0 or g.last_played]

    # Count by platform for filter UI (count from filtered games)
    platform_counts = {
        "all": len(games),
        "steam": len([g for g in games if g.platform == Platform.STEAM]),
        "playstation": len([g for g in games if g.platform == Platform.PLAYSTATION]),
        "xbox": len([g for g in games if g.platform == Platform.XBOX]),
    }

    # Filter by platform
    if platform:
        platform_map = {
            "steam": Platform.STEAM,
            "playstation": Platform.PLAYSTATION,
            "xbox": Platform.XBOX,
        }
        if platform in platform_map:
            games = [g for g in games if g.platform == platform_map[platform]]

    # Get display language for search (map zh to schinese for game names)
    display_language = os.getenv("DISPLAY_LANGUAGE", "en")
    game_name_language = "schinese" if display_language == "zh" else display_language

    # Search filter (search in both default name and localized name)
    if search:
        search_lower = search.lower()
        games = [g for g in games if search_lower in g.name.lower() or search_lower in g.get_name(game_name_language).lower()]

    # Sort
    if sort == "recent":
        # Put games with last_played first (sorted by date), then others
        with_date = [g for g in games if g.last_played]
        without_date = [g for g in games if not g.last_played]
        with_date.sort(key=lambda g: _safe_datetime(g.last_played), reverse=True)
        games = with_date + without_date
    elif sort == "playtime":
        games = sorted(games, key=lambda g: g.playtime_minutes, reverse=True)
    elif sort == "name":
        games = sorted(games, key=lambda g: g.name.lower())
    elif sort == "completion":
        # Sort by achievement completion percentage
        games = sorted(
            games,
            key=lambda g: g.achievement_stats.completion_percent if g.achievement_stats else 0,
            reverse=True,
        )

    # Check which platforms are configured
    has_steam = bool(os.getenv("STEAM_API_KEY") and os.getenv("STEAM_ID"))
    has_psn = bool(os.getenv("PSN_NPSSO_TOKEN"))
    has_xbox = bool(os.getenv("OPENXBL_API_KEY"))

    return templates.TemplateResponse(
        "library.html",
        {
            "request": request,
            "games": games,
            "platform": platform,
            "sort": sort,
            "search": search or "",
            "show_unplayed": show_unplayed,
            "platform_counts": platform_counts,
            "has_steam": has_steam,
            "has_psn": has_psn,
            "has_xbox": has_xbox,
            "display_language": game_name_language,
        },
    )


@router.get("/game/{game_id}")
async def game_detail(request: Request, game_id: str):
    """Render game detail modal/page."""
    templates = request.app.state.templates
    storage = request.app.state.storage
    profile = storage.load_profile()

    game = next((g for g in profile.games if g.id == game_id), None)

    if not game:
        return templates.TemplateResponse(
            "partials/game_not_found.html",
            {"request": request},
        )

    return templates.TemplateResponse(
        "partials/game_detail.html",
        {"request": request, "game": game},
    )
