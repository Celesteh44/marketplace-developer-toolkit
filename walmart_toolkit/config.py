import json
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    DEFAULT_SPEC_INDEX_URL = (
        "https://developer.walmart.com/us-marketplace/docs/"
        "item-spec-versioning-and-diff-reporting"
    )
    SECRET_KEY = os.environ.get("SECRET_KEY", "local-dev-only")
    DATA_DIR = Path(os.environ.get("WMT_TOOLKIT_DATA_DIR", BASE_DIR / "instance"))
    CACHE_DIR = DATA_DIR / "spec_cache"
    DATABASE = DATA_DIR / "walmart_toolkit.sqlite3"
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024

    RAW_SPEC_SOURCES = os.environ.get("WALMART_SPEC_SOURCES_JSON", "[]")

    @classmethod
    def spec_sources(cls):
        try:
            parsed = json.loads(cls.RAW_SPEC_SOURCES)
        except json.JSONDecodeError:
            parsed = []
        sources = [
            source for source in parsed
            if isinstance(source, dict) and source.get("name") and source.get("url")
        ]
        if not sources:
            sources = [
                {
                    "name": "Walmart item spec versioning index",
                    "url": cls.DEFAULT_SPEC_INDEX_URL,
                    "kind": "index",
                }
            ]
        return sources
