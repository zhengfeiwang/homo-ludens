"""Sync routes - sync game libraries from platforms."""

import os

from fastapi import APIRouter, Request

from homo_ludens.models import Platform
from homo_ludens.steam import SteamClient, SteamAPIError
from homo_ludens.psn import PSNClient, PSNAPIError
from homo_ludens.xbox import XboxClient, XboxAPIError

router = APIRouter(prefix="/sync")


@router.post("/steam")
async def sync_steam(request: Request):
    """Sync Steam library."""
    templates = request.app.state.templates
    storage = request.app.state.storage

    # Check if configured
    if not os.getenv("STEAM_API_KEY") or not os.getenv("STEAM_ID"):
        return templates.TemplateResponse(
            "partials/sync_error.html",
            {"request": request, "error": "Steam not configured. Go to Settings to set up."},
        )

    try:
        client = SteamClient()
        games = client.get_owned_games()

        # Fetch achievements for played games (60+ min playtime)
        played_games = [g for g in games if g.playtime_minutes >= 60]
        for game in played_games:
            client.enrich_game_with_achievements(game)

        # Fetch localized names for played games if Chinese display is selected
        display_language = os.getenv("DISPLAY_LANGUAGE", "en")
        if display_language in ("zh", "schinese"):
            # Only fetch for games with some playtime to reduce API calls
            games_to_localize = [g for g in games if g.playtime_minutes > 0]
            for game in games_to_localize:
                client.enrich_game_with_localized_names(game)

        # Fetch wishlist
        wishlist_items = client.get_wishlist()
        for item in wishlist_items:
            client.enrich_wishlist_item(item)

        # Save to profile
        profile = storage.load_profile()
        # Remove existing Steam games and add new ones
        profile.games = [g for g in profile.games if g.platform != Platform.STEAM] + games
        profile.wishlist = wishlist_items
        profile.steam_id = client.steam_id
        storage.save_profile(profile)

        games_with_achievements = [
            g for g in games if g.progress and g.progress.total > 0
        ]
        on_sale = [item for item in wishlist_items if item.is_on_sale]

        return templates.TemplateResponse(
            "partials/sync_success.html",
            {
                "request": request,
                "platform": "Steam",
                "message": f"Synced {len(games)} games, {len(games_with_achievements)} with achievements, {len(wishlist_items)} wishlist items ({len(on_sale)} on sale)",
            },
        )

    except SteamAPIError as e:
        return templates.TemplateResponse(
            "partials/sync_error.html",
            {"request": request, "error": f"Steam sync failed: {e}"},
        )


@router.post("/psn")
async def sync_psn(request: Request):
    """Sync PlayStation library."""
    templates = request.app.state.templates
    storage = request.app.state.storage

    # Check if configured
    if not os.getenv("PSN_NPSSO_TOKEN"):
        return templates.TemplateResponse(
            "partials/sync_error.html",
            {"request": request, "error": "PlayStation not configured. Go to Settings to set up."},
        )

    try:
        client = PSNClient()
        games = client.get_owned_games()

        # Save to profile
        profile = storage.load_profile()
        # Remove existing PSN games and add new ones
        profile.games = [g for g in profile.games if g.platform != Platform.PLAYSTATION] + games
        profile.psn_online_id = client.online_id
        storage.save_profile(profile)

        games_with_trophies = [
            g for g in games if g.progress and g.progress.total > 0
        ]

        return templates.TemplateResponse(
            "partials/sync_success.html",
            {
                "request": request,
                "platform": "PlayStation",
                "message": f"Synced {len(games)} games, {len(games_with_trophies)} with trophies",
            },
        )

    except PSNAPIError as e:
        return templates.TemplateResponse(
            "partials/sync_error.html",
            {"request": request, "error": f"PlayStation sync failed: {e}"},
        )


