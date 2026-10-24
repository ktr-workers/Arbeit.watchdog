"""Email new English-language jobs from watchlist.json companies. Run after scraper.py.

Needs env vars SMTP_USER, SMTP_PASSWORD (Gmail app password) and EMAIL_TO.
Run: .venv/bin/python watchdog.py
"""
import json
import os
import smtplib
import sqlite3
from email.message import EmailMessage

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

    msg = EmailMessage()
    msg["Subject"] = f"{len(matches)} new watched job(s): " + ", ".join(sorted({r[2] for r in matches}))
    msg["From"] = os.environ["SMTP_USER"]
    msg["To"] = os.environ["EMAIL_TO"]
    msg.set_content("\n\n".join(
        f"{title}\n{company} · {location}\nApply: {url.rstrip('/')}/apply" for _, title, company, location, url in matches
    ))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        smtp.send_message(msg)

    con.executemany("INSERT INTO notified (id) VALUES (?)", [(r[0],) for r in matches])
    con.commit()
    print(f"watchdog: emailed {len(matches)} job(s)")


if __name__ == "__main__":
    main()
