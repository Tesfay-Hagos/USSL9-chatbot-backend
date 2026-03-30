"""
ULSS9 Website Scraper Service

Crawls https://www.aulss9.veneto.it using the public sitemap, extracts clean
text with trafilatura, uploads one markdown file per page to the selected RAG
store via StoreManager, and records each page in the persistent scrape manifest.

Robots.txt rules respected:
  Disallowed: ?action=mys.print, mys.cerca, /mys/print, /mys/cerca,
              debug=mys*, decrem/increm/contrasta/solotesto/normaliz,
              medici.stampa, trasparenza.bando_stampa, trasparenza.concorso_stampa
  Allowed:    all other pages
"""

import asyncio
import hashlib
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

BASE_URL = "https://www.aulss9.veneto.it"
SITEMAP_URL = f"{BASE_URL}/index.cfm?action=mys.sitemap"
USER_AGENT = "Mozilla/5.0 ULSS9Bot/1.0 (official chatbot; +https://www.aulss9.veneto.it)"

# Minimum delay between requests per concurrent slot (seconds)
CRAWL_DELAY = 0.3
# Maximum concurrent HTTP requests
MAX_CONCURRENT = 5

# Single target store for all scraped content (overridable via start_scrape_job)
TARGET_STORE = "general"

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── URL skip rules (robots.txt + admin-only pages) ─────────────────────────────
_SKIP_ACTIONS: set[str] = {
    "trasparenza.bandi", "trasparenza.concorsi",
    "trasparenza.bando_stampa", "trasparenza.concorso_stampa",
    "mys.print", "mys.cerca",
}

_SKIP_PATTERNS: list[str] = [
    "mys.print", "mys.cerca", "debug=mys", "decrem=true", "increm=true",
    "contrasta=true", "solotesto=true", "normaliz=true",
    "medici.stampa", "trasparenza.bando_stampa", "trasparenza.concorso_stampa",
]


def _should_skip(url: str) -> bool:
    """Return True if this URL should be skipped (robots.txt / admin-only)."""
    m = re.search(r"action=([\w.]+)", url)
    if m and m.group(1) in _SKIP_ACTIONS:
        return True
    return any(p in url for p in _SKIP_PATTERNS)


# ── Topic classifier ───────────────────────────────────────────────────────────

_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "hours": [
        "orario", "orari", "apertura", "chiusura", "aperto", "chiuso",
        "lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica",
        "festivo", "prefestivo", "turno", "reperibilità", "guardia medica",
    ],
    "services": [
        "prestazione", "servizio", "prenotazione", "cup", "ricovero",
        "visita", "esame", "ambulatorio", "reparto", "specialistic",
        "ticket", "impegnativa", "esenzione", "screening",
    ],
    "locations": [
        "indirizzo", "via ", "piazza ", "viale ", "corso ", "sede",
        "ospedale", "poliambulatorio", "distretto", "presidio",
        "come raggiungere", "mappa", "percorso", "dove siamo",
    ],
    "contacts": [
        "telefono", "tel.", "fax", "email", "e-mail", "contatt",
        "riferimento", "numero verde", "call center", "urp",
        "segnalazione", "reclamo",
    ],
}


def classify_topic(text: str) -> str:
    """
    Classify a scraped page into one of: hours, services, locations, contacts, general.
    Uses simple keyword scoring — returns 'general' if no topic scores >= 2 hits.
    Lenient by design: homepage, news, org pages naturally fall into 'general'.
    """
    tl = text.lower()
    scores = {
        topic: sum(tl.count(kw) for kw in kws)
        for topic, kws in _TOPIC_KEYWORDS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] >= 2 else "general"


# ── Scrape job tracking ────────────────────────────────────────────────────────

@dataclass
class ScrapeJobStatus:
    job_id: str
    status: str = "running"       # running | done | cancelled | error
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str | None = None
    total_urls: int = 0
    scraped: int = 0              # pages successfully fetched this job
    skipped: int = 0              # pages skipped (robots / empty / no content)
    resumed: int = 0              # pages skipped because already in manifest (resume)
    uploaded: int = 0             # documents uploaded to Gemini
    errors: list[str] = field(default_factory=list)
    current_url: str = ""
    cancelled: bool = False
    target_store: str = "general"
    # Per-topic upload counts — keyed by topic name (hours/services/locations/contacts/general)
    store_counts: dict[str, int] = field(default_factory=dict)


# Module-level registry — survives the lifetime of the FastAPI process
_jobs: dict[str, ScrapeJobStatus] = {}


def get_job(job_id: str) -> ScrapeJobStatus | None:
    return _jobs.get(job_id)


def list_jobs() -> list[ScrapeJobStatus]:
    return list(_jobs.values())


