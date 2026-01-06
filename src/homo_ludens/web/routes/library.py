"""Library route - browse games."""

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
):
    """Render the library page."""
    templates = request.app.state.templates
    storage = request.app.state.storage
    profile = storage.load_profile()

    games = profile.games

    # Filter by platform
    if platform:
        platform_map = {
            "steam": Platform.STEAM,
            "playstation": Platform.PLAYSTATION,
            "xbox": Platform.XBOX,
        }
        if platform in platform_map:
            games = [g for g in games if g.platform == platform_map[platform]]

    # Search filter
    if search:
        search_lower = search.lower()
        games = [g for g in games if search_lower in g.name.lower()]

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

    # Count by platform for filter UI
    platform_counts = {
        "all": len(profile.games),
        "steam": len([g for g in profile.games if g.platform == Platform.STEAM]),
        "playstation": len([g for g in profile.games if g.platform == Platform.PLAYSTATION]),
        "xbox": len([g for g in profile.games if g.platform == Platform.XBOX]),
    }

    return templates.TemplateResponse(
        "library.html",
        {
            "request": request,
            "games": games,
            "platform": platform,
            "sort": sort,
            "search": search or "",
            "platform_counts": platform_counts,
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
