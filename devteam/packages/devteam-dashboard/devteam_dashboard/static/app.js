"use strict";

// Presentation only: this script renders JSON from the dashboard API. It never contains business
// logic — approve/reject are POSTs the server turns into ApprovalGateway calls. All text pulled from
// GitHub/logs/diffs is HTML-escaped before rendering (untrusted content).

const view = document.getElementById("view");
const POLL = { executive: 10000, overview: 25000, pipeline: 6000, agents: 6000, lifecycle: 8000, jobs: 8000, connectors: 8000, missions: 25000, logs: 4000, metrics: 20000, settings: 0 };
let currentTab = "executive";
let pollTimer = null;
let knownActionable = null; // Set<pr_number> for notification diffing

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
  );
}

async function api(path, opts) {
  setBusy(true);
  try {
    const res = await fetch(path, opts);
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = body.detail || detail;
      } catch (_) { /* non-JSON error body */ }
      throw new Error(detail);
    }
    return await res.json();
  } finally {
    setBusy(false);
  }
}

function setBusy(on) {
  const dot = document.getElementById("refresh-dot");
  if (dot) dot.classList.toggle("active", on);
}

function badge(kind, label) {
  return `<span class="badge badge-${esc(kind)}">${esc(label ?? kind)}</span>`;
}

function setHealth(health) {
  const pill = document.getElementById("health-pill");
  if (!pill) return;
  pill.className = `pill pill-${esc(health || "unknown")}`;
  pill.textContent = `health: ${health || "—"}`;
}

// ---- Overview --------------------------------------------------------------------------------

async function renderOverview() {
  let data;
  try {
    data = await api("/api/overview");
  } catch (e) {
    view.innerHTML = errorNotice("overview", e);
    return;
  }
  setHealth(data.health);
  document.getElementById("repo-label").textContent =
    data.repo || (data.repos && data.repos[0]) || "unconfigured";
  const worker = (data.workers && data.workers[0]) || {};
  const errors = (data.errors || []).map((m) => `<div class="notice notice-warn">${esc(m)}</div>`).join("");
  view.innerHTML = `
    ${errors}
    <div class="grid">
      <div class="card"><h3>Health</h3><div class="stat">${healthIcon(data.health)}</div>
        <div class="stat-sub">${esc(data.health || "unknown")}</div></div>
      <div class="card"><h3>Running Workers</h3><div class="stat">${worker.running ? 1 : 0}</div>
        <div class="stat-sub">${esc(worker.label || "monitor")} · ${esc(worker.state || "unknown")}${worker.pid ? " · pid " + esc(worker.pid) : ""}</div></div>
      <div class="card"><h3>Last Poll</h3><div class="stat" style="font-size:18px">${esc(data.last_poll || "never")}</div>
        <div class="stat-sub">${data.last_poll_open_prs != null ? esc(data.last_poll_open_prs) + " open PR(s) seen" : "no poll recorded"}</div></div>
      <div class="card"><h3>Open PRs (live)</h3><div class="stat">${data.open_pr_count != null ? esc(data.open_pr_count) : "—"}</div>
        <div class="stat-sub">on ${esc(data.repo || "—")}</div></div>
    </div>
    <div class="section-title">Monitored Repositories</div>
    ${repoList(data.repos)}`;
}

function healthIcon(h) {
  return { healthy: "🟢", degraded: "🟡", down: "🔴" }[h] || "⚪️";
}
function repoList(repos) {
  if (!repos || !repos.length) return `<div class="empty">No repositories configured.</div>`;
  return `<div class="card">${repos.map((r) => `<div class="mono">${esc(r)}</div>`).join("")}</div>`;
}

// ---- Executive (command center) --------------------------------------------------------------
// A live roll-up of the Mission + Agent Experiences from /api/executive — aggregation only, no new
// data model. Reuses the shared renderers (decisionDistribution) and the same badge/card/bar
// vocabulary. Every active mission links into the Mission Timeline, so the nav chain stays whole:
// Executive -> Mission -> Timeline -> Session -> Agent. Increments 2 (Organization View) and 3
// (Executive Insights) append sections below the overview without a redesign.

async function renderExecutive() {
  let d;
  try {
    d = await api("/api/executive");
  } catch (e) {
    view.innerHTML = errorNotice("executive overview", e);
    return;
  }
  view.innerHTML = executiveNotPresent(d) + executiveOverview(d)
    + executiveOrganization(d.organization) + executiveInsights(d.insights);
}

function executiveNotPresent(d) {
  return d.journal_present ? "" : `<div class="notice notice-warn">The monitor hasn't written the
    runtime journal yet — the command center is empty until missions run (observability is on by
    default).</div>`;
}

function executiveOverview(d) {
  const m = d.missions || {}, ag = d.agents || {}, u = d.utilization || {}, q = d.queue || {};
  const utilNow = u.ratio_now != null ? Math.round(u.ratio_now * 100) + "%" : "—";
  const utilWindow = u.ratio_window != null
    ? Math.round(u.ratio_window * 100) + "% over window"
    : "window: insufficient data";
  const blocked = ag.blocked ? ` · <span class="danger-text">${esc(ag.blocked)} blocked</span>` : "";
  return `
    <div class="banner">Command center — the whole runtime at a glance, aggregated live from the
      Mission &amp; Agent Experiences. Click any active mission to drill in
      (Mission → Timeline → Session → Agent).</div>
    <div class="grid">
      <div class="card"><h3>Active Missions</h3><div class="stat">${esc(m.active || 0)}</div>
        <div class="stat-sub">${esc(m.total || 0)} observed · ${esc(m.completed || 0)} completed</div></div>
      <div class="card"><h3>Active Agents</h3>
        <div class="stat">${esc(ag.utilized || 0)}<span class="muted" style="font-size:16px"> / ${esc(ag.total || 0)}</span></div>
        <div class="stat-sub">${esc(ag.engaged || 0)} engaged · ${esc(ag.idle || 0)} idle${blocked}</div></div>
      <div class="card"><h3>Mission Throughput</h3><div class="stat">${esc((d.throughput || {}).completed_missions || 0)}</div>
        <div class="stat-sub">missions completed</div></div>
      <div class="card"><h3>Overall Utilization</h3><div class="stat">${esc(utilNow)}</div>
        <div class="stat-sub">utilized now · ${esc(utilWindow)}</div></div>
      <div class="card"><h3>Queue Health</h3>
        <div class="stat" style="font-size:20px">${badge(healthKind(q.health), q.health || "—")}</div>
        <div class="stat-sub">${esc(q.awaiting_approval || 0)} awaiting approval · ${esc(q.blocked_agents || 0)} blocked</div></div>
    </div>
    ${decisionDistribution(d.decision_distribution, "Fleet Decision Distribution")}
    <div class="section-title">Active Missions</div>
    ${executiveActiveMissions(m.active_list)}`;
}

function healthKind(health) {
  return { healthy: "green", attention: "pending", idle: "idle" }[health] || "unknown";
}