@router.post("/xbox")
async def sync_xbox(request: Request):
    """Sync Xbox library."""
    templates = request.app.state.templates
    storage = request.app.state.storage

    # Check if configured
    if not os.getenv("OPENXBL_API_KEY"):
        return templates.TemplateResponse(
            "partials/sync_error.html",
            {"request": request, "error": "Xbox not configured. Go to Settings to set up."},
        )

    try:
        client = XboxClient()
        games = client.get_owned_games()

        # Save to profile
        profile = storage.load_profile()
        # Remove existing Xbox games and add new ones
        profile.games = [g for g in profile.games if g.platform != Platform.XBOX] + games
        profile.xbox_gamertag = client.gamertag
        storage.save_profile(profile)

        games_with_achievements = [
            g for g in games if g.progress and g.progress.total > 0
        ]

        return templates.TemplateResponse(
            "partials/sync_success.html",
            {
                "request": request,
                "platform": "Xbox",
                "message": f"Synced {len(games)} games, {len(games_with_achievements)} with achievements",
            },
        )

    except XboxAPIError as e:
        return templates.TemplateResponse(
            "partials/sync_error.html",
            {"request": request, "error": f"Xbox sync failed: {e}"},
        )


@router.post("/all")
async def sync_all(request: Request):
    """Sync all configured platforms."""
    templates = request.app.state.templates
    storage = request.app.state.storage
    profile = storage.load_profile()

    results = []
    errors = []

    # Get display language preference
    display_language = os.getenv("DISPLAY_LANGUAGE", "en")

    # Sync Steam if configured
    if os.getenv("STEAM_API_KEY") and os.getenv("STEAM_ID"):
        try:
            client = SteamClient()
            games = client.get_owned_games()

            played_games = [g for g in games if g.playtime_minutes >= 60]
            for game in played_games:
                client.enrich_game_with_achievements(game)

            # Fetch localized names for played games if Chinese display is selected
            if display_language in ("zh", "schinese"):
                games_to_localize = [g for g in games if g.playtime_minutes > 0]
                for game in games_to_localize:
                    client.enrich_game_with_localized_names(game)

            wishlist_items = client.get_wishlist()
            for item in wishlist_items:
                client.enrich_wishlist_item(item)

            profile.games = [g for g in profile.games if g.platform != Platform.STEAM] + games
            profile.wishlist = wishlist_items
            profile.steam_id = client.steam_id

            results.append(f"Steam: {len(games)} games")
        except SteamAPIError as e:
            errors.append(f"Steam: {e}")

    # Sync PSN if configured
    if os.getenv("PSN_NPSSO_TOKEN"):
        try:
            client = PSNClient()
            games = client.get_owned_games()

            profile.games = [g for g in profile.games if g.platform != Platform.PLAYSTATION] + games
            profile.psn_online_id = client.online_id

            results.append(f"PlayStation: {len(games)} games")
        except PSNAPIError as e:
            errors.append(f"PlayStation: {e}")

    # Sync Xbox if configured
    if os.getenv("OPENXBL_API_KEY"):
        try:
            client = XboxClient()
            games = client.get_owned_games()

            profile.games = [g for g in profile.games if g.platform != Platform.XBOX] + games
            profile.xbox_gamertag = client.gamertag

            results.append(f"Xbox: {len(games)} games")
        except XboxAPIError as e:
            errors.append(f"Xbox: {e}")

    # Save profile
    storage.save_profile(profile)

    if not results and not errors:
        return templates.TemplateResponse(
            "partials/sync_error.html",
            {"request": request, "error": "No platforms configured. Go to Settings to set up."},
        )

    if errors and not results:
        return templates.TemplateResponse(
            "partials/sync_error.html",
            {"request": request, "error": "; ".join(errors)},
        )

    message = ", ".join(results)
    if errors:
        message += f" (Errors: {'; '.join(errors)})"

    return templates.TemplateResponse(
        "partials/sync_success.html",
        {
            "request": request,
            "platform": "All platforms",
            "message": message,
        },
    )
