"""Job sources: Bundesagentur, Arbeitnow, company career pages (companies.json) and Fraunhofer.

Each fetch_* returns a list of job dicts with id, title, company, location, remote, url, source, posted_at
and optionally text (the job description).
"""
import html
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET
from datetime import date

import httpx

from .utils import GERMANY, strip_html

BA_QUERIES = [
    "Werkstudent Software", "Werkstudent Informatik", "Werkstudent Data", "Werkstudent KI",
    "Werkstudent Machine Learning", "Werkstudent Entwicklung", "Werkstudent IT",
    "Praktikum Software", "Praktikum Informatik", "Praktikum Data", "Praktikum KI",
    "Praktikum Machine Learning", "Praktikum IT", "Working Student", "Internship Software",
]


def fetch_ba_query(client, query):
    url = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
    headers = {"X-API-Key": "jobboerse-jobsuche"}
    jobs = []
    for page in range(1, 6):
        r = client.get(url, headers=headers, params={"was": query, "size": 100, "page": page})
        r.raise_for_status()
        items = r.json().get("ergebnisliste", [])
        for j in items:
            if not j.get("stellenangebotsTitel"):
                continue
            loc = (j.get("stellenlokationen") or [{}])[0].get("adresse", {})
            jobs.append({
                "id": "ba:" + j["referenznummer"],
                "title": j["stellenangebotsTitel"],
                "company": j.get("firma", ""),
                "location": loc.get("ort", ""),
                "remote": int(bool(j.get("homeofficemoeglich"))),
                "url": "https://www.arbeitsagentur.de/jobsuche/jobdetail/" + j["referenznummer"],
                "source": "Bundesagentur",
                "posted_at": j.get("datumErsteVeroeffentlichung", ""),
            })
        if len(items) < 100:
            break
    return jobs


def fetch_ba(client, seen):
    with ThreadPoolExecutor(max_workers=5) as pool:
        return [job for jobs in pool.map(lambda q: fetch_ba_query(client, q), BA_QUERIES) for job in jobs]


def fetch_arbeitnow(client, seen):
    # Newest first: stop once a whole page is already seen. Keep partial results on 429.
    url = "https://www.arbeitnow.com/api/job-board-api"
    jobs = []
    try:
        for page in range(1, 21):
            r = client.get(url, params={"page": page})
            r.raise_for_status()
            body = r.json()
            page_jobs = [{
                "id": "arbeitnow:" + j["slug"],
                "title": j["title"],
                "company": j.get("company_name", ""),
                "location": j.get("location", ""),
                "remote": int(bool(j.get("remote"))),
                "url": j["url"],
                "source": "Arbeitnow",
                "posted_at": date.fromtimestamp(j["created_at"]).isoformat() if j.get("created_at") else "",
                "text": strip_html(j.get("description")),
            } for j in body.get("data", [])]
            jobs += page_jobs
            if all(job["id"] in seen for job in page_jobs) or not body.get("links", {}).get("next"):
                break
            time.sleep(3)
    except httpx.HTTPError as e:
        print(f"fetch_arbeitnow stopped early: {e}")
    return jobs


def fetch_greenhouse(client, slug):
    r = client.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", params={"content": "true"})
    r.raise_for_status()
    return [{
        "id": f"greenhouse:{slug}:{j['id']}",
        "title": j["title"],
        "company": j.get("company_name") or slug,
        "location": j["location"]["name"],
        "remote": int("remote" in j["location"]["name"].lower()),
        "url": j["absolute_url"],
        "source": "Greenhouse",
        "posted_at": (j.get("first_published") or j.get("updated_at") or "")[:10],
        "text": strip_html(j.get("content")),
    } for j in r.json()["jobs"] if GERMANY.search(j["location"]["name"])]


def fetch_lever(client, slug):
    r = client.get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"})
    r.raise_for_status()
    return [{
        "id": f"lever:{slug}:{j['id']}",
        "title": j["text"],
        "company": slug,
        "location": j["categories"].get("location", ""),
        "remote": int(j.get("workplaceType") == "remote"),
        "url": j["hostedUrl"],
        "source": "Lever",
        "posted_at": date.fromtimestamp(j["createdAt"] / 1000).isoformat(),
        "text": j.get("descriptionPlain", ""),
    } for j in r.json() if GERMANY.search(j["categories"].get("location", ""))]