function executiveActiveMissions(list) {
  if (!list || !list.length) return `<div class="empty">No active missions right now.</div>`;
  const rows = list.map((m) => {
    const progress = `${esc(m.completed || 0)}/${esc(m.session_count || 0)}`
      + (m.active ? ` · <span class="accent-text">${esc(m.active)} active</span>` : "");
    return `<tr>
      <td><a class="link mono" href="#pipeline/${esc(m.mission_id)}">${esc(shortId(m.mission_id))} ↗</a></td>
      <td class="mono">${esc(m.owner || "—")}</td>
      <td>${esc(m.participants || 0)} agent(s)</td>
      <td>${progress}</td>
      <td>${badge(m.status || "unknown", m.status || "—")}</td>
    </tr>`;
  }).join("");
  return `<table>
    <thead><tr><th>Mission</th><th>Owner</th><th>Agents</th><th>Progress</th><th>Status</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
}

// ---- Executive · Organization View (Increment 2) ---------------------------------------------
// "How is the DevTeam performing as a system?" — four sections aggregated from the SAME per-agent
// metrics and mission sessions as the overview (in `d.organization`). Agent rows drill into the
// Agent Inspector; every mission drills into its timeline — so the nav chain stays whole.

function executiveOrganization(org) {
  if (!org) return "";
  return `<div class="section-title" style="margin-top:30px">Organization — how the DevTeam is performing</div>
    ${fleetOverviewSection(org.fleet)}
    ${agentPerformanceSection(org.agent_performance)}
    ${missionPerformanceSection(org.mission_performance)}
    ${operationalHealthSection(org.operational_health)}`;
}

const STATUS_ORDER = ["working", "thinking", "waiting", "idle", "blocked", "offline"];

function statusChips(dist) {
  const keys = STATUS_ORDER.filter((k) => k in (dist || {}))
    .concat(Object.keys(dist || {}).filter((k) => !STATUS_ORDER.includes(k)));
  return keys.map((k) => `<span class="badge badge-${esc(k)}">${esc(k)} ${esc(dist[k])}</span>`).join(" ")
    || `<span class="muted">none</span>`;
}

function fleetOverviewSection(fleet) {
  if (!fleet) return "";
  const u = fleet.utilization || {};
  const utilNow = u.ratio_now != null ? Math.round(u.ratio_now * 100) + "%" : "—";
  const utilWindow = u.ratio_window != null
    ? Math.round(u.ratio_window * 100) + "% over window" : "window: insufficient data";
  return `<div class="section-title">Fleet Overview</div>
    <div class="card">
      <div class="status-chips">${statusChips(fleet.status_distribution)}</div>
      <div class="stat-sub" style="margin-top:10px">Current utilization: <b>${esc(utilNow)}</b> now · ${esc(utilWindow)}</div>
    </div>`;
}

function agentPerformanceSection(rows) {
  if (!rows || !rows.length) {
    return `<div class="section-title">Agent Performance</div><div class="empty">No agents.</div>`;
  }
  const body = rows.map(agentPerfRow).join("");
  return `<div class="section-title">Agent Performance</div>
    <table>
      <thead><tr><th>Agent</th><th>Status</th><th>Completed</th><th>Avg Session</th>
        <th>Decisions</th><th>Assignment</th><th>Last Activity</th></tr></thead>
      <tbody>${body}</tbody>
    </table>`;
}

function agentPerfRow(a) {
  const key = a.agent ? a.agent.key : "";
  const name = a.display_name || (a.agent && a.agent.role) || key;
  const avg = a.avg_duration_ms != null ? fmtDur(a.avg_duration_ms) : "—";
  const assignment = a.current_mission_id
    ? `<a class="link mono" href="#pipeline/${esc(a.current_mission_id)}">${esc(shortId(a.current_mission_id))} ↗</a>`
    : `<span class="muted">—</span>`;
  const last = a.last_activity_at != null ? fmtTime(a.last_activity_at, true) : "—";
  return `<tr>
    <td><a class="link" href="#agents/${esc(key)}">${esc(name)} ↗</a></td>
    <td>${badge(a.status || "offline", a.status || "—")}</td>
    <td>${esc(a.completed_missions || 0)}</td>
    <td class="muted">${esc(avg)}</td>
    <td>${decisionMini(a.decision_distribution)}</td>
    <td>${assignment}</td>
    <td class="muted">${esc(last)}</td>
  </tr>`;
}

function decisionMini(dist) {
  const entries = Object.entries(dist || {});
  if (!entries.length) return `<span class="muted">—</span>`;
  return entries.map(([verdict, count]) =>
    `<span class="chip" title="${esc(verdict)}">${esc(verdict)} ${esc(count)}</span>`).join(" ");
}

function missionPerformanceSection(mp) {
  if (!mp) return "";
  const avgCompletion = mp.avg_completion_ms != null
    ? esc(fmtDur(mp.avg_completion_ms))
    : `<span class="muted" style="font-size:14px">insufficient data</span>`;
  const b = mp.bottlenecks || {};
  const bottleneck = (b.awaiting_approval || b.blocked_agents)
    ? `<span class="danger-text">${esc(b.awaiting_approval || 0)} awaiting · ${esc(b.blocked_agents || 0)} blocked</span>`
    : `<span class="muted">none</span>`;
  return `<div class="section-title">Mission Performance</div>
    <div class="card"><div class="status-chips">${statusChips(mp.lifecycle_distribution)}</div>
      <div class="stat-sub" style="margin-top:8px">Mission lifecycle distribution</div></div>
    <div class="grid" style="margin-top:12px">
      <div class="card"><h3>Avg Completion</h3><div class="stat" style="font-size:22px">${avgCompletion}</div>
        <div class="stat-sub">completed missions' session span</div></div>
      <div class="card"><h3>Throughput</h3><div class="stat">${esc(mp.completed_missions || 0)}</div>
        <div class="stat-sub">missions completed</div></div>
      <div class="card"><h3>Queue Health</h3>
        <div class="stat" style="font-size:20px">${badge(healthKind(mp.queue_health), mp.queue_health || "—")}</div>
        <div class="stat-sub">current</div></div>
      <div class="card"><h3>Current Bottlenecks</h3><div class="stat" style="font-size:18px">${bottleneck}</div>
        <div class="stat-sub">blocking throughput</div></div>
    </div>`;
}

function operationalHealthSection(oh) {
  if (!oh) return "";
  const waiting = oh.waiting_approvals || [];
  const longRunning = (oh.long_running || []).slice()
    .sort((a, b) => (a.active_since ?? Infinity) - (b.active_since ?? Infinity));
  const cap = oh.idle_capacity || {}, wl = oh.workload || {};
  const waitingList = waiting.length
    ? waiting.map((w) => `<li><a class="link mono" href="#pipeline/${esc(w.mission_id)}">${esc(shortId(w.mission_id))} ↗</a>
        <span class="muted">owner ${esc(w.owner || "—")}</span></li>`).join("")
    : `<li class="muted">None — nothing awaiting approval.</li>`;
  const longList = longRunning.length
    ? longRunning.map((l) => `<li><a class="link mono" href="#pipeline/${esc(l.mission_id)}">${esc(shortId(l.mission_id))} ↗</a>
        ${badge(l.status || "unknown", l.status || "—")}
        <span class="muted">${l.active_since != null ? "active for " + esc(fmtElapsed(l.active_since)) : "no active session"}</span></li>`).join("")
    : `<li class="muted">None active.</li>`;
  const total = wl.total || 0;
  const engagedPct = total ? Math.round(((wl.engaged || 0) / total) * 100) : 0;
  return `<div class="section-title">Operational Health</div>
    <div class="grid">
      <div class="card"><h3>Waiting Approvals</h3><div class="stat">${esc(waiting.length)}</div>
        <ul class="findings">${waitingList}</ul></div>
      <div class="card"><h3>Long-Running Active</h3><div class="stat">${esc(longRunning.length)}</div>
        <ul class="findings">${longList}</ul></div>
      <div class="card"><h3>Idle Capacity</h3>
        <div class="stat">${esc(cap.idle || 0)}<span class="muted" style="font-size:16px"> / ${esc(cap.total || 0)}</span></div>
        <div class="stat-sub">agents free</div></div>
      <div class="card"><h3>Workload Balance</h3><div class="stat" style="font-size:20px">${esc(engagedPct)}% engaged</div>
        ${metricBar(engagedPct, "")}
        <div class="stat-sub">${esc(wl.engaged || 0)} engaged · ${esc(wl.idle || 0)} idle</div></div>
    </div>`;
}

function fmtElapsed(sinceSeconds) {
  const ms = Date.now() - sinceSeconds * 1000;
  return ms < 0 ? "just now" : fmtDur(ms);
}

// ---- Executive · Operations Intelligence (Increment 3) ---------------------------------------
// The insights layer COMPOSES the same facts (`d.insights`) into an actionable digest — attention
// items, capacity outlook, and a plain-language operational summary of only what's observable.
// Every attention/capacity item drills into its Mission or Agent. No new numbers, no predictions.

function executiveInsights(ins) {
  if (!ins) return "";
  return `<div class="section-title" style="margin-top:30px">Operations Intelligence</div>
    ${operationalSummarySection(ins.operational_summary)}
    ${attentionRequiredSection(ins.attention_required)}
    ${capacityOutlookSection(ins.capacity_outlook)}`;
}

function operationalSummarySection(lines) {
  const items = (lines || []).map((l) => `<li>${esc(l)}</li>`).join("")
    || `<li class="muted">Nothing to report.</li>`;
  return `<div class="section-title">Operational Summary</div>
    <div class="card"><ul class="summary-list">${items}</ul>
      <div class="stat-sub">Observed facts only — no recommendations or predictions.</div></div>`;
}

// A mission attention item: a link into its timeline + status + (optionally) live elapsed.
function missionAttentionItem(m, withElapsed) {
  const elapsed = withElapsed && m.active_since != null
    ? ` <span class="muted">active for ${esc(fmtElapsed(m.active_since))}</span>`
    : m.owner ? ` <span class="muted">owner ${esc(m.owner)}</span>` : "";
  return `<li><a class="link mono" href="#pipeline/${esc(m.mission_id)}">${esc(shortId(m.mission_id))} ↗</a>
    ${m.status ? badge(m.status, m.status) : ""}${elapsed}</li>`;
}

// An agent attention item: a link into the Agent Inspector + status + its current mission (if any).
function agentAttentionItem(a) {
  const key = a.agent ? a.agent.key : "";
  const name = a.display_name || (a.agent && a.agent.role) || key;
  const mission = a.current_mission_id
    ? ` <span class="muted">on</span> <a class="link mono" href="#pipeline/${esc(a.current_mission_id)}">${esc(shortId(a.current_mission_id))} ↗</a>`
    : "";
  return `<li><a class="link" href="#agents/${esc(key)}">${esc(name)} ↗</a> ${badge(a.status || "idle", a.status || "—")}${mission}</li>`;
}

function attentionCard(title, count, items, emptyText) {
  const list = (items && items.length)
    ? `<ul class="findings">${items}</ul>`
    : `<ul class="findings"><li class="muted">${esc(emptyText)}</li></ul>`;
  return `<div class="card"><h3>${esc(title)}</h3><div class="stat">${esc(count)}</div>${list}</div>`;
}

function attentionRequiredSection(ar) {
  if (!ar) return "";
  const waiting = ar.waiting_approvals || [];
  const longRunning = (ar.long_running || []).slice()
    .sort((a, b) => (a.active_since ?? Infinity) - (b.active_since ?? Infinity));
  const stalled = ar.stalled || [];
  const hotspots = ar.queue_hotspots || [];
  return `<div class="section-title">Attention Required</div>
    <div class="grid">
      ${attentionCard("Waiting Approvals", waiting.length,
        waiting.map((m) => missionAttentionItem(m, false)).join(""), "None awaiting approval.")}
      ${attentionCard("Long-Running Missions", longRunning.length,
        longRunning.map((m) => missionAttentionItem(m, true)).join(""), "None active.")}
      ${attentionCard("Stalled Activity", stalled.length,
        stalled.map(agentAttentionItem).join(""), "No blocked agents.")}
      ${attentionCard("Queue Hotspots", hotspots.length,
        hotspots.map(agentAttentionItem).join(""), "No active work — queue is clear.")}
    </div>`;
}

function capacityOutlookSection(co) {
  if (!co) return "";
  const total = co.total || 0;
  const idlePct = total ? Math.round(((co.idle || 0) / total) * 100) : 0;
  const utilPct = total ? Math.round(((co.utilized || 0) / total) * 100) : 0;
  const available = co.available_agents || [];
  const wl = co.workload || {};
  const engagedPct = total ? Math.round(((wl.engaged || 0) / total) * 100) : 0;
  const availList = available.length
    ? `<ul class="findings">${available.map(agentAttentionItem).join("")}</ul>`
    : `<ul class="findings"><li class="muted">No agents free right now.</li></ul>`;
  return `<div class="section-title">Capacity Outlook</div>
    <div class="grid">
      <div class="card"><h3>Idle Capacity</h3>
        <div class="stat">${esc(co.idle || 0)}<span class="muted" style="font-size:16px"> / ${esc(total)}</span></div>
        ${metricBar(idlePct, "")}<div class="stat-sub">${esc(idlePct)}% of the fleet free</div></div>
      <div class="card"><h3>Utilized Capacity</h3>
        <div class="stat">${esc(co.utilized || 0)}<span class="muted" style="font-size:16px"> / ${esc(total)}</span></div>
        ${metricBar(utilPct, "")}<div class="stat-sub">${esc(utilPct)}% of the fleet working</div></div>
      <div class="card"><h3>Workload Balance</h3><div class="stat" style="font-size:20px">${esc(engagedPct)}% engaged</div>
        ${metricBar(engagedPct, "")}<div class="stat-sub">${esc(wl.engaged || 0)} engaged · ${esc(wl.idle || 0)} idle</div></div>
      <div class="card"><h3>Agents Available Now</h3><div class="stat">${esc(available.length)}</div>${availList}</div>
    </div>`;
}

// ---- Missions (Mission Experience) -----------------------------------------------------------

async function renderPipeline() {
  let data;
  try {
    data = await api("/api/pipeline");
  } catch (e) {
    view.innerHTML = errorNotice("missions", e);
    return;
  }
  const missions = data.missions || [];
  const notPresent = !data.journal_present
    ? `<div class="notice notice-warn">The monitor hasn't written the runtime journal yet
        (<span class="mono">${esc(data.journal_path || "")}</span>). Restart the monitor (observability
        is on by default) to see missions.</div>`
    : "";
  const banner = `<div class="banner">Observed mission <b>executions</b> from the runtime journal —
    what the agents actually ran, owner → hand-offs → outcome. (For open PRs awaiting your approval,
    see <b>Open Missions</b>.)</div>`;
  const cards = missions.length
    ? `<div class="grid mission-grid">${missions.map(missionCard).join("")}</div>`
    : `<div class="empty">No missions observed yet.</div>`;
  view.innerHTML = notPresent + banner + `<div class="section-title">Missions (${missions.length})</div>` + cards;
}

function missionCard(m) {
  const status = m.status || "unknown";
  const owner = m.owner ? m.owner.key : "—";
  const parts = (m.participants || []).length;
  const summary = `${esc(m.completed || 0)}/${esc(m.session_count || 0)} sessions`
    + (m.active ? ` · ${esc(m.active)} active` : "")
    + (m.failed ? ` · <span class="danger-text">${esc(m.failed)} failed</span>` : "");
  const chain = (m.participants || [])
    .map((p) => `<span class="chip">${esc(p.role)}</span>`)
    .join('<span class="arrow">→</span>') || `<span class="muted">—</span>`;
  // The card is the drill-down entry (Mission Card -> Mission Timeline); content is unchanged.
  return `<div class="card mission-card clickable" title="Open mission timeline"
      onclick="location.hash='#pipeline/${esc(m.mission_id)}'">
    <div class="agent-head"><span class="agent-name mono">${esc(shortId(m.mission_id))}</span>
      ${badge(status, status)}</div>
    <div class="stat-sub">owner <span class="mono">${esc(owner)}</span> · ${esc(parts)} agent(s) · ${summary}</div>
    <div class="mission-chain">${chain}</div>
  </div>`;
}

// ---- Mission Timeline (drill-down: Card -> Timeline -> Session Details) -----------------------
// Live Pipeline (Increment 3): the SAME timeline, made live — NOT a separate page. Initial state
// loads from the REST endpoint (renderMissionTimeline -> drawTimeline). An SSE stream then pushes
// the mission whenever the runtime journal changes, and patchTimeline updates ONLY the changed
// session nodes (+ the header) — never a full rebuild. Falls back to polling if SSE is unavailable.
// Every payload is a RuntimeStateView shape from /api/pipeline; no journal access, no runtime logic.

const expandedSessions = new Set(); // survives redraws, so a live refresh keeps expansions open
let currentMission = null;
let activeTimelineId = null; // the mission the timeline is showing (guards async / stale frames)
let missionStream = null;    // the live EventSource
let timelineTimer = null;    // polling fallback timer
const TERMINAL_MISSION_STATUSES = new Set(["completed", "failed", "cancelled"]);
// Verdicts that mean "needs attention" — grouped with a failed session in the UI (owner's spec:
// "Failed/request_changes session" is one visual bucket).
const ATTENTION_VERDICTS = new Set(
  ["request_changes", "changes_requested", "needs_changes", "block", "escalate", "reject", "rejected"]
);

async function renderMissionTimeline(missionId) {
  activeTimelineId = missionId;
  view.innerHTML = pipelineBack() + `<div class="loading">Loading mission ${esc(shortId(missionId))}…</div>`;
  let m;
  try {
    m = await api(`/api/pipeline/${encodeURIComponent(missionId)}`);
  } catch (e) {
    if (activeTimelineId === missionId) view.innerHTML = pipelineBack() + errorNotice("mission timeline", e);
    return;
  }
  if (activeTimelineId !== missionId) return; // navigated away while the initial load was in flight
  currentMission = m;
  if (!m.found) {
    // The mission may just not be in the journal YET (freshly created). Show a placeholder and go
    // live anyway, so the timeline materializes the moment its first session starts.
    view.innerHTML = pipelineBack()
      + `<div id="tl-header"></div>`
      + `<div class="timeline" id="tl-list"><div class="empty">Mission not observed in the runtime journal yet — watching live…</div></div>`;
  } else {
    drawTimeline(m);
  }
  openMissionStream(missionId);
}

function drawTimeline(m) {
  view.innerHTML = pipelineBack()
    + `<div id="tl-header">${timelineHeader(m)}</div>`
    + `<div class="timeline" id="tl-list">${timelineNodes(m)}</div>`;
  const header = document.getElementById("tl-header");
  if (header) header.dataset.sig = headerSig(m);
}

function timelineNodes(m) {
  const sessions = m.sessions || [];
  if (!sessions.length) return `<div class="empty">No sessions yet.</div>`;
  return sessions.map((s) => sessionNode(s, m)).join("");
}

function timelineHeader(m) {
  const owner = m.owner ? m.owner.key : "—";
  const total = m.session_count || (m.sessions || []).length || 0;
  const done = m.completed || 0;
  const pct = total ? Math.round((done / total) * 100) : 0;
  const terminal = TERMINAL_MISSION_STATUSES.has(m.status);
  const live = terminal
    ? `<span class="tl-final">✓ final</span>`
    : `<span class="tl-live"><span class="live-dot"></span> live</span>`;
  const counts = `${esc(done)}/${esc(total)} sessions`
    + (m.active ? ` · <span class="accent-text">${esc(m.active)} active</span>` : "")
    + (m.failed ? ` · <span class="danger-text">${esc(m.failed)} failed</span>` : "");
  return `
    <div class="section-title mono">${esc(shortId(m.mission_id))} ${badge(m.status, m.status)} ${live}</div>
    <div class="stat-sub">owner <span class="mono">${esc(owner)}</span> · ${counts} · click a session for details</div>
    <div class="tl-progress"><div class="tl-progress-fill ${m.failed ? "has-fail" : ""}" style="width:${pct}%"></div></div>
    <div class="mission-chain">${missionFlowChain(m)}</div>`;
}

// The owner -> ... -> current handoff chain, with the currently-executing (or last) agent emphasized
// so a live handoff is visible at the mission level as the active session moves between agents.
function missionFlowChain(m) {
  const parts = m.participants || [];
  if (!parts.length) return `<span class="muted">—</span>`;
  const active = (m.sessions || []).find((s) => s.status === "active");
  const currentKey = active && active.agent ? active.agent.key : parts[parts.length - 1].key;
  return parts
    .map((p) => `<span class="chip ${p.key === currentKey ? "current" : ""}">${esc(p.role)}</span>`)
    .join('<span class="arrow">→</span>');
}

function sessionNode(s, m) {
  const all = m.sessions || [];
  const depth = sessionDepth(s, all);
  const role = s.agent ? s.agent.role : "—";
  const disp = sessionDisplayState(s, m);
  const dur = s.duration_ms != null
    ? Math.round(s.duration_ms) + " ms"
    : (disp === "waiting" ? "waiting…" : disp === "active" ? "running…" : "—");
  const dec = s.decision ? badge("neutral", s.decision.verdict) : "";
  const parent = s.parent_session_id ? findSession(all, s.parent_session_id) : null;
  const handoff = parent && parent.agent && s.agent && parent.agent.key !== s.agent.key
    ? `<span class="handoff">⇄ from ${esc(parent.agent.role)}</span>` : "";
  const tag = disp === "active" ? `<span class="live-tag">live</span>`
    : disp === "waiting" ? badge("waiting", "waiting") : "";
  const live = (disp === "active" || disp === "waiting") ? " live" : "";
  const open = expandedSessions.has(s.session_id);
  const sig = sessionSig(s, disp, open);
  return `<div class="tl-node" id="node-${esc(s.session_id)}" data-sig="${esc(sig)}" style="margin-left:${depth * 22}px">
    <div class="tl-dot tl-${esc(disp)}${live}"></div>
    <div class="tl-body ${open ? "open" : ""}" onclick="toggleSession('${esc(s.session_id)}')">
      <div class="tl-head">
        <span class="chip">${esc(role)}</span> ${badge(s.status, s.status)} ${dec} ${tag} ${handoff}
        <span class="tl-time muted">${esc(dur)}</span>
      </div>
      <div class="tl-summary">${esc(s.output_summary || (disp === "active" ? "in progress…" : "—"))}</div>
      ${open ? sessionDetails(s) : ""}
    </div>
  </div>`;
}

// The visual bucket a session renders as (presentation only — derived from the frozen session
// status + its decision + the mission's lifecycle; adds no runtime state):
//   active   — in flight now (pulses)      waiting   — in flight but the mission is at a human gate
//   completed — sealed OK                  failed    — sealed FAILED, or a "needs attention" verdict
function sessionDisplayState(s, m) {
  if (s.status === "active") return (m && m.status === "awaiting_approval") ? "waiting" : "active";
  if (s.status === "failed") return "failed";
  const verdict = s.decision ? String(s.decision.verdict || "").toLowerCase() : "";
  if (verdict && ATTENTION_VERDICTS.has(verdict)) return "changes";
  return s.status; // "completed" (any future status falls back to a neutral dot)
}

// Fingerprint of everything a rendered node shows, so a live frame re-renders ONLY changed nodes.
function sessionSig(s, disp, open) {
  const dec = s.decision ? s.decision.verdict + ":" + (s.decision.rationale || "") : "";
  return [disp, s.status, s.ended_at, s.duration_ms, s.output_summary, dec, s.parent_session_id,
    (s.child_session_ids || []).length, (s.errors || []).length, (s.artifacts || []).length,
    open ? "open" : "shut"].join("|");
}

function headerSig(m) {
  const active = (m.sessions || []).find((s) => s.status === "active");
  const currentKey = active && active.agent ? active.agent.key : "";
  return [m.found, m.status, m.completed, m.session_count, m.active, m.failed,
    (m.participants || []).map((p) => p.key).join(">"), currentKey].join("|");
}

// Live update: patch only what moved. Refresh the header if it changed; upsert each session node by
// its signature (insert new, replace changed, leave identical ones untouched). No full-page rebuild.
function patchTimeline(next) {
  if (!next || activeTimelineId !== next.mission_id) return; // stale frame for another mission
  const list = document.getElementById("tl-list");
  if (!list) { currentMission = next; drawTimeline(next); return; } // structure not built yet
  const header = document.getElementById("tl-header");
  const hsig = headerSig(next);
  if (header && header.dataset.sig !== hsig) { header.innerHTML = timelineHeader(next); header.dataset.sig = hsig; }
  const sessions = next.sessions || [];
  if (sessions.length && !list.querySelector(".tl-node")) {
    // First sessions arriving over a "no sessions yet" / not-observed placeholder — build the list.
    list.innerHTML = timelineNodes(next);
    list.querySelectorAll(".tl-node").forEach((n) => flashNode(n, "enter"));
    currentMission = next;
    return;
  }
  const seen = new Set();
  sessions.forEach((s) => {
    seen.add(s.session_id);
    const sig = sessionSig(s, sessionDisplayState(s, next), expandedSessions.has(s.session_id));
    const el = document.getElementById("node-" + s.session_id);
    if (!el) {
      list.insertAdjacentHTML("beforeend", sessionNode(s, next));
      flashNode(document.getElementById("node-" + s.session_id), "enter");
    } else if (el.dataset.sig !== sig) {
      el.outerHTML = sessionNode(s, next);
      flashNode(document.getElementById("node-" + s.session_id), "flash");
    }
  });
  // Sessions are append-only history, so this normally removes nothing; defensive against replays.
  list.querySelectorAll(".tl-node").forEach((el) => {
    if (!seen.has(el.id.replace(/^node-/, ""))) el.remove();
  });
  currentMission = next;
}

function flashNode(nodeEl, kind) {
  const target = kind === "enter" ? nodeEl : (nodeEl && nodeEl.querySelector(".tl-body"));
  if (!target) return;
  const cls = kind === "enter" ? "enter" : "flash";
  target.classList.remove(cls);
  void target.offsetWidth; // reflow so the animation restarts even on a rapid re-render
  target.classList.add(cls);
}

// ---- Live stream (SSE) with a polling fallback -----------------------------------------------

function openMissionStream(missionId) {
  closeMissionStream();
  if (!("EventSource" in window)) { startTimelinePolling(missionId); return; }
  let gotFrame = false;
  const es = new EventSource(`/api/pipeline/${encodeURIComponent(missionId)}/stream`);
  missionStream = es;
  es.onmessage = (event) => {
    if (activeTimelineId !== missionId) return;
    gotFrame = true;
    try { patchTimeline(JSON.parse(event.data)); } catch (_) { /* ignore a torn frame */ }
  };
  es.addEventListener("done", () => closeMissionStream()); // mission terminal; final state is shown
  es.onerror = () => {
    // EventSource auto-reconnects on transient errors. If we never connected at all, SSE is likely
    // unavailable here — fall back to polling the REST endpoint (acceptable per the spec).
    if (!gotFrame) { closeMissionStream(); startTimelinePolling(missionId); }
  };
}

function startTimelinePolling(missionId) {
  if (timelineTimer) return;
  timelineTimer = setInterval(async () => {
    if (activeTimelineId !== missionId) { closeMissionStream(); return; }
    try {
      const m = await api(`/api/pipeline/${encodeURIComponent(missionId)}`);
      if (activeTimelineId !== missionId) return;
      patchTimeline(m);
      if (m.found && TERMINAL_MISSION_STATUSES.has(m.status)) closeMissionStream();
    } catch (_) { /* transient; try again next tick */ }
  }, POLL.pipeline || 6000);
}

function closeMissionStream() {
  if (missionStream) { missionStream.close(); missionStream = null; }
  if (timelineTimer) { clearInterval(timelineTimer); timelineTimer = null; }
}

function sessionDetails(s) {
  const d = s.decision;
  const arts = (s.artifacts || []).map((a) => `<span class="chip">${esc(a.kind)}: ${esc(a.title)}</span>`).join(" ")
    || `<span class="muted">none</span>`;
  const errs = (s.errors || []).length
    ? `<div class="tl-errors">${(s.errors || []).map((e) => `<div>${esc(e)}</div>`).join("")}</div>` : "";
  const agentKey = s.agent ? s.agent.key : "";
  const agentLink = s.agent
    ? `<a class="link" href="#agents/${esc(agentKey)}">${esc(s.agent.role)} ↗</a>`
    : "—";
  return `<div class="tl-details" onclick="event.stopPropagation()">
    <div class="kv">
      <dt>Agent</dt><dd>${agentLink}</dd>
      <dt>Session</dt><dd class="mono">${esc(s.session_id)}</dd>
      <dt>Step</dt><dd class="mono">${esc(s.step_id || "—")}</dd>
      <dt>Started</dt><dd>${esc(fmtTime(s.started_at, true))}</dd>
      <dt>Ended</dt><dd>${s.ended_at != null ? esc(fmtTime(s.ended_at, true)) : "—"}</dd>
      <dt>Duration</dt><dd>${s.duration_ms != null ? esc(Math.round(s.duration_ms)) + " ms" : "—"}</dd>
      <dt>Parent</dt><dd class="mono">${esc(s.parent_session_id || "—")}</dd>
      ${d ? `<dt>Decision</dt><dd>${badge("neutral", d.verdict)} <span class="muted">${esc(d.rationale || "")}</span></dd>` : ""}
    </div>
    <div class="tl-arts"><b>Artifacts:</b> ${arts}</div>
    ${errs}
    <div class="tl-output"><b>Output:</b> ${esc(s.output_summary || "—")}</div>
  </div>`;
}

function sessionDepth(s, all) {
  let depth = 0, cur = s;
  while (cur && cur.parent_session_id && depth < 64) {
    cur = findSession(all, cur.parent_session_id);
    depth++;
  }
  return depth;
}
function findSession(all, id) { return (all || []).find((x) => x.session_id === id) || null; }

function fmtTime(ts, withDate) {
  if (ts == null) return "—";
  const d = new Date(ts * 1000);
  return withDate ? d.toLocaleString() : d.toLocaleTimeString();
}

function pipelineBack() {
  return `<button class="btn-back" onclick="location.hash='#pipeline'">← Missions</button>`;
}

function toggleSession(id) {
  if (expandedSessions.has(id)) expandedSessions.delete(id);
  else expandedSessions.add(id);
  const el = document.getElementById("node-" + id);
  // Re-render only the toggled node, in whichever timeline is showing it (agent inspector or mission
  // timeline). Same expand/collapse behavior and Session Details in both — one shared toggle.
  if (activeAgentKey && currentAgent) {
    const s = findSession(currentAgent.sessions, id);
    if (s && el) el.outerHTML = agentSessionNode(s, true);
    return; // in the agent inspector — never fall through to the mission timeline
  }
  if (currentMission) {
    const s = findSession(currentMission.sessions, id);
    if (s && el) el.outerHTML = sessionNode(s, currentMission);
    else drawTimeline(currentMission);
  }
}
window.toggleSession = toggleSession;

// ---- Agents (Agent Experience) ---------------------------------------------------------------
// Agent Cards -> Agent Inspector -> Session -> its Mission, mirroring the Mission Experience. A card
// drills into #agents/{key}; every session (here and in the Mission Timeline) links to the agent
// that ran it and to its mission — so navigation closes the loop Mission -> Timeline -> Session ->
// Agent -> Mission. Reads only RuntimeStateView (/api/agents, /api/agents/{key}); no runtime logic.

let currentAgent = null;
let activeAgentKey = null;
const AGENT_LIVE_STATUSES = new Set(["working", "thinking"]); // actively executing -> pulse

async function renderAgents() {
  let data;
  try {
    data = await api("/api/agents");
  } catch (e) {
    view.innerHTML = errorNotice("agents", e);
    return;
  }
  const agents = data.agents || [];
  const sessions = (data.sessions || []).slice().reverse(); // newest first
  const notPresent = !data.journal_present
    ? `<div class="notice notice-warn">The monitor hasn't written the runtime journal yet
        (<span class="mono">${esc(data.journal_path)}</span>). Showing the idle roster — restart the
        monitor (observability is on by default) to see live activity.</div>`
    : "";
  const cards = agents.map(agentCard).join("") || `<div class="empty">No agents.</div>`;
  const rows = sessions.map(sessionRow).join("")
    || `<tr><td colspan="6" class="muted">No sessions recorded yet.</td></tr>`;
  view.innerHTML = `
    ${notPresent}
    <div class="banner">The autonomous dev-team agents, observed live from the runtime journal. Each
      card is one agent's current state — click it to open the agent's inspector. The table is the
      recent execution pipeline (one session per row, a child session indented under the step it
      followed).</div>
    <div class="section-title">Roster</div>
    <div class="grid agents-grid">${cards}</div>
    <div class="section-title">Recent Sessions</div>
    <table>
      <thead><tr><th>Agent</th><th>Mission</th><th>Step</th><th>Status</th><th>Duration</th><th>Decision</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function agentCard(a) {
  const status = a.status || "offline";
  const active = a.active_session;
  const live = AGENT_LIVE_STATUSES.has(status) ? `<span class="live-dot"></span> ` : "";
  const history = a.decision_history || [];
  const last = history.length ? history[history.length - 1] : null;
  const avg = a.average_duration_ms ? Math.round(a.average_duration_ms) + " ms" : "—";
  const current = active
    ? `<div class="agent-run">▶ ${esc(active.step_id || "step")} · ${esc(shortId(active.mission_id))}</div>`
    : a.current_mission_id
      ? `<div class="agent-run muted">on ${esc(shortId(a.current_mission_id))}</div>`
      : `<div class="agent-run muted">no mission in hand</div>`;
  const key = a.agent ? a.agent.key : "";
  return `<div class="card agent-card clickable" title="Open agent inspector"
      onclick="location.hash='#agents/${esc(key)}'">
    <div class="agent-head"><span class="agent-name">${live}${esc(a.display_name || (a.agent && a.agent.role))}</span>
      ${badge(status, status)}</div>
    <div class="stat-sub">${esc(a.executions || 0)} run(s) · avg ${esc(avg)} · ${esc(a.completed_missions || 0)} mission(s)</div>
    ${current}
    ${last ? `<div class="agent-decision">last verdict: ${badge("neutral", last.verdict)}</div>` : ""}
  </div>`;
}

function sessionRow(s) {
  const dur = s.duration_ms != null ? Math.round(s.duration_ms) + " ms" : "—";
  const dec = s.decision ? badge("neutral", s.decision.verdict) : `<span class="muted">—</span>`;
  const indent = s.parent_session_id ? `<span class="tree-in">↳</span> ` : "";
  const key = s.agent ? s.agent.key : "";
  return `<tr>
    <td>${indent}<a class="link mono" href="#agents/${esc(key)}">${esc(key)}</a></td>
    <td class="mono">${esc(shortId(s.mission_id))}</td>
    <td class="mono">${esc(s.step_id || "—")}</td>
    <td>${badge(s.status, s.status)}</td>
    <td class="muted">${esc(dur)}</td>
    <td>${dec}</td>
  </tr>`;
}

// ---- Agent Inspector (drill-down: Agent Card -> Inspector) ------------------------------------
// Increment 1: identity, live status, current mission, current session. Structured so Increment 2
// (session-history timeline, decisions, handoffs) and Increment 3 (metrics) slot in below without a
// redesign — the same fetch/draw split the Mission Timeline uses.

async function renderAgentInspector(key, initial = true) {
  activeAgentKey = key;
  if (initial) view.innerHTML = agentBack() + `<div class="loading">Loading agent ${esc(key)}…</div>`;
  let a;
  try {
    a = await api(`/api/agents/${encodeURIComponent(key)}`);
  } catch (e) {
    if (activeAgentKey === key) view.innerHTML = agentBack() + errorNotice("agent inspector", e);
    return;
  }
  if (activeAgentKey !== key) return; // navigated away while loading / between polls
  // On a poll, skip the redraw when nothing moved — so an open Session Details stays put.
  if (!initial && currentAgent && agentSig(a) === agentSig(currentAgent)) return;
  currentAgent = a;
  drawAgentInspector(a);
}

// A fingerprint of an agent payload: redraw the inspector only when it actually changes.
function agentSig(a) {
  if (!a || !a.found) return "none";
  const sessions = (a.sessions || [])
    .map((s) => `${s.session_id}:${s.status}:${s.duration_ms}:${s.decision ? s.decision.verdict : ""}`)
    .join("|");
  return [a.status, a.current_mission_id, a.current_step_id, a.executions, sessions].join("~");
}

function drawAgentInspector(a) {
  if (!a.found) {
    view.innerHTML = agentBack() + `<div class="empty">Agent not in the runtime roster.</div>`;
    return;
  }
  const agent = a.agent || {};
  const status = a.status || "offline";
  const live = AGENT_LIVE_STATUSES.has(status)
    ? `<span class="tl-live"><span class="live-dot"></span> live</span>` : "";
  const mission = a.current_mission_id
    ? `<a class="link mono" href="#pipeline/${esc(a.current_mission_id)}">${esc(shortId(a.current_mission_id))} ↗</a>`
    : `<span class="muted">—</span>`;
  const activeSession = (a.sessions || []).find((s) => s.status === "active") || a.active_session;
  const current = activeSession
    ? agentSessionNode(activeSession)
    : `<div class="empty">Idle — no session in hand.</div>`;
  view.innerHTML = agentBack() + `
    <div class="section-title">${agentTitle(a)} ${badge(status, status)} ${live}</div>
    <div class="stat-sub">
      <span class="mono">${esc(agent.key || "—")}</span> · ${esc(agent.subsystem || "—")} /
      ${esc(agent.role || "—")} · last active ${esc(a.last_activity_at != null ? fmtTime(a.last_activity_at, true) : "never")}
    </div>
    <div class="grid" style="margin-top:14px">
      <div class="card"><h3>Runs</h3><div class="stat">${esc(a.executions || 0)}</div>
        <div class="stat-sub">avg ${esc(a.average_duration_ms ? Math.round(a.average_duration_ms) + " ms" : "—")}</div></div>
      <div class="card"><h3>Missions</h3><div class="stat">${esc(a.completed_missions || 0)}</div>
        <div class="stat-sub">completed</div></div>
      <div class="card"><h3>Current Mission</h3><div class="stat" style="font-size:18px">${mission}</div>
        <div class="stat-sub">${esc(a.current_step_id ? "step " + a.current_step_id : "no step in hand")}</div></div>
    </div>
    <div class="section-title">Current Session</div>
    <div class="timeline">${current}</div>
    <div class="section-title">Activity Timeline</div>
    ${agentActivityTimeline(a)}
    <div class="section-title">Operational Metrics</div>
    ${agentMetrics(a.metrics)}`;
}

// Operational metrics for the inspected agent, from its RuntimeStateView-derived `metrics` payload.
// Point-in-time / live figures (not historical reporting); anything the data can't support renders
// as "—" or "insufficient data" — never estimated. Same card/badge/bar vocabulary as elsewhere.
function agentMetrics(m) {
  if (!m) return `<div class="empty">No metrics.</div>`;
  const util = m.utilized
    ? `<span class="badge badge-working">utilized</span>`
    : `<span class="badge badge-idle">idle</span>`;
  const utilPct = m.utilization_ratio != null ? Math.round(m.utilization_ratio * 100) + "%" : "—";
  const activeIdle = m.idle_ms != null
    ? `${metricBar(Math.round((m.utilization_ratio || 0) * 100), "")}
       <div class="stat-sub">active ${esc(fmtDur(m.active_ms))} · idle ${esc(fmtDur(m.idle_ms))}</div>`
    : `<div class="stat-sub muted">insufficient data</div>`;
  const median = m.median_duration_ms != null
    ? esc(fmtDur(m.median_duration_ms))
    : `<span class="muted" style="font-size:14px">need ≥${esc(m.median_min_sessions)} sessions</span>`;
  const cards = `<div class="grid">
    <div class="card"><h3>Current Utilization</h3><div class="stat" style="font-size:20px">${util}</div>
      <div class="stat-sub">${esc(m.status || "—")} · ${esc(m.session_count)} sealed session(s)</div></div>
    <div class="card"><h3>Active vs Idle</h3><div class="stat" style="font-size:22px">${esc(utilPct)}</div>${activeIdle}</div>
    <div class="card"><h3>Avg Session</h3><div class="stat" style="font-size:22px">${esc(m.avg_duration_ms != null ? fmtDur(m.avg_duration_ms) : "—")}</div>
      <div class="stat-sub">over ${esc(m.session_count)} session(s)</div></div>
    <div class="card"><h3>Median Session</h3><div class="stat" style="font-size:22px">${median}</div>
      <div class="stat-sub">50th percentile</div></div>
    <div class="card"><h3>Mission Throughput</h3><div class="stat">${esc(m.missions_completed)}</div>
      <div class="stat-sub">completed · ${esc(m.missions_worked)} worked</div></div>
  </div>`;
  return cards + decisionDistribution(m.decision_distribution)
    + recentMissionHistory(m.recent_missions) + queueParticipation(m.queue);
}

function metricBar(pct, cls) {
  return `<div class="tl-progress"><div class="tl-progress-fill ${esc(cls)}" style="width:${esc(pct)}%"></div></div>`;
}

// The verdict mix as proportional bars — named verdicts first (approve/proceed/request_changes),
// request_changes flagged in the attention colour, consistent with the session buckets.
function decisionDistribution(dist, title = "Decision Distribution") {
  const entries = Object.entries(dist || {});
  if (!entries.length) {
    return `<div class="section-title">${esc(title)}</div>
      <div class="empty">No decisions recorded yet.</div>`;
  }
  const total = entries.reduce((sum, [, count]) => sum + count, 0);
  const order = ["approve", "proceed", "request_changes"];
  const rank = (v) => (order.indexOf(v) < 0 ? order.length : order.indexOf(v));
  entries.sort((a, b) => rank(a[0]) - rank(b[0]) || b[1] - a[1]);
  const rows = entries.map(([verdict, count]) => {
    const pct = total ? Math.round((count / total) * 100) : 0;
    const cls = verdict === "request_changes" ? "danger"
      : (verdict === "approve" || verdict === "proceed") ? "" : "warn";
    return `<div class="metric-row">
      <span class="metric-label">${badge("neutral", verdict)}</span>
      <div class="tl-progress metric-track"><div class="tl-progress-fill ${cls}" style="width:${pct}%"></div></div>
      <span class="metric-count mono">${esc(count)}</span>
    </div>`;
  }).join("");
  return `<div class="section-title">${esc(title)}</div>
    <div class="card">${rows}
      <div class="stat-sub">${esc(total)} decision(s) across the observed window</div></div>`;
}

function recentMissionHistory(list) {
  if (!list || !list.length) {
    return `<div class="section-title">Recent Mission History</div>
      <div class="empty">No missions yet.</div>`;
  }
  const rows = list.map((e) => `<tr>
    <td><a class="link mono" href="#pipeline/${esc(e.mission_id)}">${esc(shortId(e.mission_id))} ↗</a></td>
    <td>${e.verdict ? badge("neutral", e.verdict) : `<span class="muted">—</span>`}</td>
    <td>${badge(e.status || "unknown", e.status || "—")}</td>
    <td class="muted">${esc(e.at != null ? fmtTime(e.at, true) : "—")}</td>
  </tr>`).join("");
  return `<div class="section-title">Recent Mission History</div>
    <table><thead><tr><th>Mission</th><th>Verdict</th><th>Status</th><th>When</th></tr></thead>
      <tbody>${rows}</tbody></table>`;
}

function queueParticipation(q) {
  if (!q || !q.participating) {
    return `<div class="section-title">Current Queue Participation</div>
      <div class="card"><div class="stat-sub">Not in a mission right now.</div></div>`;
  }
  const mission = q.mission_id
    ? `<a class="link mono" href="#pipeline/${esc(q.mission_id)}">${esc(shortId(q.mission_id))} ↗</a>`
    : `<span class="muted">—</span>`;
  return `<div class="section-title">Current Queue Participation</div>
    <div class="card">
      <div class="stat" style="font-size:18px">${badge(q.status || "idle", q.status || "idle")} on ${mission}</div>
      <div class="stat-sub">${esc(q.step_id ? "step " + q.step_id : "no step in hand")}</div>
    </div>`;
}

function fmtDur(ms) {
  if (ms == null) return "—";
  if (ms < 1000) return Math.round(ms) + " ms";
  const seconds = ms / 1000;
  if (seconds < 60) return (Math.round(seconds * 10) / 10) + " s";
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
}

// The agent's completed sessions in chronological order — its work across missions. Each row is an
// interactive session node (click to expand the same Session Details as the Mission Timeline). The
// active session lives in the summary's Current Session panel above, so it is not repeated here.
function agentActivityTimeline(a) {
  const sealed = (a.sessions || []).filter((s) => s.status !== "active");
  if (!sealed.length) return `<div class="empty">No completed sessions yet.</div>`;
  return `<div class="timeline">${sealed.map((s) => agentSessionNode(s, true)).join("")}</div>`;
}

// One session as it reads in an agent context: step + status + decision + handoff-in + a link back
// to its mission, using the SAME dot/badge vocabulary as the Mission Timeline. `interactive` adds
// the id + click-to-expand and reuses sessionDetails() for the inline expansion (identical to the
// Mission Timeline's Session Details); the summary's Current Session panel renders it flat.
function agentSessionNode(s, interactive = false) {
  const disp = sessionDisplayState(s, null); // no mission context: an active session stays "active"
  const dur = s.duration_ms != null ? Math.round(s.duration_ms) + " ms"
    : (disp === "active" ? "running…" : "—");
  const dec = s.decision ? badge("neutral", s.decision.verdict) : "";
  const live = disp === "active" ? " live" : "";
  const from = s.handoff_from && s.agent && s.handoff_from.key !== s.agent.key
    ? `<span class="handoff">⇄ from ${esc(s.handoff_from.role)}</span>` : "";
  const missionLink = `<span class="handoff">on <a class="link" href="#pipeline/${esc(s.mission_id)}">${esc(shortId(s.mission_id))} ↗</a></span>`;
  const open = interactive && expandedSessions.has(s.session_id);
  const id = interactive ? ` id="node-${esc(s.session_id)}"` : "";
  const click = interactive ? ` onclick="toggleSession('${esc(s.session_id)}')"` : "";
  return `<div class="tl-node"${id}>
    <div class="tl-dot tl-${esc(disp)}${live}"></div>
    <div class="tl-body ${open ? "open" : ""}"${click}>
      <div class="tl-head">
        <span class="chip mono">${esc(s.step_id || "step")}</span> ${badge(s.status, s.status)} ${dec} ${from} ${missionLink}
        <span class="tl-time muted">${esc(dur)}</span>
      </div>
      <div class="tl-summary">${esc(s.output_summary || (disp === "active" ? "in progress…" : "—"))}</div>
      ${open ? sessionDetails(s) : ""}
    </div>
  </div>`;
}

function agentTitle(a) {
  return `<span class="agent-name">${esc(a.display_name || (a.agent && a.agent.role) || a.agent_key || "agent")}</span>`;
}

function agentBack() {
  return `<button class="btn-back" onclick="location.hash='#agents'">← Agents</button>`;
}

function shortId(id) {
  const s = String(id ?? "");
  return s.length > 10 ? s.slice(0, 8) + "…" : s;
}

// ---- Open Missions ---------------------------------------------------------------------------

async function renderMissions() {
  let data;
  try {
    data = await api("/api/missions");
  } catch (e) {
    view.innerHTML = errorNotice("open missions", e);
    return;
  }
  checkNotifications(data.missions || []);
  const banner = `<div class="banner">Rows are open PRs with their live CI verdict. A <b>failing</b> PR
    is the actionable set — click <b>View</b> to re-derive its diagnosis &amp; patch and decide.
    "daemon" columns are the running monitor's own attempt, parsed from its log.</div>`;
  if (!data.missions || !data.missions.length) {
    view.innerHTML = banner + (data.error ? `<div class="notice notice-warn">${esc(data.error)}</div>` : "") +
      `<div class="empty">No open pull requests on the monitored repository.</div>`;
    return;
  }
  const rows = data.missions.map(missionRow).join("");
  view.innerHTML = banner + `
    <table>
      <thead><tr>
        <th>PR</th><th>Repository</th><th>Attempt</th><th>Confidence</th>
        <th>Category</th><th>CI Status</th><th></th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function missionRow(m) {
  const attempt = m.daemon_attempt != null
    ? `${esc(m.daemon_attempt)}${m.max_attempts ? "/" + esc(m.max_attempts) : ""} <span class="muted">(daemon)</span>`
    : `<span class="muted">—</span>`;
  const title = m.title ? `<div class="muted" style="font-size:12px">${esc(m.title)}</div>` : "";
  return `<tr>
    <td><a class="link" href="${esc(m.html_url)}" target="_blank" rel="noopener">#${esc(m.pr_number)}</a>${title}</td>
    <td class="mono">${esc(m.repo)}</td>
    <td>${attempt}</td>
    <td class="muted">on view</td>
    <td class="muted">on view</td>
    <td>${badge(m.ci_status)}</td>
    <td class="row-actions">
      <button class="btn btn-view" onclick="location.hash='#mission/${esc(m.pr_number)}'">View</button>
    </td>
  </tr>`;
}

// ---- Mission Details -------------------------------------------------------------------------

async function renderMissionDetail(prNumber) {
  view.innerHTML = `<button class="btn-back" onclick="location.hash='#missions'">← Open Missions</button>
    <div class="loading">Re-deriving diagnosis &amp; patch for PR #${esc(prNumber)}…</div>`;
  let m;
  try {
    m = await api(`/api/missions/${encodeURIComponent(prNumber)}`);
  } catch (e) {
    view.innerHTML = backLink() + errorNotice("mission detail", e);
    return;
  }
  const header = `${backLink()}
    <div class="section-title">PR
      <a class="link" href="${esc(m.html_url)}" target="_blank" rel="noopener">#${esc(m.pr_number)}</a>
      on <span class="mono">${esc(m.repo)}</span> ${m.mission_status ? badge(m.mission_status) : ""}</div>`;

  if (m.state !== "awaiting_approval" && m.state !== "no_patch") {
    view.innerHTML = header + `<div class="notice notice-warn">${esc(m.message || m.state)}</div>`;
    return;
  }

  const findings = (m.findings || []).map(
    (f) => `<li>${esc(f.file)}:${esc(f.line)} — ${esc(f.message)}${f.code ? ` <span class="muted">[${esc(f.code)}]</span>` : ""}</li>`
  ).join("");
  const affected = (m.affected_files || []).map((f) => `<div class="mono">${esc(f)}</div>`).join("") || `<span class="muted">—</span>`;
  const confidence = m.confidence != null ? Math.round(m.confidence * 100) + "%" : "—";

  const actions = m.state === "awaiting_approval"
    ? `<div class="row-actions" style="margin-top:16px">
         <button class="btn btn-approve" onclick="decide('approve','${esc(m.mission_id)}',${esc(m.pr_number)})">Approve &amp; Land</button>
         <button class="btn btn-reject" onclick="decide('reject','${esc(m.mission_id)}',${esc(m.pr_number)})">Reject</button>
       </div>
       <div class="stat-sub" style="margin-top:8px">Approve applies the patch and pushes (git apply → commit → push → PR) via the existing gateway. Reject cancels — no repo change.</div>`
    : `<div class="notice notice-warn">${esc(m.message)}</div>`;

  view.innerHTML = header + `
    <div class="card">
      <h3>Diagnosis</h3>
      <div class="kv">
        <dt>Category</dt><dd>${esc(m.category || "—")}</dd>
        <dt>Confidence</dt><dd>${esc(confidence)}</dd>
        <dt>Summary</dt><dd>${esc(m.summary || "—")}</dd>
        <dt>Failing step</dt><dd>${esc(m.failing_job || "—")} → ${esc(m.failing_step || "—")}</dd>
        <dt>Mission</dt><dd>${esc(m.mission_id || "—")}</dd>
      </div>
    </div>
    <div class="grid" style="margin-top:14px">
      <div class="card"><h3>Affected Files</h3>${affected}</div>
      <div class="card"><h3>Findings (${(m.findings || []).length})</h3><ul class="findings">${findings || "<li class='muted'>none</li>"}</ul></div>
    </div>
    <div class="section-title">Patch Diff</div>
    ${m.diff ? renderDiff(m.diff) : `<div class="empty">No diff.</div>`}
    ${actions}`;
}

function renderDiff(text) {
  const lines = String(text).split("\n").map((line) => {
    let cls = "";
    if (line.startsWith("+++") || line.startsWith("---") || line.startsWith("diff ") || line.startsWith("index ")) cls = "meta";
    else if (line.startsWith("@@")) cls = "hunk";
    else if (line.startsWith("+")) cls = "add";
    else if (line.startsWith("-")) cls = "del";
    return `<div class="${cls}">${esc(line) || "&nbsp;"}</div>`;
  });
  return `<div class="diff">${lines.join("")}</div>`;
}

async function decide(action, missionId, prNumber) {
  const summary = action === "approve"
    ? "APPROVE and LAND this fix.\n\nThis applies the patch and pushes a commit + opens/updates the PR."
    : "REJECT this fix.\n\nThe mission is cancelled — no repository change.";
  if (!window.confirm(`${summary}\n\nMission: ${missionId}\n\nContinue?`)) return;
  document.querySelectorAll(".btn-approve, .btn-reject").forEach((b) => (b.disabled = true));
  try {
    const q = prNumber != null ? `?pr_number=${encodeURIComponent(prNumber)}` : "";
    const res = await api(`/api/missions/${encodeURIComponent(missionId)}/${action}${q}`, { method: "POST" });
    window.alert(`${action === "approve" ? "Approved" : "Rejected"} — mission ${res.status}.` + (res.pr_url ? `\n\n${res.pr_url}` : ""));
    location.hash = "#missions";
  } catch (e) {
    window.alert(`Failed: ${e.message}`);
    document.querySelectorAll(".btn-approve, .btn-reject").forEach((b) => (b.disabled = false));
  }
}
window.decide = decide;

// ---- Logs ------------------------------------------------------------------------------------

async function renderLogs() {
  const q = (document.getElementById("log-q") || {}).value || "";
  const level = (document.getElementById("log-level") || {}).value || "";
  let data;
  try {
    data = await api(`/api/logs?tail=400${q ? "&q=" + encodeURIComponent(q) : ""}${level ? "&level=" + encodeURIComponent(level) : ""}`);
  } catch (e) {
    view.innerHTML = errorNotice("logs", e);
    return;
  }
  const lines = (data.lines || []).map(logLine).join("") || `<div class="muted">No matching log lines.</div>`;
  view.innerHTML = `
    <div class="toolbar">
      <input type="text" id="log-q" placeholder="search…" value="${esc(q)}" oninput="debouncedLogs()" />
      <select id="log-level" onchange="renderLogs()">
        <option value="">all levels</option>
        <option value="INFO"${level === "INFO" ? " selected" : ""}>INFO</option>
        <option value="WARNING"${level === "WARNING" ? " selected" : ""}>WARNING</option>
        <option value="ERROR"${level === "ERROR" ? " selected" : ""}>ERROR</option>
      </select>
      <span class="muted mono">${esc(data.log_path || "")}</span>
    </div>
    <div class="logbox" id="logbox">${lines}</div>`;
  const box = document.getElementById("logbox");
  if (box) box.scrollTop = box.scrollHeight;
}

function logLine(e) {
  if (!e.timestamp) return `<div class="logline muted">${esc(e.raw)}</div>`;
  return `<div class="logline"><span class="ts">${esc(e.timestamp)}</span> <span class="lvl-${esc(e.level)}">${esc(e.level)}</span> ${esc(e.message)}</div>`;
}

let logDebounce = null;
function debouncedLogs() {
  clearTimeout(logDebounce);
  logDebounce = setTimeout(renderLogs, 300);
}
window.debouncedLogs = debouncedLogs;
window.renderLogs = renderLogs;

// ---- Metrics ---------------------------------------------------------------------------------

async function renderMetrics() {
  let data;
  try {
    data = await api("/api/metrics?window=today");
  } catch (e) {
    view.innerHTML = errorNotice("metrics", e);
    return;
  }
  const tiles = [
    ["Detected Today", data.detected, "failures the monitor acted on"],
    ["Opened Missions", data.opened_missions, "reached the approval gate"],
    ["Approved", data.approved, "landed via this dashboard"],
    ["Rejected", data.rejected, "cancelled via this dashboard"],
    ["Declined", data.declined, "Developer produced no patch"],
    ["Average Attempts", data.average_attempts, "per opened mission"],
    ["Green CI", data.green_ci, "chains resolved"],
    ["Running Workers", data.running_workers, "monitor process"],
  ];
  view.innerHTML = `
    <div class="banner">Counts are for <b>today</b>, parsed from the monitor log. Approved/Rejected
      are the decisions made <b>through this dashboard</b> (the daemon never approves).</div>
    <div class="grid">
      ${tiles.map(([label, val, sub]) => `<div class="card"><h3>${esc(label)}</h3>
        <div class="stat">${esc(val != null ? val : "—")}</div><div class="stat-sub">${esc(sub)}</div></div>`).join("")}
    </div>`;
}

// ---- Settings --------------------------------------------------------------------------------

async function renderSettings() {
  let data;
  try {
    data = await api("/api/settings");
  } catch (e) {
    view.innerHTML = errorNotice("settings", e);
    return;
  }
  const gh = data.github || {};
  const worker = data.worker || {};
  view.innerHTML = `
    <div class="card">
      <h3>Deployment (read-only — from the LaunchAgent plist)</h3>
      <div class="kv">
        <dt>Repositories</dt><dd>${(data.repos || []).map(esc).join(", ") || "—"}</dd>
        <dt>Poll interval</dt><dd>${data.poll_seconds != null ? esc(data.poll_seconds) + "s" : "—"}</dd>
        <dt>Max attempts</dt><dd>${data.max_attempts != null ? esc(data.max_attempts) : "—"}</dd>
        <dt>Repo root</dt><dd>${esc(data.repo_root)}</dd>
        <dt>Log file</dt><dd>${esc(data.log_path)}</dd>
        <dt>Plist</dt><dd>${esc(data.plist_path)}</dd>
        <dt>Actions log</dt><dd>${esc(data.actions_log_path)}</dd>
      </div>
    </div>
    <div class="grid" style="margin-top:14px">
      <div class="card"><h3>Worker</h3>
        <div class="stat" style="font-size:20px">${worker.running ? "🟢 running" : "🔴 " + esc(worker.state || "stopped")}</div>
        <div class="stat-sub">${esc(worker.label || "")}${worker.pid ? " · pid " + esc(worker.pid) : ""}</div></div>
      <div class="card"><h3>GitHub Connectivity</h3>
        <div class="stat" style="font-size:20px">${gh.ok ? "🟢 connected" : "🔴 error"}</div>
        <div class="stat-sub">${esc(gh.message || "")}</div></div>
    </div>`;
}

// ---- Notifications ---------------------------------------------------------------------------

function checkNotifications(missions) {
  const actionable = new Set(missions.filter((m) => m.actionable).map((m) => m.pr_number));
  if (knownActionable !== null && "Notification" in window && Notification.permission === "granted") {
    for (const pr of actionable) {
      if (!knownActionable.has(pr)) {
        const m = missions.find((x) => x.pr_number === pr);
        new Notification("Mission awaiting approval", {
          body: `PR #${pr}${m && m.title ? " — " + m.title : ""}`,
        });
      }
    }
  }
  knownActionable = actionable;
}

async function notifyPoll() {
  try {
    const data = await api("/api/missions");
    checkNotifications(data.missions || []);
  } catch (_) { /* transient; try again next tick */ }
}

// ---- Router / polling ------------------------------------------------------------------------

// ---- Jobs (AI Organization Jobs — recurring departmental responsibilities) --------------------

async function renderJobs() {
  let data;
  try {
    data = await api("/api/jobs");
  } catch (e) {
    view.innerHTML = errorNotice("jobs", e);
    return;
  }
  const jobs = data.jobs || [];
  const notPresent = !data.snapshot_present
    ? `<div class="notice notice-warn">The organization service hasn't written the jobs snapshot yet
        (<span class="mono">${esc(data.jobs_path)}</span>). Start the organization service to populate
        the departmental jobs.</div>`
    : "";
  const rows = jobs.map(jobRow).join("")
    || `<tr><td colspan="8" class="muted">No jobs yet.</td></tr>`;
  view.innerHTML = `
    ${notPresent}
    <div class="banner">The AI Organization's recurring departmental jobs — each agent owns scheduled
      responsibilities that run automatically and open a Mission only when real evidence requires it.
      An idle job is a healthy job: it inspected its source and found nothing to do.</div>
    <div class="section-title">Organization Jobs</div>
    <table>
      <thead><tr><th>Job</th><th>Owner</th><th>Status</th><th>Health</th><th>Last Run</th>
        <th>Next Run</th><th>Duration</th><th>Missions Created</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function jobRow(j) {
  const dur = j.last_duration_ms != null ? Math.round(j.last_duration_ms) + " ms" : "—";
  const cadence = j.every_tick ? "every tick" : cadenceLabel(j.schedule_seconds);
  const mission = j.last_mission_id
    ? ` · <a class="link mono" href="#pipeline/${esc(j.last_mission_id)}">${esc(shortId(j.last_mission_id))}</a>`
    : "";
  return `<tr>
    <td><span class="agent-name">${esc(j.name)}</span>
      <div class="stat-sub mono">${esc(j.id)} · ${esc(cadence)}</div></td>
    <td>${esc((j.owner_agent || "").toUpperCase())}</td>
    <td>${badge(jobStatusKind(j.status), j.status || "—")}</td>
    <td>${badge(jobHealthKind(j.health), j.health || "unknown")}</td>
    <td class="muted">${esc(fmtAgo(j.last_run))}</td>
    <td class="muted">${esc(fmtIn(j.next_run, j.every_tick))}</td>
    <td class="muted">${esc(dur)}</td>
    <td>${esc(j.created_missions || 0)}${mission}</td>
  </tr>`;
}

function cadenceLabel(sec) {
  if (!sec) return "—";
  if (sec % 3600 === 0) return sec / 3600 + "h";
  if (sec % 60 === 0) return sec / 60 + "m";
  return sec + "s";
}

function fmtAgo(epoch) {
  if (epoch == null) return "never";
  const diff = Date.now() / 1000 - epoch;
  if (diff < 60) return "just now";
  if (diff < 3600) return Math.round(diff / 60) + "m ago";
  return Math.round(diff / 3600) + "h ago";
}

function fmtIn(epoch, everyTick) {
  if (everyTick) return "every tick";
  if (epoch == null) return "—";
  const diff = epoch - Date.now() / 1000;
  if (diff <= 0) return "due";
  if (diff < 60) return "in " + Math.round(diff) + "s";
  if (diff < 3600) return "in " + Math.round(diff / 60) + "m";
  return "in " + Math.round(diff / 3600) + "h";
}

function jobStatusKind(status) {
  return { idle: "idle", acted: "working", error: "blocked", pending: "neutral", disabled: "offline" }[status]
    || "neutral";
}

function jobHealthKind(health) {
  return { healthy: "idle", degraded: "waiting", unhealthy: "blocked" }[health] || "neutral";
}

async function renderConnectors() {
  let data;
  try {
    data = await api("/api/connectors");
  } catch (e) {
    view.innerHTML = errorNotice("connectors", e);
    return;
  }
  const connectors = data.connectors || [];
  const notPresent = !data.snapshot_present
    ? `<div class="notice notice-warn">The organization service hasn't written the connectors
        snapshot yet (<span class="mono">${esc(data.path)}</span>).</div>`
    : "";
  const rows = connectors.map(connectorRow).join("")
    || `<tr><td colspan="7" class="muted">No connectors yet.</td></tr>`;
  view.innerHTML = `
    ${notPresent}
    <div class="banner">The read-only integration layer. Every job obtains evidence through a
      connector — never a direct integration. A connector that cannot reach its source reports
      Unavailable, and its job opens no mission (evidence is never fabricated).</div>
    <div class="section-title">Connectors</div>
    <table>
      <thead><tr><th>Connector</th><th>Owner</th><th>Health</th><th>Latency</th><th>Last Sync</th>
        <th>Owner Jobs</th><th>Status</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function connectorRow(c) {
  const lat = c.latency_ms != null ? Math.round(c.latency_ms) + " ms" : "—";
  const jobs = (c.owner_jobs || []).length;
  return `<tr>
    <td><span class="agent-name">${esc(c.name)}</span>
      <div class="stat-sub mono">${esc(c.id)} · ${esc(c.type)}</div></td>
    <td>${esc((c.owner || "").toUpperCase())}</td>
    <td>${badge(connectorHealthKind(c.health), c.health || "unknown")}</td>
    <td class="muted">${esc(lat)}</td>
    <td class="muted">${esc(fmtAgo(c.last_check))}</td>
    <td class="muted" title="${esc((c.owner_jobs || []).join(', '))}">${esc(jobs)} job(s)</td>
    <td>${badge(connectorStatusKind(c.status), c.status || "—")}</td>
  </tr>`;
}

function connectorHealthKind(h) {
  return { healthy: "idle", warning: "waiting", unavailable: "offline" }[h] || "neutral";
}

function connectorStatusKind(s) {
  return { ok: "idle", unavailable: "offline", error: "blocked", disabled: "neutral" }[s] || "neutral";
}

async function renderLifecycle() {
  let data;
  try {
    data = await api("/api/lifecycle");
  } catch (e) {
    view.innerHTML = errorNotice("lifecycle", e);
    return;
  }
  const problems = data.problems || [];
  const m = data.metrics || {};
  const num = (v) => (v == null ? "—" : v);
  const secs = (v) => (v == null ? "—" : Math.round(v) + "s");
  const notPresent = !data.snapshot_present
    ? `<div class="notice notice-warn">The organization service hasn't written the lifecycle
        snapshot yet (<span class="mono">${esc(data.path)}</span>).</div>`
    : "";
  const rows = problems.map(problemRow).join("")
    || `<tr><td colspan="4" class="muted">No active problems — the organization is healthy.</td></tr>`;
  view.innerHTML = `
    ${notPresent}
    <div class="banner">The single operational path. Every problem is owned by the
      LifecycleCoordinator: detected by a connector, driven NEW → IN_PROGRESS → VERIFIED → CLOSED, and
      verified against a real re-observation. This is a read-only view of that state.</div>
    <div class="banner"><b>${num(m.active_problems)}</b> active&nbsp;·&nbsp; MTTV <b>${secs(m.mean_time_to_verify)}</b>
      &nbsp;·&nbsp; MTTC <b>${secs(m.mean_time_to_close)}</b> &nbsp;·&nbsp; ${num(m.escalation_count)} escalations
      &nbsp;·&nbsp; ${num(m.retry_count)} retries &nbsp;·&nbsp; ${num(m.verification_failures)} verify-failures</div>
    <div class="section-title">Active problems</div>
    <table>
      <thead><tr><th>Problem</th><th>Type</th><th>Severity</th><th>State</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function problemRow(p) {
  return `<tr>
    <td><span class="agent-name">${esc(p.asset)}</span>
      <div class="stat-sub mono">${esc(p.evidence_signature)}</div></td>
    <td>${esc(p.mission_type)}</td>
    <td>${badge(severityKind(p.severity), p.severity || "—")}</td>
    <td>${badge(problemStateKind(p.state), p.state || "—")}</td>
  </tr>`;
}

function problemStateKind(s) {
  return { new: "waiting", in_progress: "working", verified: "idle", closed: "idle",
    escalated: "blocked" }[s] || "neutral";
}

function severityKind(s) {
  return { low: "neutral", medium: "waiting", high: "waiting", critical: "blocked" }[s] || "neutral";
}

const routes = {
  executive: renderExecutive,
  overview: renderOverview,
  pipeline: renderPipeline,
  agents: renderAgents,
  lifecycle: renderLifecycle,
  jobs: renderJobs,
  connectors: renderConnectors,
  missions: renderMissions,
  logs: renderLogs,
  metrics: renderMetrics,
  settings: renderSettings,
};

function route() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  closeMissionStream();     // tear down any live timeline stream when navigating
  activeTimelineId = null;  // ignore any late frames from the mission we're leaving
  activeAgentKey = null;    // ignore any late poll from the agent we're leaving
  const hash = (location.hash || "#executive").slice(1);
  if (hash.startsWith("mission/")) {
    const pr = parseInt(hash.split("/")[1], 10);
    setActiveTab("missions");
    renderMissionDetail(pr);
    return;
  }
  if (hash.startsWith("pipeline/")) {
    // Mission Timeline drill-down, live: renderMissionTimeline loads the initial state then opens
    // the SSE stream (no page-level poll — the stream drives updates; render path is split for it).
    setActiveTab("pipeline");
    renderMissionTimeline(decodeURIComponent(hash.slice("pipeline/".length)));
    return;
  }
  if (hash.startsWith("agents/")) {
    // Agent Inspector drill-down. Polls on the agents interval, re-fetching without a loading flash
    // (initial=false) so the live status/session stay current — mirroring the roster's own poll.
    setActiveTab("agents");
    const key = decodeURIComponent(hash.slice("agents/".length));
    renderAgentInspector(key);
    if (POLL.agents) pollTimer = setInterval(() => renderAgentInspector(key, false), POLL.agents);
    return;
  }
  const tab = routes[hash] ? hash : "executive";
  currentTab = tab;
  setActiveTab(tab);
  routes[tab]();
  const interval = POLL[tab];
  if (interval) pollTimer = setInterval(routes[tab], interval);
}

function setActiveTab(tab) {
  document.querySelectorAll(".tabs a").forEach((a) =>
    a.classList.toggle("active", a.dataset.tab === tab)
  );
}

function backLink() {
  return `<button class="btn-back" onclick="location.hash='#missions'">← Open Missions</button>`;
}

function errorNotice(what, err) {
  return `<div class="notice notice-warn">Could not load ${esc(what)}: ${esc(err.message)}</div>`;
}

document.getElementById("notify-btn").addEventListener("click", async () => {
  if (!("Notification" in window)) { window.alert("This browser has no Notification API."); return; }
  const perm = await Notification.requestPermission();
  if (perm === "granted") new Notification("Notifications on", { body: "You'll be alerted when a mission awaits approval." });
});

function tickClock() {
  const el = document.getElementById("clock");
  if (el) el.textContent = new Date().toLocaleTimeString();
}

window.addEventListener("hashchange", route);
tickClock();
setInterval(tickClock, 1000);
notifyPoll(); // seed knownActionable (no notification on first load)
setInterval(notifyPoll, 45000);
route();
