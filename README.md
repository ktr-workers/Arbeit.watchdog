# Arbeit.watchdog

Collects Werkstudent / internship tech jobs in Germany and watches selected companies for new English-language postings.

**Dashboard:** https://arbeit-watchdog.vercel.app/

- `scraper.py` fills `jobs.db` from the Bundesagentur, Arbeitnow, company career pages (`companies.json`) and Fraunhofer.
- `watchdog.py` opens a GitHub issue (which GitHub emails to you) for new English jobs from `watchlist.json` companies.
- `export_jobs.py` writes `web/public/jobs.json` for the dashboard in `web/` (Next.js on Vercel).
- `.github/workflows/scrape.yml` runs all three at 09:00 and 18:00 Berlin time and commits the results.
- Statuses set on the dashboard are saved to `statuses.json` via the GitHub API (passphrase required).
