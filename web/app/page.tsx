"use client";
import { useEffect, useMemo, useState } from "react";

type Job = {
  id: string; title: string; company: string; location: string; level: string; lang: string | null;
  remote: number; source: string; posted_at: string; first_seen: string; url: string;
};

const STATUSES = ["new", "interesting", "applied", "interview", "rejected", "hidden"];
const LEVELS = ["Werkstudent", "Intern"];
const LANGS = ["de", "en", "unknown"];

function toggle(list: string[], value: string) {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

function Checks({ label, options, value, onChange }: {
  label: string; options: string[]; value: string[]; onChange: (v: string[]) => void;
}) {
  return (
    <fieldset>
      <legend>{label}</legend>
      {options.map((o) => (
        <label key={o}>
          <input type="checkbox" checked={value.includes(o)} onChange={() => onChange(toggle(value, o))} /> {o}
        </label>
      ))}
    </fieldset>
  );
}

export default function Page() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [statuses, setStatuses] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [city, setCity] = useState("");
  const [levels, setLevels] = useState(LEVELS);
  const [langs, setLangs] = useState(LANGS);
  const [sources, setSources] = useState<string[] | null>(null);
  const [shown, setShown] = useState(STATUSES.filter((s) => s !== "hidden"));
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [pageSize, setPageSize] = useState(50);
  const [page, setPage] = useState(1);
  const [passphrase, setPassphrase] = useState("");

  useEffect(() => {
    fetch("/jobs.json").then((r) => r.json()).then(setJobs);
    fetch("/api/statuses").then((r) => (r.ok ? r.json() : Promise.reject(r.statusText)))
      .then(setStatuses).catch((e) => setError(`Could not load statuses: ${e}`));
    try { setPassphrase(localStorage.getItem("passphrase") ?? ""); } catch {}
  }, []);

  const allSources = useMemo(() => [...new Set(jobs.map((j) => j.source))].sort(), [jobs]);
  const statusOf = (j: Job) => statuses[j.id] ?? "new";

  const view = jobs.filter((j) =>
    levels.includes(j.level) && (sources ?? allSources).includes(j.source) && shown.includes(statusOf(j)) &&
    langs.includes(j.lang ?? "unknown") && (!remoteOnly || j.remote === 1) &&
    (!search || `${j.title} ${j.company}`.toLowerCase().includes(search.toLowerCase())) &&
    (!city || (j.location ?? "").toLowerCase().includes(city.toLowerCase())),
  );
  const pages = Math.max(1, Math.ceil(view.length / pageSize));
  const current = Math.min(page, pages);
  const rows = view.slice((current - 1) * pageSize, current * pageSize);
  const latest = jobs.reduce((m, j) => (j.first_seen > m ? j.first_seen : m), "");
  const count = (s: string) => Object.values(statuses).filter((v) => v === s).length;

  async function save(id: string, status: string) {
    const before = statuses;
    setStatuses({ ...statuses, [id]: status });
    const r = await fetch("/api/statuses", {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-passphrase": passphrase },
      body: JSON.stringify({ id, status }),
    });
    if (r.ok) { setStatuses(await r.json()); setError(""); }
    else { setStatuses(before); setError(r.status === 401 ? "Wrong passphrase, not saved." : `Save failed: ${await r.text()}`); }
  }

  return (
    <main>
      <h1>Werkstudent &amp; Intern Tech Jobs (Germany)</h1>
      <div className="filters">
        <input placeholder="Search title / company" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
        <input placeholder="City contains" value={city} onChange={(e) => { setCity(e.target.value); setPage(1); }} />
        <Checks label="Level" options={LEVELS} value={levels} onChange={setLevels} />
        <Checks label="Lang" options={LANGS} value={langs} onChange={setLangs} />
        <Checks label="Status" options={STATUSES} value={shown} onChange={setShown} />
        <Checks label="Source" options={allSources} value={sources ?? allSources} onChange={setSources} />
        <label><input type="checkbox" checked={remoteOnly} onChange={(e) => setRemoteOnly(e.target.checked)} /> Home office</label>
        <input type="password" placeholder="Passphrase to save" value={passphrase}
          onChange={(e) => { setPassphrase(e.target.value); try { localStorage.setItem("passphrase", e.target.value); } catch {} }} />
      </div>
      {error && <p className="error">{error}</p>}
      <div className="metrics">
        <div><b>{view.length}</b><span>Shown</span></div>
        <div><b>{jobs.filter((j) => j.first_seen === latest).length}</b><span>New today</span></div>
        <div><b>{count("applied")}</b><span>Applied</span></div>
        <div><b>{count("interview")}</b><span>Interviews</span></div>
      </div>
      <div className="table">
        <table>
          <thead>
            <tr><th>Status</th><th>Title</th><th>Company</th><th>Location</th><th>Level</th><th>Lang</th><th>Remote</th><th>Source</th><th>Posted</th></tr>
          </thead>
          <tbody>
            {rows.map((j) => (
              <tr key={j.id}>
                <td>
                  <select value={statusOf(j)} onChange={(e) => save(j.id, e.target.value)}>
                    {STATUSES.map((s) => <option key={s}>{s}</option>)}
                  </select>
                </td>
                <td><a href={j.url} target="_blank" rel="noreferrer">{j.title}</a></td>
                <td>{j.company}</td>
                <td>{j.location}</td>
                <td>{j.level}</td>
                <td>{j.lang}</td>
                <td>{j.remote ? "✓" : ""}</td>
                <td>{j.source}</td>
                <td>{j.posted_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="pager">
        <button disabled={current <= 1} onClick={() => setPage(current - 1)}>‹</button>
        Page {current} of {pages}
        <button disabled={current >= pages} onClick={() => setPage(current + 1)}>›</button>
        <select value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}>
          {[25, 50, 100].map((n) => <option key={n} value={n}>{n} per page</option>)}
        </select>
      </div>
    </main>
  );
}
