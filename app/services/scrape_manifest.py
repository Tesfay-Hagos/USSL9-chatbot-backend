"""
Scrape Manifest Service

Persistent URL-level tracking for the web scraper.
Enables:
  - Resume on restart: skip already-scraped URLs
  - Coverage reporting: how many of 1871 pages have been scraped
  - Content audit: inspect individual scraped pages by URL
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import delete, func, select

from app.core.database import get_db
from app.core.models import ScrapedPageRecord

logger = logging.getLogger(__name__)


async def get_scraped_url_set() -> set[str]:
    """Return a set of all URLs that have been successfully scraped.
    Called once at job start to build the resume skip-set (O(1) lookup per URL)."""
    async with get_db() as db:
        result = await db.execute(select(ScrapedPageRecord.url))
        return set(result.scalars().all())


async def record_scraped_page(
    url: str,
    title: str | None,
    content_hash: str,
    char_count: int,
    batch_file: str | None,
    job_id: str,
) -> None:
    """Insert or update a scraped page record."""
    async with get_db() as db:
        existing = await db.get(ScrapedPageRecord, url)
        if existing:
            existing.title = title
            existing.content_hash = content_hash
            existing.char_count = char_count
            existing.batch_file = batch_file
            existing.job_id = job_id
            existing.scraped_at = datetime.now(timezone.utc)
        else:
            db.add(ScrapedPageRecord(
                url=url,
                title=title,
                content_hash=content_hash,
                char_count=char_count,
                batch_file=batch_file,
                job_id=job_id,
                scraped_at=datetime.now(timezone.utc),
            ))


async def update_batch_file(urls: list[str], batch_file: str) -> None:
    """Set batch_file on a list of URLs once their batch has been uploaded."""
    if not urls:
        return
    async with get_db() as db:
        for url in urls:
            rec = await db.get(ScrapedPageRecord, url)
            if rec:
                rec.batch_file = batch_file


async def get_manifest_stats() -> dict:
    """Return coverage statistics for the admin dashboard."""
    async with get_db() as db:
        total = (await db.execute(select(func.count()).select_from(ScrapedPageRecord))).scalar_one()
        total_chars = (await db.execute(select(func.sum(ScrapedPageRecord.char_count)))).scalar_one() or 0
        last_row = (await db.execute(
            select(ScrapedPageRecord.scraped_at)
            .order_by(ScrapedPageRecord.scraped_at.desc())
            .limit(1)
        )).scalar_one_or_none()
        jobs_result = await db.execute(
            select(ScrapedPageRecord.job_id, func.count().label("cnt"))
            .group_by(ScrapedPageRecord.job_id)
            .order_by(func.count().desc())
        )
        jobs = [{"job_id": r.job_id, "count": r.cnt} for r in jobs_result]

    return {
        "total_scraped": total,
        "total_sitemap_urls": 1871,
        "coverage_pct": round(total / 1871 * 100, 1) if total else 0.0,
        "total_chars": total_chars,
        "last_scraped_at": last_row.isoformat() if last_row else None,
        "jobs": jobs[:5],
    }


async def get_sample_pages(limit: int = 30, offset: int = 0) -> list[dict]:
    """Return a paginated sample of scraped page records for content audit."""
    async with get_db() as db:
        result = await db.execute(
            select(ScrapedPageRecord)
            .order_by(ScrapedPageRecord.scraped_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = result.scalars().all()
    return [
        {
            "url": r.url,
            "title": r.title,
            "char_count": r.char_count,
            "content_hash": r.content_hash,
            "batch_file": r.batch_file,
            "job_id": r.job_id,
            "scraped_at": r.scraped_at.isoformat() if r.scraped_at else None,
        }
        for r in rows
    ]


async def reset_manifest() -> int:
    """Delete all scraped page records (allow full re-scrape). Returns count deleted."""
    async with get_db() as db:
        result = await db.execute(delete(ScrapedPageRecord))
        return result.rowcount
