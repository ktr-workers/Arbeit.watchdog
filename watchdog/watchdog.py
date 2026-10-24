"""Open a GitHub issue for new English-language jobs from watchlist.json companies. Run after watchdog.scraper.

GitHub emails the repo owner about the issue. Needs env vars GITHUB_TOKEN and GITHUB_REPOSITORY
(set by GitHub Actions) and NOTIFY (GitHub username to @mention).
Run from the repo root: .venv/bin/python -m watchdog.watchdog
"""
import json
import os
import sqlite3

import httpx

DB = "jobs.db"


def main():
    with open("watchlist.json") as f:
        prefixes = [f"{ats}:{slug}:" for ats, slugs in json.load(f).items() for slug in slugs]
    con = sqlite3.connect(DB)
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


if __name__ == "__main__":
    main()
