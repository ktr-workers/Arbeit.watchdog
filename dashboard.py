"""Run: .venv/bin/streamlit run dashboard.py

jobs.db is updated by GitHub Actions; statuses are kept locally in statuses.json so they never conflict with it.
"""
import json
import sqlite3

import pandas as pd
import streamlit as st

STATUSES = ["new", "interesting", "applied", "interview", "rejected", "hidden"]

st.set_page_config(page_title="Tech Jobs", layout="wide")
st.title("Werkstudent & Intern Tech Jobs (Germany)")

con = sqlite3.connect("jobs.db")
df = pd.read_sql("SELECT * FROM jobs ORDER BY posted_at DESC", con)
try:
    with open("statuses.json") as f:
        saved = json.load(f)
except FileNotFoundError:
    saved = {}
df["status"] = df.id.map(saved).fillna("new")

with st.sidebar:
    search = st.text_input("Search title / company")
    levels = st.multiselect("Level", ["Werkstudent", "Intern"], default=["Werkstudent", "Intern"])
    sources = st.multiselect("Source", sorted(df.source.unique()), default=sorted(df.source.unique()))
    langs = st.multiselect("JD language", ["de", "en", "unknown"], default=["de", "en", "unknown"])
    city = st.text_input("City contains")
    remote_only = st.checkbox("Home office possible")
    statuses = st.multiselect("Status", STATUSES, default=[s for s in STATUSES if s != "hidden"])

view = df[df.level.isin(levels) & df.source.isin(sources) & df.status.isin(statuses) & df.lang.fillna("unknown").isin(langs)]
if search:
    view = view[view.title.str.contains(search, case=False) | view.company.str.contains(search, case=False)]
if city:
    view = view[view.location.str.contains(city, case=False, na=False)]
if remote_only:
    view = view[view.remote == 1]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Shown", len(view))
c2.metric("New today", int((df.first_seen == df.first_seen.max()).sum()) if len(df) else 0)
c3.metric("Applied", int((df.status == "applied").sum()))
c4.metric("Interviews", int((df.status == "interview").sum()))

p1, p2, p3 = st.columns([1, 1, 4])
page_size = p1.selectbox("Rows per page", [25, 50, 100], index=1)
pages = max(1, -(-len(view) // page_size))
page_no = p2.number_input(f"Page (of {pages})", min_value=1, max_value=pages, value=1)
start = (page_no - 1) * page_size
p3.caption(f"Showing {min(start + 1, len(view))}–{min(start + page_size, len(view))} of {len(view)}")
page = view.iloc[start:start + page_size]

edited = st.data_editor(
    page[["status", "title", "company", "location", "level", "lang", "remote", "source", "posted_at", "url", "id"]],
    column_config={
        "status": st.column_config.SelectboxColumn("Status", options=STATUSES, required=True),
        "url": st.column_config.LinkColumn("Link", display_text="open"),
        "remote": st.column_config.CheckboxColumn("Remote"),
        "lang": st.column_config.TextColumn("Lang"),
        "id": None,
    },
    disabled=["title", "company", "location", "level", "lang", "remote", "source", "posted_at", "url"],
    hide_index=True,
    width="stretch",
    height=700,
)

changed = edited[edited.status != page.status]
if len(changed):
    saved.update(zip(changed.id, changed.status))
    with open("statuses.json", "w") as f:
        json.dump(saved, f, indent=1)
    st.toast(f"Saved {len(changed)} status change(s)")
