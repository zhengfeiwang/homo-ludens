"""Internationalization (i18n) support for the web UI."""

import json
import os
from pathlib import Path
from typing import Any

# Directory containing translation files
I18N_DIR = Path(__file__).parent / "i18n"

# Supported languages
SUPPORTED_LANGUAGES = {
    "en": "English",
    "zh": "简体中文",
}

# Default language
DEFAULT_LANGUAGE = "en"

# Cache for loaded translations
_translations_cache: dict[str, dict[str, Any]] = {}


def load_translations(language: str) -> dict[str, Any]:
    """Load translations for a specific language.
    
    Args:
        language: Language code (e.g., 'en', 'zh')
        
    Returns:
        Dictionary of translations
    """
    if language in _translations_cache:
        return _translations_cache[language]
    
    translation_file = I18N_DIR / f"{language}.json"
    
    if not translation_file.exists():
        # Fall back to default language
        translation_file = I18N_DIR / f"{DEFAULT_LANGUAGE}.json"
    
    try:
        with open(translation_file, "r", encoding="utf-8") as f:
            translations = json.load(f)
            _translations_cache[language] = translations
            return translations
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def get_text(key: str, language: str = DEFAULT_LANGUAGE, **kwargs) -> str:
    """Get translated text for a key.
    
    Args:
        key: Translation key (supports dot notation like 'nav.dashboard')
        language: Language code
        **kwargs: Format arguments for string interpolation
        
    Returns:
        Translated string, or the key itself if not found
    """
    translations = load_translations(language)
    
    # Support dot notation for nested keys
    keys = key.split(".")
    value = translations
    
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            # Key not found, return the key itself
            return key
    
    if isinstance(value, str):
        # Support string interpolation
        if kwargs:
            try:
                return value.format(**kwargs)
            except KeyError:
                return value
        return value
    
    return key


def get_current_language() -> str:
    """Get the current display language from environment."""
    lang = os.getenv("DISPLAY_LANGUAGE", DEFAULT_LANGUAGE)
    # Map schinese to zh for consistency
    if lang == "schinese":
        return "zh"
    return lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def create_translator(language: str | None = None):
    """Create a translator function for templates.
    
    Args:
        language: Language code, or None to use current language
        
    Returns:
        A function that translates keys
    """
    lang = language or get_current_language()
    
    def translate(key: str, **kwargs) -> str:
        return get_text(key, lang, **kwargs)
    
    return translate
