"""Dashboard route - main overview page."""

from datetime import datetime, timezone

from fastapi import APIRouter, Request

from homo_ludens.models import Platform

router = APIRouter()


def _safe_datetime(dt: datetime | None) -> datetime:
    """Convert datetime to timezone-aware for comparison, handling None."""
    if dt is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@router.get("/")
async def dashboard(request: Request):
    """Render the dashboard page."""
    templates = request.app.state.templates
    storage = request.app.state.storage
    profile = storage.load_profile()

    # Calculate stats
    steam_games = [g for g in profile.games if g.platform == Platform.STEAM]
    psn_games = [g for g in profile.games if g.platform == Platform.PLAYSTATION]
    xbox_games = [g for g in profile.games if g.platform == Platform.XBOX]

    total_playtime_hours = sum(g.playtime_minutes for g in profile.games) // 60
    played_count = len([g for g in profile.games if g.playtime_minutes > 0 or g.last_played])
    
    # Achievement stats
    games_with_ach = [g for g in profile.games if g.achievement_stats and g.achievement_stats.total > 0]
    total_ach = sum(g.achievement_stats.total for g in games_with_ach if g.achievement_stats)
    unlocked_ach = sum(g.achievement_stats.unlocked for g in games_with_ach if g.achievement_stats)
    
    # Recently played
    recent_games = [g for g in profile.games if g.last_played]
    recent_games.sort(key=lambda g: _safe_datetime(g.last_played), reverse=True)
    recent_games = recent_games[:5]

    # Wishlist on sale
    on_sale = [item for item in profile.wishlist if item.is_on_sale][:5]

    stats = {
        "total_games": len(profile.games),
        "steam_games": len(steam_games),
        "psn_games": len(psn_games),
        "xbox_games": len(xbox_games),
        "total_playtime_hours": total_playtime_hours,
        "played_count": played_count,
        "unplayed_count": len(profile.games) - played_count,
        "total_achievements": total_ach,
        "unlocked_achievements": unlocked_ach,
        "achievement_percent": round(unlocked_ach / total_ach * 100, 1) if total_ach > 0 else 0,
    }

    platforms = {
        "steam": {
            "connected": profile.steam_id is not None,
            "id": profile.steam_id,
            "game_count": len(steam_games),
        },
        "playstation": {
            "connected": profile.psn_online_id is not None,
            "id": profile.psn_online_id,
            "game_count": len(psn_games),
        },
        "xbox": {
            "connected": profile.xbox_gamertag is not None,
            "id": profile.xbox_gamertag,
            "game_count": len(xbox_games),
        },
    }

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
            "platforms": platforms,
            "recent_games": recent_games,
            "on_sale": on_sale,
        },
    )
