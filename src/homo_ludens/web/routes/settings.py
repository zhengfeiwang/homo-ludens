"""Settings route - platform configuration."""

import os

from fastapi import APIRouter, Request, Form
from dotenv import set_key

from homo_ludens.storage import Storage

router = APIRouter(prefix="/settings")

# Config file path
from pathlib import Path
ENV_FILE = Path.home() / ".homo_ludens" / ".env"


@router.get("")
async def settings_page(request: Request):
    """Render the settings page."""
    templates = request.app.state.templates
    storage = request.app.state.storage
    profile = storage.load_profile()

    config = {
        "steam": {
            "api_key": bool(os.getenv("STEAM_API_KEY")),
            "steam_id": os.getenv("STEAM_ID"),
            "connected": profile.steam_id is not None,
            "profile_id": profile.steam_id,
        },
        "playstation": {
            "token": bool(os.getenv("PSN_NPSSO_TOKEN")),
            "connected": profile.psn_online_id is not None,
            "profile_id": profile.psn_online_id,
        },
        "xbox": {
            "api_key": bool(os.getenv("OPENXBL_API_KEY")),
            "connected": profile.xbox_gamertag is not None,
            "profile_id": profile.xbox_gamertag,
        },
        "llm": {
            "azure_configured": bool(os.getenv("AZURE_OPENAI_API_KEY")),
            "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
            "endpoint": os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            "deployment": os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini"),
        },
        "display": {
            "language": os.getenv("DISPLAY_LANGUAGE", "en"),
        },
    }

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "config": config,
        },
    )


@router.post("/steam")
async def save_steam_config(
    request: Request,
    api_key: str = Form(""),
    steam_id: str = Form(""),
):
    """Save Steam configuration."""
    templates = request.app.state.templates

    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENV_FILE.touch(exist_ok=True)

    if api_key.strip():
        set_key(str(ENV_FILE), "STEAM_API_KEY", api_key.strip())
    if steam_id.strip():
        set_key(str(ENV_FILE), "STEAM_ID", steam_id.strip())

    return templates.TemplateResponse(
        "partials/settings_saved.html",
        {"request": request, "platform": "Steam"},
    )


@router.post("/playstation")
async def save_psn_config(
    request: Request,
    npsso_token: str = Form(""),
):
    """Save PlayStation configuration."""
    templates = request.app.state.templates

    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENV_FILE.touch(exist_ok=True)

    if npsso_token.strip():
        set_key(str(ENV_FILE), "PSN_NPSSO_TOKEN", npsso_token.strip())

    return templates.TemplateResponse(
        "partials/settings_saved.html",
        {"request": request, "platform": "PlayStation"},
    )


@router.post("/xbox")
async def save_xbox_config(
    request: Request,
    api_key: str = Form(""),
):
    """Save Xbox configuration."""
    templates = request.app.state.templates

    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENV_FILE.touch(exist_ok=True)

    if api_key.strip():
        set_key(str(ENV_FILE), "OPENXBL_API_KEY", api_key.strip())

    return templates.TemplateResponse(
        "partials/settings_saved.html",
        {"request": request, "platform": "Xbox"},
    )


@router.post("/display")
async def save_display_config(
    request: Request,
    language: str = Form("en"),
):
    """Save display settings."""
    templates = request.app.state.templates

    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENV_FILE.touch(exist_ok=True)

    # Validate language choice and map to internal codes
    # UI uses 'zh' but Steam API uses 'schinese' for game localization
    valid_languages = ["en", "zh"]
    if language in valid_languages:
        set_key(str(ENV_FILE), "DISPLAY_LANGUAGE", language)
        # Update the environment variable immediately
        os.environ["DISPLAY_LANGUAGE"] = language

    return templates.TemplateResponse(
        "partials/settings_saved.html",
        {"request": request, "platform": "Display"},
    )
