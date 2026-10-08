// ---- Live data: every number on this page is queried from BigQuery through the viewer's own connector. ----
const BQ = "Google Cloud BigQuery", RUN = "execute_sql_readonly", POLL = "get_query_results";
const PROJECT = "__PROJECT__";
const SQL = id => document.getElementById(id).textContent.trim();
const PIECES = [
  { id: "core", label: "Offices and monthly totals", query: SQL("q-core") },
  { id: "opex0", label: "Expenses, latest 6 months", query: SQL("q-opex").replace("__CHUNK__", "0") },
  { id: "detail", label: "Marketing, procedures and checks", query: SQL("q-detail") },
  { id: "opex1", label: "Expenses, months 7 to 12 back", query: SQL("q-opex").replace("__CHUNK__", "1") },
  { id: "opex2", label: "Expenses, months 13 to 18 back", query: SQL("q-opex").replace("__CHUNK__", "2") },
  { id: "weekly", label: "Weekly numbers for comparisons", query: SQL("q-weekly") },
];
const ST = Object.fromEntries(PIECES.map(p => [p.id, { status: "loading", data: null, err: null, at: null, retried: false }]));
let mcp = null, started = false;

const SOURCE_DETAIL = { "Practice management": "7 PMS systems, CDT codes", "Sage Intacct": "GL detail, chart of accounts",
  "UKG": "Timecards, job and earning codes", "Inventory": "Usage, vendor categories", "Marketing / websites": "UTM source and medium, Meta via Windsor.ai" };
const cols = o => { const ks = Object.keys(o || {}); const n = ks.length ? (o[ks[0]] || []).length : 0;
  return Array.from({ length: n }, (_, r) => Object.fromEntries(ks.map(k => [k, o[k][r]]))) };
const addMonths = (ym, k) => { const [y, m] = ym.split("-").map(Number); const t = y * 12 + (m - 1) + k; return Math.floor(t / 12) + "-" + String(t % 12 + 1).padStart(2, "0") };

function cellJson(payload) {
  let p = payload;
  if (typeof p === "string") { try { p = JSON.parse(p) } catch (e) { throw { code: "tool_error", message: p.slice(0, 300) } } }
  if (!p || typeof p !== "object") throw { code: "tool_error", message: "BigQuery returned an empty answer." };
  if (p.error) throw { code: "tool_error", message: p.error.message || String(p.error) };
  const done = p.jobComplete ?? p.job_complete;
  if (done === false) return { pending: p.jobReference?.jobId || p.jobId || p.job_id, location: p.jobReference?.location };
  const v = p.rows?.[0]?.f?.[0]?.v;
  if (v == null) throw { code: "tool_error", message: "The query ran but returned no rows." };
  return { json: JSON.parse(v) };
}
async function finishJob(jobId, location) {
  for (let i = 0; i < 4; i++) {
    const r = await mcp.callTool(BQ, POLL, { projectId: PROJECT, jobId, ...(location ? { location } : {}), timeoutMs: 30000 }, { cache: false });
    const c = cellJson(r.payload);
    if (c.json) return c.json;
  }
  throw { code: "server_unavailable", message: "BigQuery is still working on this query.", retryable: true };
}

const DENY = new Set(["needs_reauth", "server_not_connected", "selection_required", "blocked_by_policy", "approval_required", "not_in_manifest", "consent_required", "server_not_found"]);
function onEvent(p, input) {
  return async ev => {
    const s = ST[p.id];
    if (ev.type === "error") {
      const e = ev.error || {};
      if (e.code === "user_changed") return;
      if (e.retryable && !s.retried) {
        s.retried = true;
        setTimeout(() => mcp.invalidate(BQ, RUN, input).catch(() => {}), (e.retryAfterMs || 1500) + Math.random() * 1500);
        return;
      }
      if (DENY.has(e.code) || !s.data) { s.data = DENY.has(e.code) ? null : s.data; s.status = "error"; s.err = e }
      else s.stale = e;   // transient: keep last good data visible
      return update();
    }
    try {
      let c = cellJson(ev.result.payload);
      const json = c.json || await finishJob(c.pending, c.location);
      Object.assign(s, { status: "ok", data: json, err: null, stale: null, retried: false, at: ev.result.cache?.storedAt || Date.now() });
    } catch (e) {
      Object.assign(s, { status: s.data ? "ok" : "error", err: s.data ? null : e, stale: s.data ? e : null });
    }
    update();
  };
}

