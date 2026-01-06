"""FastAPI application for Homo Ludens web UI."""

from pathlib import Path

import markdown
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from homo_ludens.storage import Storage
from homo_ludens.web.routes import dashboard, library, chat, settings

# Paths
WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"


def render_markdown(text: str) -> str:
    """Convert markdown text to HTML."""
    return markdown.markdown(
        text,
        extensions=["fenced_code", "tables", "nl2br"],
    )


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Homo Ludens",
        description="Your personal AI game companion",
    )

    # Mount static files
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    # Set up templates
    templates = Jinja2Templates(directory=TEMPLATES_DIR)

    # Register custom filters
    templates.env.filters["markdown"] = render_markdown

    # Store templates and storage in app state for access in routes
    app.state.templates = templates
    app.state.storage = Storage()

    # Include routers
    app.include_router(dashboard.router)
    app.include_router(library.router)
    app.include_router(chat.router)
    app.include_router(settings.router)

    return app


app = create_app()