def cancel_job(job_id: str) -> bool:
    job = _jobs.get(job_id)
    if job and job.status == "running":
        job.cancelled = True
        return True
    return False


# ── Sitemap fetching ───────────────────────────────────────────────────────────

async def fetch_sitemap(client) -> list[str]:
    """Return all allowed URLs from the ULSS9 sitemap."""
    resp = await client.get(SITEMAP_URL, headers={"User-Agent": USER_AGENT}, timeout=60)
    resp.raise_for_status()
    urls = re.findall(r"<loc>(.*?)</loc>", resp.text)
    # Unescape XML entities
    urls = [u.replace("&amp;", "&") for u in urls]
    # Remove duplicates, preserve order
    seen: set[str] = set()
    unique: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique


# ── Single-page scraping ───────────────────────────────────────────────────────

def _extract_html_content(html: str) -> str | None:
    """
    Extract the main content from ULSS9's ColdFusion CMS HTML.

    The site puts all citizen-facing content inside <div class="bdix_page">.
    Falls back to trafilatura for non-standard page layouts.
    """
    # 1. Site-specific: bdix_page is the primary content container on aulss9.veneto.it
    #    corpox pagecorp is used on action pages (farmacie, sedivaccini, etc.)
    m = None
    for css_cls in ("bdix_page", "corpox pagecorp"):
        m = re.search(
            rf'<div[^>]*class=["\']{css_cls}["\'"][^>]*>(.*?)(?=<div[^>]*class=["\'](?:collegate|blkcol|lastupd|votola|sinbar|footer|corpo\b)["\'])',
            html, re.DOTALL | re.IGNORECASE,
        )
        if m:
            break
    if m:
        chunk = m.group(1)
        try:
            from markdownify import markdownify as md
            text = md(chunk, heading_style="ATX", strip=["a", "img"])
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
            if len(text) >= 80:
                return text
        except Exception:
            pass

    # 2. Fallback: strip known nav/chrome divs then run trafilatura
    try:
        import trafilatura
        # Remove known non-content sections by class/id before trafilatura
        clean = re.sub(
            r'<div[^>]*(?:id|class)=["\'"](?:hdrnew|cssmenu|sinbar|footer_new|bbar|lnksopra|lnk_socials|cerca|votola|lastupd|collegate|blkcol|stringitore|corpo)["\'][^>]*>.*?</div>',
            "", html, flags=re.DOTALL | re.IGNORECASE,
        )
        text = trafilatura.extract(
            clean,
            output_format="markdown",
            include_comments=False,
            include_tables=True,
            no_fallback=False,
        )
        if text and len(text.strip()) >= 80:
            return text.strip()
    except Exception:
        pass

    return None


async def scrape_page(url: str, client) -> tuple[str, str] | None:
    """
    Fetch a page and return (title, markdown_text).
    Returns None if the page yields no usable content.
    """
    try:
        resp = await client.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
        if resp.status_code != 200:
            return None

        html = resp.text
        if not html.strip():
            return None

        text = _extract_html_content(html)
        if not text:
            return None

        # Extract title from <title> tag
        title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        raw_title = title_m.group(1) if title_m else ""
        # Strip " ULSS 9 Scaligera" suffix
        title = re.sub(r"\s*[|\-–]\s*ULSS\s*9.*$", "", raw_title, flags=re.IGNORECASE).strip()
        if not title:
            title = url.split("content_id=")[-1] if "content_id=" in url else url

        return title, text

    except Exception as e:
        logger.debug(f"scrape_page error for {url}: {e}")
        return None


# ── Per-page file naming ───────────────────────────────────────────────────────

def _page_filename(title: str, url: str) -> str:
    """
    Generate a unique, descriptive filename for a single scraped page.
    Uses title slug + URL hash suffix to guarantee uniqueness across collisions.
    """
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower())[:50].strip("_") or "page"
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"web_{slug}_{url_hash}.md"


def _page_markdown(url: str, title: str, text: str) -> str:
    return f"# {title}\n\n*Fonte: {url}*\n\n{text}\n"


# ── Main background job ────────────────────────────────────────────────────────