function assemble() {
  const core = ST.core.data, det = ST.detail.data;
  DATA.locations = core.locations;
  DATA.monthly = cols(core.monthly);
  DATA.sources = (core.sources || []).map(s => ({ source: s.source, detail: SOURCE_DETAIL[s.source] || "", n: s.n }));
  DATA.unmapped = core.unmapped;
  DATA.channels = det ? cols(det.channels) : [];
  DATA.mix = det ? cols(det.mix) : [];
  DATA.recon = det ? cols(det.recon) : [];
  DATA.weekly = ST.weekly.data ? cols(ST.weekly.data) : [];
  DATA.opex = []; DATA.opex_accounts = [];
  ["opex0", "opex1", "opex2"].forEach(id => { const o = ST[id].data; if (!o) return;
    if (!DATA.opex_accounts.length) DATA.opex_accounts = o.accounts.map(a => a.split("|"));
    for (let r = 0; r < o.k.length; r++) DATA.opex.push([o.k[r], addMonths(o.first_month, o.m[r]), o.i[r], o.amt[r]]) });
  LOC = Object.fromEntries(DATA.locations.map(l => [l.location_key, l]));
  MONTHS = [...new Set(DATA.monthly.map(r => r.month))].sort();
}

function errText(e) {
  switch (e && e.code) {
    case "server_not_connected": return "Add the Google Cloud BigQuery connector in claude.ai Settings → Connectors, then reload this page.";
    case "selection_required": return "You have more than one BigQuery connector. Pick which one this page should use when Claude asks, then reload.";
    case "needs_reauth": return "Your BigQuery connection has expired. Reconnect Google Cloud BigQuery in claude.ai Settings → Connectors.";
    case "not_in_manifest": case "consent_required": return "BigQuery access is turned off for this page. Allow it when Claude asks, then press Try again.";
    case "blocked_by_policy": case "approval_required": return "Your organization's settings don't allow this page to run BigQuery queries.";
    case "server_unavailable": case "rate_limited": return "BigQuery didn't answer in time. Try again in a moment.";
    case "tool_error": return "BigQuery refused the query: " + (e.message || "no detail given") + ". Your Google account may not have access to the Northwind project.";
    case "not_granted": case "capability_disabled": case "capability_removed": return "This view can't use connectors. Open the page inside Claude to see live numbers.";
    default: return "BigQuery couldn't be reached" + (e && e.message ? ": " + e.message : ".") + " Try again in a moment.";
  }
}
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function update() {
  const core = ST.core;
  const ready = core.status === "ok" && core.data;
  $("#app").hidden = !ready;
  $("#gate").hidden = !!ready;
  if (!ready) {
    const failed = core.status === "error";
    $("#gate").innerHTML = failed
      ? `<h2>Live data couldn't load</h2><p>${esc(errText(core.err))}</p><button class="btn" id="retry">Try again</button>`
      : `<div class="pulse" aria-hidden="true"></div><h2>Loading live data from BigQuery</h2><p class="muted">The first load runs the warehouse queries and can take up to a minute. After that it opens from cache.</p>
         <ul class="steps">${PIECES.map(p => `<li class="${ST[p.id].status}">${p.label}</li>`).join("")}</ul>`;
    if (failed) $("#retry").onclick = refresh;
    return;
  }
  assemble();
  if (!started) { started = true; setupFilters(); if (location.hash && document.getElementById("v-" + location.hash.slice(1))) showTab(location.hash.slice(1)) }
  else fillLocs();
  render();
  // section notes
  const note = (sel, ids, what) => {
    const bad = ids.filter(id => ST[id].status === "error"), wait = ids.filter(id => ST[id].status === "loading");
    document.querySelectorAll(sel).forEach(el => {
      el.hidden = !bad.length && !wait.length;
      el.classList.toggle("bad", !!bad.length); el.classList.toggle("wait", !bad.length);
      el.innerHTML = bad.length ? `${what} ${bad.length < ids.length ? "is partly missing" : "didn't load"}. ${esc(errText(ST[bad[0]].err))}` : `Still loading ${what.toLowerCase()} from BigQuery…`;
    });
  };
  note(".note-opex", ["opex0", "opex1", "opex2"], "Expense detail");
  note(".note-detail", ["detail"], "This section");
  const ats = PIECES.map(p => ST[p.id].at).filter(Boolean), oldest = Math.min(...ats);
  const loading = PIECES.some(p => ST[p.id].status === "loading");
  const stale = PIECES.some(p => ST[p.id].stale);
  $("#live-txt").innerHTML = `<i class="dot ${loading ? "busy" : stale ? "warn" : ""}"></i>` +
    (loading ? "Loading the rest" : `Updated ${new Date(oldest).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}`) +
    (stale ? ". Last refresh failed, showing earlier data" : "");
}

function refresh() {
  PIECES.forEach(p => { const s = ST[p.id]; s.retried = false; if (!s.data) { s.status = "loading"; s.err = null } });
  update();
  if (mcp) mcp.invalidate(BQ, RUN).catch(() => {}); else boot();
}

async function boot() {
  update();
  mcp = await claude.use("mcp").catch(() => null);
  if (!mcp) { ST.core.status = "error"; ST.core.err = { code: "capability_disabled" }; return update() }
  PIECES.forEach(p => {
    const input = { projectId: PROJECT, query: p.query, timeoutMs: 60000 };
    p.unsub = mcp.watchTool(BQ, RUN, input, onEvent(p, input), { cache: { staleTime: 300000, gcTime: 86400000 } });
  });
}
$("#refresh").addEventListener("click", refresh);
boot();
