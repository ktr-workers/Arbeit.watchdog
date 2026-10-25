"""Scrape jobs into data/jobs.db, export web/public/jobs.json, and open a GitHub issue for new watched jobs.

Notifying needs env vars GITHUB_TOKEN and GITHUB_REPOSITORY (set by GitHub Actions) and NOTIFY
(GitHub username to @mention); it is skipped when GITHUB_TOKEN is unset, e.g. on local runs.
Run from the repo root: .venv/bin/python -m watchdog.main
"""
import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import httpx

from .sources import fetch_arbeitnow, fetch_ba, fetch_company_pages, fetch_fraunhofer
from .utils import dedupe_key, detect_lang, is_relevant, level_of

DB = "data/jobs.db"


def init_db(con):
    con.execute(
        """CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, title TEXT, company TEXT, location TEXT, remote INTEGER,
            url TEXT, source TEXT, level TEXT, posted_at TEXT, first_seen TEXT,
            status TEXT DEFAULT 'new', dedupe_key TEXT
        )"""
    )
    con.execute("CREATE TABLE IF NOT EXISTS seen (id TEXT PRIMARY KEY)")
    if "lang" not in [row[1] for row in con.execute("PRAGMA table_info(jobs)")]:
        con.execute("ALTER TABLE jobs ADD COLUMN lang TEXT")


def scrape(con):
    known = {row[0] for row in con.execute("SELECT dedupe_key FROM jobs")}
    seen = {row[0] for row in con.execute("SELECT id FROM seen")}
    today = date.today().isoformat()
    new = 0
    with httpx.Client(timeout=30, headers={"User-Agent": "personal-job-search/0.1"}) as client, \
            ThreadPoolExecutor() as pool:
        futures = {fetch.__name__: pool.submit(fetch, client, seen) for fetch in (fetch_ba, fetch_arbeitnow, fetch_company_pages, fetch_fraunhofer)}
        for name, future in futures.items():
            try:
                jobs = future.result()
            except httpx.HTTPError as e:
                print(f"{name} failed: {e}")
                continue
            con.executemany("INSERT OR IGNORE INTO seen (id) VALUES (?)", [(job["id"],) for job in jobs])
            for job in jobs:
                if not is_relevant(job["title"]):
                    continue
                # Fraunhofer titles don't reliably reflect the JD language.
                lang = "unknown" if job["source"] == "Fraunhofer" else detect_lang(job["title"] + " " + job.get("text", ""))
                con.execute("UPDATE jobs SET lang=? WHERE id=? AND lang IS NULL", (lang, job["id"]))
                key = dedupe_key(job)
                if key in known:
                    continue
                known.add(key)
                con.execute(
                    "INSERT OR IGNORE INTO jobs (id,title,company,location,remote,url,source,level,posted_at,first_seen,dedupe_key,lang)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (job["id"], job["title"], job["company"], job["location"], job["remote"], job["url"],
                     job["source"], level_of(job["title"]), job["posted_at"], today, key, lang),
                )
                new += 1
    # Jobs no longer listed (or not re-fetched) fall back to title-only detection.
    for job_id, title in con.execute("SELECT id, title FROM jobs WHERE lang IS NULL").fetchall():
        con.execute("UPDATE jobs SET lang=? WHERE id=?", (detect_lang(title), job_id))
    con.commit()
    total = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    print(f"{new} new jobs, {total} total in {DB}")


def export(con):
    """Write the jobs table to web/public/jobs.json for the Vercel dashboard."""
    cur = con.cursor()
    cur.row_factory = sqlite3.Row
    rows = cur.execute(
        "SELECT id, title, company, location, level, lang, remote, source, posted_at, first_seen, url"
        " FROM jobs ORDER BY posted_at DESC"
    )
    with open("web/public/jobs.json", "w") as f:
        json.dump([dict(r) for r in rows], f, ensure_ascii=False)


def notify(con):
    """Open a GitHub issue for new English-language jobs from data/watchlist.json companies."""
    if not os.environ.get("GITHUB_TOKEN"):
        print("watchdog: GITHUB_TOKEN not set, skipping notification")
        return
    with open("data/watchlist.json") as f:
        prefixes = [f"{ats}:{slug}:" for ats, slugs in json.load(f).items() for slug in slugs]
    con.execute("CREATE TABLE IF NOT EXISTS notified (id TEXT PRIMARY KEY)")
    rows = con.execute(
        "SELECT id, title, company, location, url FROM jobs WHERE lang='en' AND id NOT IN (SELECT id FROM notified)"
    ).fetchall()
    matches = [r for r in rows if r[0].startswith(tuple(prefixes))]
    if not matches:
        print("watchdog: no new watched jobs")
        return

    body = "\n".join(
        f"- [ ] **{title}** · {company} · {location} — [apply]({url.rstrip('/')}/apply)"
        for _, title, company, location, url in matches
    )
    r = httpx.post(
        f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/issues",
        headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json"},
        json={
            "title": f"{len(matches)} new watched job(s): " + ", ".join(sorted({r[2] for r in matches})),
            "body": f"@{os.environ['NOTIFY']}\n\n{body}",
        },
    )
    r.raise_for_status()

    con.executemany("INSERT INTO notified (id) VALUES (?)", [(r[0],) for r in matches])
    con.commit()
    print(f"watchdog: opened {r.json()['html_url']} for {len(matches)} job(s)")


def main():
    con = sqlite3.connect(DB)
    init_db(con)
    scrape(con)
    export(con)
    notify(con)


if __name__ == "__main__":
    main()
