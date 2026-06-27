import shutil
import ssl
import urllib.request
from html import unescape
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlparse, urlunparse

from flask import current_app

from ..db import get_db
from .spec_repository import import_spec_file

try:
    import certifi
except ImportError:  # pragma: no cover - optional until dependencies are installed
    certifi = None

DOWNLOAD_EXTENSIONS = (".zip", ".xlsx", ".xlsm", ".json", ".xml")
DISCOVERABLE_PATH_MARKERS = (
    "/file/mp/us/",
    "marketplace.walmartapis.com/aurora/v1/developer-portal/api/file/us/mp/",
)


def sync_configured_sources():
    db = get_db()
    started_at = _now()
    run = db.execute(
        "INSERT INTO sync_runs (started_at, status, message) VALUES (?, ?, ?)",
        (started_at, "running", "Sync started"),
    )
    db.commit()
    run_id = run.lastrowid
    downloaded = 0
    failed = 0
    messages = []
    try:
        sources = _expand_sources(current_app.config["SPEC_SOURCES"])
        for source in sources:
            try:
                path = _download(source)
                import_spec_file(path, name=source["name"], version=source.get("version"), source_url=source["url"])
                downloaded += 1
            except Exception as exc:  # noqa: BLE001 - keep syncing remaining public files
                failed += 1
                messages.append(f"{source['name']} skipped: {exc}")
        status = "success" if downloaded and not failed else "warning" if downloaded else "failed"
        message = (
            f"{downloaded} public file(s) cached from Walmart Developer Portal."
            if downloaded else
            "No public spec links were discovered. Use manual upload as a fallback."
        )
        if failed:
            message = f"{message} {failed} file(s) skipped. " + " ".join(messages[:3])
    except Exception as exc:  # noqa: BLE001 - recorded for UI troubleshooting
        status = "failed"
        message = str(exc)
    db.execute(
        "UPDATE sync_runs SET finished_at = ?, status = ?, message = ?, files_downloaded = ? WHERE id = ?",
        (_now(), status, message, downloaded, run_id),
    )
    db.commit()
    return latest_sync_run()


def latest_sync_run():
    return get_db().execute(
        "SELECT * FROM sync_runs ORDER BY started_at DESC, id DESC LIMIT 1"
    ).fetchone()


def sync_history(limit=20):
    return get_db().execute(
        "SELECT * FROM sync_runs ORDER BY started_at DESC, id DESC LIMIT ?", (limit,)
    ).fetchall()


def _expand_sources(sources):
    expanded = []
    for source in sources:
        if source.get("kind") == "index" or _looks_like_index(source["url"]):
            expanded.extend(_discover_sources(source))
        else:
            expanded.append(source)
    return _dedupe_sources(expanded)


def _discover_sources(source):
    request = urllib.request.Request(source["url"], headers={"User-Agent": "Walmart-Marketplace-Toolkit/1.0"})
    with urllib.request.urlopen(request, timeout=45, context=_ssl_context()) as response:
        html = response.read().decode("utf-8", errors="replace")
    html = unescape(html).replace("\\/", "/")
    links = []
    for match in __import__("re").finditer(r'href=["\']([^"\']+)["\']', html, flags=__import__("re").I):
        href = unquote(match.group(1).strip())
        if not _is_download_link(href):
            continue
        absolute_url = urljoin(source["url"], href)
        absolute_url = _safe_url(absolute_url)
        links.append({
            "name": _source_name(absolute_url),
            "url": absolute_url,
            "version": _version_from_url(absolute_url),
        })
    return links


def _download(source):
    cache_dir = Path(current_app.config["CACHE_DIR"])
    cache_dir.mkdir(parents=True, exist_ok=True)
    filename = unquote(source.get("filename") or urlparse(source["url"]).path.split("/")[-1] or f"{source['name']}.zip")
    target = cache_dir / filename
    request = urllib.request.Request(_safe_url(source["url"]), headers={"User-Agent": "Walmart-Marketplace-Toolkit/1.0"})
    with urllib.request.urlopen(request, timeout=45, context=_ssl_context()) as response, target.open("wb") as fh:
        shutil.copyfileobj(response, fh)
    return target


def _ssl_context():
    if certifi:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


def _looks_like_index(url):
    return "item-spec-versioning-and-diff-reporting" in url


def _is_download_link(href):
    lower = href.lower()
    return any(marker in lower for marker in DISCOVERABLE_PATH_MARKERS) and any(
        lower.split("?", 1)[0].endswith(extension) for extension in DOWNLOAD_EXTENSIONS
    )


def _dedupe_sources(sources):
    seen = set()
    deduped = []
    for source in sources:
        key = source["url"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(source)
    return deduped


def _source_name(url):
    filename = unquote(urlparse(url).path.split("/")[-1])
    return Path(filename).stem.replace("_", " ").replace("-", " ")


def _safe_url(url):
    parsed = urlparse(url)
    return urlunparse(parsed._replace(path=quote(unquote(parsed.path), safe="/:%")))


def _version_from_url(url):
    filename = unquote(urlparse(url).path.split("/")[-1])
    match = __import__("re").search(r"(\d{4}-\d{2}-\d{2}|v?\d+(?:\.\d+){1,3}(?:[.\-_]\d+)*)", filename, __import__("re").I)
    return match.group(1).replace("_", "-") if match else None


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
