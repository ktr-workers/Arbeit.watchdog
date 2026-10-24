// Statuses live in statuses.json at the repo root, read and written through the GitHub contents API.
// Env: GITHUB_TOKEN (contents read/write on the repo), GITHUB_REPO (owner/name), SAVE_PASSPHRASE.
export const dynamic = "force-dynamic";

const url = () => `https://api.github.com/repos/${process.env.GITHUB_REPO}/contents/statuses.json`;
const headers = () => ({
  Authorization: `Bearer ${process.env.GITHUB_TOKEN}`,
  Accept: "application/vnd.github+json",
});

async function load(): Promise<{ statuses: Record<string, string>; sha: string }> {
  const r = await fetch(url(), { headers: headers(), cache: "no-store" });
  if (!r.ok) throw new Error(`GitHub GET ${r.status}`);
  const body = await r.json();
  return { statuses: JSON.parse(Buffer.from(body.content, "base64").toString("utf8")), sha: body.sha };
}

export async function GET() {
  return Response.json((await load()).statuses);
}

export async function POST(req: Request) {
  if (req.headers.get("x-passphrase") !== process.env.SAVE_PASSPHRASE) {
    return new Response("wrong passphrase", { status: 401 });
  }
  const { id, status } = (await req.json()) as { id: string; status: string };
  const { statuses, sha } = await load();
  if (status === "new") delete statuses[id];
  else statuses[id] = status;
  const r = await fetch(url(), {
    method: "PUT",
    headers: headers(),
    body: JSON.stringify({
      message: `Set ${id} to ${status}`,
      content: Buffer.from(JSON.stringify(statuses, null, 1) + "\n").toString("base64"),
      sha,
    }),
  });
  if (!r.ok) return new Response(`GitHub PUT ${r.status}`, { status: 502 });
  return Response.json(statuses);
}
