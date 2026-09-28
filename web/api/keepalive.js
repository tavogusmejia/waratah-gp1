/* ==========================================================================
   Keep the Supabase project awake, and say whether it is.

   A free-tier project pauses after seven days of inactivity. The register
   itself would keep rendering - the catalogue is a static JSON file - while
   every status, note and invoice quietly failed. A page that looks fine and
   saves nothing is the worst shape this can fail in, so a Vercel cron job
   calls this once a day.

   TWO BEHAVIOURS, DECIDED BY THE CALLER

     Vercel's cron   sends `Authorization: Bearer $CRON_SECRET`. That calls
                     gp1.beat(), which WRITES a heartbeat row. A write is
                     unambiguous activity, and it exercises the path that
                     actually matters - a read-only ping would keep reporting
                     success on a database that had stopped accepting writes.

     Anyone else     gets gp1.beat_status(), which writes nothing. So opening
                     this URL in a browser answers "is the keep-alive working"
                     without being a way to drive it.

   NO SECRETS LIVE HERE. The only Supabase credential is the anon key, which
   is public by design and already in web/assets/config.js. gp1.beat() is
   rate-limited inside the database - one write an hour however often it is
   called - which is what makes it safe to expose. Putting a service_role key
   in a deployment to keep a project awake would be a poor trade.

   Env on Vercel:
     SUPABASE_ANON_KEY   required
     SUPABASE_URL        optional, defaults to the project below
     CRON_SECRET         optional but recommended; Vercel sends it as a
                         bearer token on scheduled invocations
   ========================================================================== */

const URL_ = process.env.SUPABASE_URL || "https://iygkonfuyslvgezgofby.supabase.co";
const KEY = process.env.SUPABASE_ANON_KEY || "";
const SECRET = process.env.CRON_SECRET || "";

async function rpc(fn, body) {
  const r = await fetch(`${URL_}/rest/v1/rpc/${fn}`, {
    method: "POST",
    headers: {
      apikey: KEY,
      Authorization: `Bearer ${KEY}`,
      "Content-Type": "application/json",
      /* The schema is gp1, not public. Without this PostgREST answers
         PGRST106 and the function looks as though it does not exist. */
      "Content-Profile": "gp1",
      "Accept-Profile": "gp1"
    },
    body: JSON.stringify(body || {})
  });
  const text = await r.text();
  let data = null;
  try { data = JSON.parse(text); } catch (e) { /* keep the raw text below */ }
  return { ok: r.ok, status: r.status, data, text };
}

module.exports = async (req, res) => {
  res.setHeader("Cache-Control", "no-store");

  if (!KEY) {
    return res.status(503).json({
      ok: false,
      error: "SUPABASE_ANON_KEY is not set on this deployment.",
      fix: "Vercel -> Settings -> Environment Variables -> add SUPABASE_ANON_KEY"
    });
  }

  /* Vercel puts CRON_SECRET in the Authorization header of scheduled runs.
     With no secret configured, treat a request carrying Vercel's cron header
     as the cron - otherwise a project that never set one would never beat. */
  const auth = req.headers.authorization || "";
  const isCron = SECRET
    ? auth === `Bearer ${SECRET}`
    : Boolean(req.headers["x-vercel-cron"]);

  const r = isCron
    ? await rpc("beat", { source: "vercel-cron" })
    : await rpc("beat_status", {});

  if (!r.ok) {
    /* Say which half failed. "It did not work" costs an afternoon; "the gp1
       schema is not exposed" costs ten seconds. */
    const hint =
      r.status === 404 ? "The function is missing - has supabase db push been run?"
      : r.status === 401 || r.status === 403 ? "The anon key was refused."
      : r.text && r.text.includes("PGRST106")
        ? "The gp1 schema is not exposed: Supabase -> Settings -> API -> Exposed schemas."
      : r.status === 503 || r.status === 544
        ? "The project looks paused. Restore it in the Supabase dashboard."
      : "";
    return res.status(502).json({
      ok: false, mode: isCron ? "beat" : "status",
      status: r.status, hint, body: r.data || r.text.slice(0, 400)
    });
  }

  return res.status(200).json(
    Object.assign({ mode: isCron ? "beat" : "status" }, r.data)
  );
};