def fetch_smartrecruiters(client, slug):
    jobs, offset = [], 0
    while True:
        r = client.get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings",
                       params={"country": "de", "limit": 100, "offset": offset})
        r.raise_for_status()
        body = r.json()
        jobs += [{
            "id": f"smartrecruiters:{slug}:{j['id']}",
            "title": j["name"],
            "company": j["company"]["name"],
            "location": j["location"].get("city", ""),
            "remote": int(bool(j["location"].get("remote"))),
            "url": f"https://jobs.smartrecruiters.com/{slug}/{j['id']}",
            "source": "SmartRecruiters",
            "posted_at": j.get("releasedDate", "")[:10],
        } for j in body["content"]]
        offset += 100
        if offset >= body["totalFound"]:
            return jobs


def fetch_personio(client, slug):
    # Personio feeds have no country field; companies in companies.json are assumed German.
    r = client.get(f"https://{slug}.jobs.personio.de/xml", follow_redirects=True)
    r.raise_for_status()
    jobs = []
    for p in ET.fromstring(r.content).iter("position"):
        office = p.findtext("office", "")
        jobs.append({
            "id": f"personio:{slug}:{p.findtext('id')}",
            "title": p.findtext("name", ""),
            "company": p.findtext("subcompany") or slug,
            "location": office,
            "remote": int("remote" in office.lower()),
            "url": f"https://{slug}.jobs.personio.de/job/{p.findtext('id')}",
            "source": "Personio",
            "posted_at": p.findtext("createdAt", "")[:10],
            "text": " ".join(strip_html(d.findtext("value")) for d in p.iter("jobDescription")),
        })
    return jobs


def fetch_ashby(client, slug):
    r = client.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    r.raise_for_status()
    jobs = []
    for j in r.json()["jobs"]:
        locations = [j.get("location", "")] + [l.get("location", "") for l in j.get("secondaryLocations", [])]
        country = (j.get("address") or {}).get("postalAddress", {}).get("addressCountry", "")
        if not GERMANY.search(" ".join(locations) + " " + country):
            continue
        jobs.append({
            "id": f"ashby:{slug}:{j['id']}",
            "title": j["title"],
            "company": slug,
            "location": ", ".join(l for l in locations if l),
            "remote": int(bool(j.get("isRemote"))),
            "url": j["jobUrl"],
            "source": "Ashby",
            "posted_at": (j.get("publishedAt") or "")[:10],
            "text": j.get("descriptionPlain", ""),
        })
    return jobs


ATS_FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "smartrecruiters": fetch_smartrecruiters,
    "personio": fetch_personio,
    "ashby": fetch_ashby,
}


def fetch_company_pages(client, seen):
    with open("companies.json") as f:
        companies = json.load(f)

    def fetch_one(ats, slug):
        try:
            return ATS_FETCHERS[ats](client, slug)
        except (httpx.HTTPError, ET.ParseError, KeyError) as e:
            print(f"{ats}/{slug} failed: {e}")
            return []

    tasks = [(ats, slug) for ats, slugs in companies.items() for slug in slugs]
    with ThreadPoolExecutor(max_workers=8) as pool:
        return [job for jobs in pool.map(lambda t: fetch_one(*t), tasks) for job in jobs]


FRAUNHOFER_QUERIES = [
    "Werkstudent", "Studentische Hilfskraft", "Hiwi", "Praktikum", "Praktikant", "Internship", "Working Student",
]


def fetch_fraunhofer_query(client, query):
    # Only /search/ pages: robots.txt disallows the /services/ RSS feed.
    jobs, start = [], 0
    while True:
        r = client.get("https://jobs.fraunhofer.de/search/", params={"q": query, "startrow": start})
        r.raise_for_status()
        for row in re.findall(r'<tr class="data-row">(.*?)</tr>', r.text, re.S):
            href, title = re.search(r'<a href="(/job/[^"]+)" class="jobTitle-link">([^<]+)</a>', row).groups()
            location = re.search(r'<span class="jobShifttype">([^<]*)</span>', row).group(1).strip()
            facility = html.unescape(re.search(r'<span class="jobFacility">([^<]*)</span>', row).group(1))
            jobs.append({
                "id": "fraunhofer:" + href.rstrip("/").rsplit("/", 1)[-1],
                "title": html.unescape(title).strip(),
                "company": "Fraunhofer " + facility.split(" - ")[0].strip(),
                "location": html.unescape(location),
                "remote": 0,
                "url": "https://jobs.fraunhofer.de" + href,
                "source": "Fraunhofer",
                "posted_at": "",
            })
        total = re.search(r"von <b>(\d+)</b>", r.text)
        start += 25
        if not total or start >= int(total.group(1)):
            return jobs
        time.sleep(0.5)


def fetch_fraunhofer(client, seen):
    with ThreadPoolExecutor(max_workers=4) as pool:
        return [job for jobs in pool.map(lambda q: fetch_fraunhofer_query(client, q), FRAUNHOFER_QUERIES) for job in jobs]