async def run_scrape_job(job_id: str, max_pages: int | None = None, target_store: str = "general") -> None:
    """
    Background coroutine: crawl the sitemap concurrently, upload one file per page.

    Architecture:
      - asyncio.Semaphore(MAX_CONCURRENT) limits concurrent HTTP requests
      - asyncio.Queue decouples crawling from Gemini uploads (uploads happen in
        a single background worker so crawling is never blocked waiting for Gemini)
      - Resume: already-scraped URLs (from manifest DB) are skipped up-front
    """
    import httpx

    from app.services import scrape_manifest
    from app.services.store_manager import StoreManager

    job = _jobs[job_id]
    store_manager = StoreManager()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    # Upload queue: items are (url, title, text, topic, content_hash) tuples.
    # None is the sentinel that tells the worker to exit.
    upload_queue: asyncio.Queue = asyncio.Queue()

    # ── Upload worker ──────────────────────────────────────────────────────────
    async def upload_worker() -> None:
        """Single background task: drains upload_queue and pushes docs to Gemini."""
        while True:
            item = await upload_queue.get()
            if item is None:  # sentinel — crawl phase complete
                upload_queue.task_done()
                break

            url, title, text, topic, _ = item
            filename = _page_filename(title, url)
            file_path = DATA_DIR / filename
            file_path.write_text(_page_markdown(url, title, text), encoding="utf-8")

            try:
                await store_manager.upload_document(
                    str(file_path),
                    target_store,
                    source_type="website",
                    title_override=title,
                    url=url,
                    custom_metadata=[
                        {"key": "topic",  "string_value": topic},
                        {"key": "source", "string_value": "web_scrape"},
                    ],
                )
                job.uploaded += 1
                job.store_counts[topic] = job.store_counts.get(topic, 0) + 1
                logger.info(f"[{job_id}] Uploaded {filename} → {target_store} [{topic}]")
                # Update the manifest row with the filename now that upload succeeded
                try:
                    await scrape_manifest.update_batch_file([url], filename)
                except Exception as me:
                    logger.warning(f"[{job_id}] Manifest batch_file update failed for {url}: {me}")
            except Exception as e:
                err = f"Upload failed for {filename}: {e}"
                logger.error(f"[{job_id}] {err}")
                job.errors.append(err)

            upload_queue.task_done()

    # ── Crawl task (one per URL) ───────────────────────────────────────────────
    async def crawl_one(url: str, client) -> None:
        if job.cancelled:
            return
        if _should_skip(url):
            job.skipped += 1
            return
        if url in scraped_url_set:
            job.resumed += 1
            return

        async with semaphore:
            if job.cancelled:
                return
            await asyncio.sleep(CRAWL_DELAY)
            job.current_url = url
            result = await scrape_page(url, client)

        if result is None:
            job.skipped += 1
            return

        title, text = result
        topic = classify_topic(text)
        content_hash = hashlib.md5(text.encode()).hexdigest()

        # Record to manifest immediately after scraping so that if the server
        # is killed before the upload queue drains, these URLs are not re-scraped
        # on the next run.  Upload status is tracked separately via job.uploaded.
        try:
            await scrape_manifest.record_scraped_page(
                url=url,
                title=title,
                content_hash=content_hash,
                char_count=len(text),
                batch_file=None,          # filled in by upload_worker once uploaded
                job_id=job_id,
            )
        except Exception as me:
            logger.warning(f"[{job_id}] Manifest record failed for {url}: {me}")

        await upload_queue.put((url, title, text, topic, content_hash))
        job.scraped += 1

    # ── Keep-alive ping (prevents Render free-tier sleep) ─────────────────────
    async def keep_alive() -> None:
        """
        Ping our own health endpoint every 8 minutes so Render's load balancer
        sees incoming traffic and doesn't spin down the server mid-scrape.
        Uses RENDER_EXTERNAL_URL (set automatically by Render) — no-op in local dev.
        """
        base = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
        if not base:
            return  # not on Render — skip
        ping_url = f"{base}/health"
        import httpx as _httpx
        while not job.cancelled and job.status == "running":
            await asyncio.sleep(8 * 60)  # 8 minutes
            if job.status != "running":
                break
            try:
                async with _httpx.AsyncClient(timeout=10) as _c:
                    await _c.get(ping_url)
                logger.debug(f"[{job_id}] Keep-alive ping sent to {ping_url}")
            except Exception:
                pass  # best-effort

    try:
        # 0. Load resume manifest — set of already-scraped URLs
        logger.info(f"[{job_id}] Loading scrape manifest for resume check…")
        try:
            scraped_url_set = await scrape_manifest.get_scraped_url_set()
            logger.info(f"[{job_id}] Manifest has {len(scraped_url_set)} previously scraped URLs")
        except Exception as e:
            logger.warning(f"[{job_id}] Could not load manifest: {e} — proceeding without resume")
            scraped_url_set = set()

        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            # 1. Fetch sitemap
            logger.info(f"[{job_id}] Fetching sitemap…")
            try:
                urls = await fetch_sitemap(client)
            except Exception as e:
                job.status = "error"
                job.errors.append(f"Sitemap fetch failed: {e}")
                job.finished_at = datetime.now(timezone.utc).isoformat()
                return

            if max_pages:
                urls = urls[:max_pages]

            job.total_urls = len(urls)
            logger.info(f"[{job_id}] {len(urls)} URLs to process (MAX_CONCURRENT={MAX_CONCURRENT})")

            # 2. Start upload worker + keep-alive ping
            worker_task = asyncio.create_task(upload_worker())
            keepalive_task = asyncio.create_task(keep_alive())

            # 3. Crawl all URLs concurrently (semaphore limits parallelism)
            crawl_tasks = [crawl_one(url, client) for url in urls]
            await asyncio.gather(*crawl_tasks, return_exceptions=True)

        # 4. Signal upload worker to finish and wait for queue to drain
        await upload_queue.put(None)
        await worker_task
        keepalive_task.cancel()

        job.status = "done" if not job.cancelled else "cancelled"

    except Exception as e:
        logger.error(f"[{job_id}] Fatal scrape error: {e}", exc_info=True)
        job.status = "error"
        job.errors.append(str(e))
        try:
            upload_queue.put_nowait(None)
        except Exception:
            pass
        try:
            keepalive_task.cancel()
        except Exception:
            pass
    finally:
        job.finished_at = datetime.now(timezone.utc).isoformat()
        job.current_url = ""
        logger.info(
            f"[{job_id}] Finished — status={job.status} "
            f"scraped={job.scraped} resumed={job.resumed} "
            f"uploaded={job.uploaded} skipped={job.skipped} "
            f"topics={job.store_counts}"
        )


