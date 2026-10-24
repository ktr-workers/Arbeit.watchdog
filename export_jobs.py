"""Export jobs.db to web/public/jobs.json for the Vercel dashboard. Run after scraper.py."""
import json
import sqlite3

con = sqlite3.connect("jobs.db")
con.row_factory = sqlite3.Row
rows = con.execute(
    "SELECT id, title, company, location, level, lang, remote, source, posted_at, first_seen, url"
    " FROM jobs ORDER BY posted_at DESC"
)
with open("web/public/jobs.json", "w") as f:
    json.dump([dict(r) for r in rows], f, ensure_ascii=False)