def start_scrape_job(max_pages: int | None = None, target_store: str = "general") -> ScrapeJobStatus:
    """Create a new scrape job, register it, and schedule it as a background task."""
    job_id = uuid.uuid4().hex[:12]
    job = ScrapeJobStatus(job_id=job_id, target_store=target_store, store_counts={})
    _jobs[job_id] = job
    asyncio.create_task(run_scrape_job(job_id, max_pages=max_pages, target_store=target_store))
    return job


# ── Single-URL scrape (synchronous, awaitable) ─────────────────────────────────

async def scrape_single_url(url: str, target_store: str = "general") -> dict:
    """
    Scrape a single URL, upload it to the given Gemini store, and record it in
    the manifest — exactly as the full-site job does, but for one URL.

    Returns a dict with keys:
      status    "scraped" | "already_scraped" | "skipped" | "error"
      url       the requested URL
      title     page title (if scraped)
      filename  local .md filename (if scraped)
      topic     classified topic (if scraped)
      uploaded  bool — whether Gemini upload succeeded
      message   human-readable summary
    """
    import httpx

    from app.services import scrape_manifest
    from app.services.store_manager import StoreManager

    # 1. Skip if robots.txt rules disallow it
    if _should_skip(url):
        return {"status": "skipped", "url": url, "uploaded": False,
                "message": "URL is disallowed by robots.txt rules"}

    # 2. Skip if already in manifest (full-scrape will skip it too)
    scraped_url_set = await scrape_manifest.get_scraped_url_set()
    if url in scraped_url_set:
        return {"status": "already_scraped", "url": url, "uploaded": False,
                "message": "URL is already in the scrape manifest — will be skipped during full scrape"}

    # 3. Fetch and extract content
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            result = await scrape_page(url, client)
    except Exception as e:
        return {"status": "error", "url": url, "uploaded": False,
                "message": f"HTTP error: {e}"}

    if result is None:
        return {"status": "skipped", "url": url, "uploaded": False,
                "message": "Page yielded no usable content"}

    title, text = result
    topic = classify_topic(text)
    content_hash = hashlib.md5(text.encode()).hexdigest()
    filename = _page_filename(title, url)
    file_path = DATA_DIR / filename
    file_path.write_text(_page_markdown(url, title, text), encoding="utf-8")

    # 4. Upload to Gemini
    uploaded = False
    upload_error: str | None = None
    try:
        store_manager = StoreManager()
        await store_manager.upload_document(
            str(file_path),
            target_store,
            source_type="website",
            title_override=title,
            url=url,
            custom_metadata=[
                {"key": "topic",  "string_value": topic},
                {"key": "source", "string_value": "web_scrape"},
            ],
        )
        uploaded = True
        logger.info(f"[single-url] Uploaded {filename} → {target_store} [{topic}]")
    except Exception as e:
        upload_error = str(e)
        logger.error(f"[single-url] Upload failed for {filename}: {e}")

    # 5. Record in manifest regardless of upload outcome so full-scrape skips this URL
    try:
        await scrape_manifest.record_scraped_page(
            url=url,
            title=title,
            content_hash=content_hash,
            char_count=len(text),
            batch_file=filename,
            job_id="single_url",
        )
    except Exception as me:
        logger.warning(f"[single-url] Manifest record failed for {url}: {me}")

    return {
        "status": "scraped",
        "url": url,
        "title": title,
        "filename": filename,
        "topic": topic,
        "uploaded": uploaded,
        "message": "OK" if uploaded else f"Scraped but upload failed: {upload_error}",
    }
