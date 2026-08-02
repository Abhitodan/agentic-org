/* Agentic Org command center - light enterprise ops console.
   All values come from the platform API. Empty states when data is missing. */

const h = React.createElement;

const PIPELINE_LABELS = {
  intake: "Intake",
  map_repository: "Repo map",
  create_brain: "Brain",
  draft_charter: "Charter",
  request_decision: "Decision",
  plan: "Plan",
  implement: "Implement",
  merge: "Merge",
  request_release: "Release gate",
  release: "Release",
};

const ROLE_SHORT = {
  "intake-agent": "Intake",
  "repository-agent": "Repo",
  "product-manager-agent": "PM",
  "planning-agent": "Plan",
  "backend-agent": "Build",
  "release-agent": "Release",
  human: "Human",
};

const EVENT_TONE = {
  "workflow.transition": "info",
  "workflow.blocked": "bad",
  "budget.exceeded": "bad",
  "approval.requested": "warn",
  "approval.granted": "ok",
  "approval.rejected": "bad",
  "release.approval.requested": "warn",
  "charter.drafted": "ok",
  "plan.created": "ok",
  "implementation.succeeded": "ok",
  "merge.succeeded": "ok",
  "release.succeeded": "ok",
  "docs.indexed": "info",
  "command.issued": "info",
  "checkpoint.restored": "warn",
};

const SPEAKER_FOR_EVENT = {
  "intake.classified": "intake-agent",
  "repository.mapped": "repository-agent",
  "brain.updated": "repository-agent",
  "charter.drafted": "product-manager-agent",
  "plan.created": "planning-agent",
  "implementation.succeeded": "backend-agent",
  "implementation.failed": "backend-agent",
  "merge.succeeded": "release-agent",
  "release.succeeded": "release-agent",
  "release.approval.requested": "human",
  "approval.requested": "human",
  "approval.granted": "human",
  "approval.rejected": "human",
  "workflow.blocked": "human",
  "budget.exceeded": "human",
  "docs.indexed": "repository-agent",
};

function tone(type) { return EVENT_TONE[type] || ""; }

function clockTime(iso) {
  if (!iso) return "--:--:--";
  const d = new Date(iso);
  return isNaN(d) ? "--:--:--" : d.toTimeString().slice(0, 8);
}

function money(n) { return "$" + Number(n || 0).toFixed(4); }
function num(n) { return Number(n || 0).toLocaleString(); }

function pct(used, limit) {
  if (!limit) return 0;
  return Math.max(0, Math.min(100, (used / limit) * 100));
}

function level(p) { return p >= 90 ? "bad" : p >= 65 ? "warn" : ""; }

function stateClass(state) {
  return "badge st-" + String(state || "unknown").toLowerCase();
}

function initials(role) {
  const label = ROLE_SHORT[role] || role || "?";
  return label.slice(0, 2).toUpperCase();
}

function roleLabel(role) {
  if (!role) return "System";
  return ROLE_SHORT[role] || role.replace(/-agent$/, "").replace(/-/g, " ");
}

function eventSummary(ev) {
  const p = ev.payload || {};
  if (ev.event_type === "workflow.transition") {
    const base = `${p.from} -> ${p.to}`;
    return p.reason ? `${base} - ${p.reason}` : base;
  }
  if (p.reason) return p.reason;
  if (p.model) return `model ${p.model}`;
  if (p.action) return `action ${p.action}`;
  if (p.files !== undefined) return `${p.files} files mapped`;
  if (p.sections) return `sections: ${p.sections.join(", ")}`;
  if (p.gate) return `gate ${p.gate}`;
  if (p.files_indexed !== undefined) {
    return `indexed ${p.files_indexed} files | ${p.vector_chunks || 0} chunks`;
  }
  if (p.name) return p.name;
  return "";
}

function theaterLine(ev) {
  const summary = eventSummary(ev);
  const map = {
    "intake.classified": "Classified the request and opened the workflow.",
    "repository.mapped": summary || "Mapped the repository.",
    "brain.updated": "Updated the feature brain.",
    "charter.drafted": "Drafted the feature charter.",
    "plan.created": "Created the implementation plan.",
    "implementation.succeeded": "Implementation passed tests.",
    "implementation.failed": summary || "Implementation failed tests.",
    "merge.succeeded": "Merged the agent branch.",
    "release.succeeded": "Created the release.",
    "approval.requested": summary || "Human decision required.",
    "release.approval.requested": summary || "Release approval required.",
    "approval.granted": summary || "Gate approved.",
    "approval.rejected": summary || "Gate rejected.",
    "workflow.blocked": summary || "Workflow blocked.",
    "budget.exceeded": "Budget hard-stop reached.",
    "docs.indexed": summary || "Document index rebuilt.",
    "workflow.transition": summary || "State advanced.",
    "command.issued": summary || "Command issued.",
  };
  return map[ev.event_type] || summary || ev.event_type;
}

function pendingGateFor(workflow) {
  if (!workflow) return null;
  if (workflow.state === "AWAITING_DECISION" && !workflow.approval_granted) {
    return "plan-approval";
  }
  if (workflow.state === "AWAITING_APPROVAL" && !workflow.release_approval_granted) {
    return "release-approval";
  }
  return null;
}

/* --------------------------------------------------------------- primitives */

function Chip({ kind, label, live }) {
  return h("span", { className: "chip " + (kind || "") },
    h("span", { className: "dot" + (live ? " live" : "") }), label);
}

function Panel({ title, count, children, className, bodyClass, head, footer }) {
  return h("section", { className: "panel " + (className || "") },
    h("div", { className: "panel-head" },
      h("h2", null, title),
      count !== undefined && count !== null
        ? h("span", { className: "count" }, count) : null,
      head || null),
    h("div", { className: "panel-body " + (bodyClass || "") }, children),
    footer ? h("div", { className: "panel-foot" }, footer) : null);
}

function Empty({ text }) { return h("div", { className: "empty" }, text); }

/* ---------------------------------------------------------------- pipeline */

function PipelineStrip({ workflow }) {
  if (!workflow) {
    return h("div", { className: "pipeline-strip" },
      h(Empty, { text: "Select a workflow to see Mode A progress" }));
  }
  const nodes = workflow.pipeline || [];
  return h("div", { className: "pipeline-strip" },
    h("div", { className: "pipe-meta" },
      h("div", null,
        h("span", { className: "name" },
          (workflow.project_name || "?") + " / " + (workflow.feature_name || "?")),
        workflow.is_running
          ? h("span", { className: "badge st-running", style: { marginLeft: 8 } }, "Running")
          : h("span", { className: stateClass(workflow.state), style: { marginLeft: 8 } },
              workflow.state)),
      h("span", { className: "id" }, workflow.id)),
    workflow.objective
      ? h("div", {
          className: "objective",
          style: { marginBottom: 8, maxHeight: 40, overflow: "hidden",
                   textOverflow: "ellipsis", whiteSpace: "nowrap" },
          title: workflow.objective,
        }, workflow.objective)
      : null,
    h("div", { className: "pipeline-track" },
      nodes.map((node, i) => h("div", {
        key: node.key,
        className: "pipe-step " + node.status,
        style: { animationDelay: (i * 0.03) + "s" },
      },
        h("div", { className: "pipe-node" },
          node.status === "done" ? "OK"
            : node.status === "blocked" ? "x" : String(i + 1)),
        h("div", { className: "pipe-label" },
          PIPELINE_LABELS[node.key] || node.key),
        node.gate ? h("div", { className: "pipe-gate" }, "Human gate") : null))));
}

/* ---------------------------------------------------------------- theater */

function buildTurns(workflow, allEvents) {
  const id = workflow && workflow.id;
  const events = (allEvents || [])
    .filter((e) => !id || e.workflow_id === id)
    .slice()
    .reverse();
  const turns = [];
  let prevRole = null;
  for (const ev of events) {
    const role = ev.agent_role || SPEAKER_FOR_EVENT[ev.event_type] || "system";
    if (prevRole && prevRole !== role && turns.length) {
      turns.push({ kind: "handoff", key: "h-" + ev.event_id, from: prevRole, to: role });
    }
    turns.push({
      kind: "turn",
      key: ev.event_id,
      role,
      human: role === "human",
      time: ev.timestamp,
      text: theaterLine(ev),
      type: ev.event_type,
    });
    prevRole = role;
  }
  return turns;
}

function CastColumn({ roles, speaking, side }) {
  return h("div", { className: "cast", "aria-label": side + " cast" },
    roles.map((role) => {
      const live = speaking.has(role);
      return h("div", {
        key: role,
        className: "cast-agent" + (live ? " speaking" : "") + (role === "human" ? " human" : ""),
      },
        h("div", {
          className: "avatar" + (role === "human" ? " human" : live ? "" : " dim"),
        }, initials(role)),
        h("div", { className: "cast-name" }, roleLabel(role)),
        live ? h("div", { className: "typing" },
          h("i"), h("i"), h("i")) : null);
    }));
}

function AgentTheater({ workflow, events }) {
  const [detailEvents, setDetailEvents] = React.useState([]);
  React.useEffect(() => {
    if (!workflow) { setDetailEvents([]); return; }
    let alive = true;
    fetch(`/workflows/${workflow.id}`)
      .then((r) => r.json())
      .then((d) => { if (alive) setDetailEvents(d.events || []); })
      .catch(() => { if (alive) setDetailEvents([]); });
    return () => { alive = false; };
  }, [workflow && workflow.id, workflow && workflow.updated_at, workflow && workflow.event_count]);

  const runs = (workflow && workflow.agent_runs) || [];
  const speaking = new Set(
    runs.filter((r) => r.status === "running").map((r) => r.agent_role));
  const sourceEvents = detailEvents.length ? detailEvents : (events || []);
  const turns = buildTurns(workflow, sourceEvents);
  const leftRoles = ["intake-agent", "repository-agent", "product-manager-agent"];
  const rightRoles = ["planning-agent", "backend-agent", "release-agent", "human"];

  return h(Panel, {
    title: "Agent theater",
    count: turns.filter((t) => t.kind === "turn").length || null,
    className: "grow theater",
  },
    !workflow ? h(Empty, { text: "Select a workflow to open the theater" })
      : h(React.Fragment, null,
          workflow.state === "BLOCKED" && workflow.blocked_reason
            ? h("div", { className: "banner" },
                h("div", { className: "h" }, "Blocked - honest failure recorded"),
                workflow.blocked_reason)
            : null,
          pendingGateFor(workflow)
            ? h("div", { className: "banner warn" },
                h("div", { className: "h" }, "Human decision required"),
                "Review artifacts, then approve or reject the " +
                pendingGateFor(workflow) + " gate. Agents cannot bypass this gate.")
            : null,
          h("div", { className: "theater-stage" },
            h(CastColumn, { roles: leftRoles, speaking, side: "left" }),
            h("div", { className: "transcript", role: "log" },
              turns.length === 0
                ? h(Empty, { text: "No agent activity yet. Launch a run to open the theater." })
                : turns.map((t) => t.kind === "handoff"
                  ? h("div", { key: t.key, className: "handoff" },
                      roleLabel(t.from) + " -> " + roleLabel(t.to))
                  : h("div", {
                      key: t.key,
                      className: "turn" + (t.human ? " human" : ""),
                    },
                      h("div", { className: "turn-time" }, clockTime(t.time)),
                      h("div", null,
                        h("div", { className: "turn-who" }, roleLabel(t.role)),
                        h("div", { className: "turn-text" }, t.text),
                        h("div", { className: "turn-type" }, t.type))))),
            h(CastColumn, { roles: rightRoles, speaking, side: "right" }))));
}

/* ------------------------------------------------------------- guardrails */

function Meter({ name, used, limit, format }) {
  const p = pct(used, limit);
  const fmt = format || num;
  return h("div", { className: "metric" },
    h("div", { className: "metric-label" },
      h("span", null, name),
      h("span", null, h("b", null, fmt(used)), " / ", fmt(limit))),
    h("div", { className: "bar" },
      h("i", { className: level(p), style: { width: p.toFixed(1) + "%" } })));
}

function SuggestionRail({ product, feature, workflow }) {
  const [data, setData] = React.useState(null);
  const [err, setErr] = React.useState("");
  const name = product ? product.name : null;
  React.useEffect(() => {
    if (!name) { setData(null); return; }
    let alive = true;
    const params = new URLSearchParams();
    if (feature && feature.id) params.set("feature_id", feature.id);
    if (workflow && workflow.id) params.set("workflow_id", workflow.id);
    const q = params.toString() ? ("?" + params.toString()) : "";
    fetch("/api/products/" + encodeURIComponent(name) + "/suggestions" + q)
      .then((r) => r.json())
      .then((d) => { if (alive) { setData(d); setErr(""); } })
      .catch((e) => { if (alive) setErr(String(e)); });
    return () => { alive = false; };
  }, [name, feature && feature.id, workflow && workflow.id, workflow && workflow.state]);

  if (!product) {
    return h(Panel, { title: "Suggestions", className: "grow" },
      h(Empty, { text: "Select a product" }));
  }
  return h(Panel, {
    title: "Suggestions",
    count: "Autonomy A",
    className: "grow",
  },
    err ? h(Empty, { text: err })
    : !data ? h(Empty, { text: "Loading…" })
    : h("div", { className: "suggest-rail" },
        h("div", { className: "muted", style: { fontSize: 11, marginBottom: 8 } },
          data.disclaimer || "Suggest only — humans approve gates."),
        h("div", { className: "stat", style: { marginBottom: 8 } },
          h("div", { className: "k" }, "Next agent"),
          h("div", { className: "v" }, data.next_agent || "human")),
        h("div", { className: "metric-label", style: { marginBottom: 4 } },
          h("span", null, "Suggested order"),
          h("span", null, "never auto-approve")),
        (data.components || []).map((c) => h("div", {
          key: c.id, className: "unit", style: { cursor: "default" },
        },
          h("div", { className: "unit-title" },
            h("span", null, c.id),
            h("span", { className: "muted", style: { marginLeft: "auto" } },
              c.kind)),
          h("div", { className: "unit-sub" },
            h("span", null, c.suggested_role || "-"),
            h("span", null, c.path ? "path ok" : "missing path"))))));
}

function GuardrailsRail({ workflow, totals, pending, busy, onDecide }) {
  if (!workflow) {
    return h(Panel, { title: "Guardrails", className: "grow" },
      h(Empty, { text: "Select a workflow" }));
  }
  const b = workflow.budget;
  const s = workflow.spent;
  const gate = pendingGateFor(workflow);
  const wfPending = (pending || []).filter((a) => a.workflow_id === workflow.id);

  return h(Panel, { title: "Guardrails", count: workflow.id.slice(-6), className: "grow" },
    h(Meter, { name: "Cost USD", used: s.cost_usd, limit: b.maximum_cost_usd, format: money }),
    h(Meter, { name: "Iterations", used: s.iterations, limit: b.maximum_iterations }),
    h(Meter, { name: "Tool calls", used: s.tool_calls, limit: b.maximum_tool_calls }),
    h(Meter, { name: "Tokens in", used: s.input_tokens, limit: b.maximum_input_tokens }),
    h(Meter, { name: "Tokens out", used: s.output_tokens, limit: b.maximum_output_tokens }),
    h("div", { className: "stat-grid" },
      h("div", { className: "stat" },
        h("div", { className: "k" }, "Workflow cost"),
        h("div", { className: "v" }, money(s.cost_usd))),
      h("div", { className: "stat" },
        h("div", { className: "k" }, "Portfolio"),
        h("div", { className: "v warn" }, money(totals.cost_usd)))),
    h("div", { style: { marginTop: 12 } },
      h("div", { className: "metric-label", style: { marginBottom: 6 } },
        h("span", null, "Pending approvals"),
        h("span", null, String(wfPending.length || (gate ? 1 : 0)))),
      gate
        ? h("div", { className: "approval-row" },
            h("div", { className: "g" }, gate),
            h("div", { className: "muted", style: { fontSize: 11 } },
              "State " + workflow.state),
            h("div", { className: "approval-actions" },
              h("button", {
                className: "btn warn", disabled: busy,
                onClick: () => onDecide(workflow, true, gate),
              }, "Approve"),
              h("button", {
                className: "btn danger", disabled: busy,
                onClick: () => onDecide(workflow, false, gate),
              }, "Reject")))
        : h(Empty, { text: "No open gates" })));
}

/* --------------------------------------------------------------- docs */

const DOC_TABS = [
  ["charter", "Charter"],
  ["plan", "Plan"],
  ["brain", "Brain"],
  ["repo-map", "Repo map"],
];

function renderMarkdown(text) {
  const out = [];
  text.split("\n").forEach((raw, i) => {
    const line = raw.replace(/\s+$/, "");
    if (/^#{1,6}\s/.test(line)) {
      out.push(h("h3", { key: i }, line.replace(/^#{1,6}\s*/, "")));
      return;
    }
    if (/^(-{3,}|={3,})$/.test(line)) {
      out.push(h("div", { className: "hr", key: i }));
      return;
    }
    const parts = line.split("**");
    const nodes = parts.map((part, k) =>
      k % 2 === 1 ? h("b", { key: k }, part) : part);
    out.push(h("div", { key: i, className: "li" }, nodes.length ? nodes : "\u00a0"));
  });
  return out;
}

function DocsPanel({ feature, busy, onNotify }) {
  const [tab, setTab] = React.useState("charter");
  const [doc, setDoc] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const [hits, setHits] = React.useState(null);
  const [view, setView] = React.useState("doc");
  const featureId = feature ? feature.id : null;

  React.useEffect(() => {
    if (!featureId) { setDoc(null); return; }
    let alive = true;
    setLoading(true);
    fetch(`/api/features/${featureId}/document/${tab}`)
      .then((r) => r.json())
      .then((d) => { if (alive) { setDoc(d); setLoading(false); } })
      .catch(() => { if (alive) { setDoc(null); setLoading(false); } });
    return () => { alive = false; };
  }, [featureId, tab]);

  async function onSearch(e) {
    e.preventDefault();
    if (!query.trim()) return;
    setView("search");
    try {
      const params = new URLSearchParams({
        q: query.trim(), mode: "hybrid", limit: "8",
      });
      if (feature) {
        if (feature.project_name) params.set("project", feature.project_name);
        if (feature.name) params.set("feature", feature.name);
      }
      const res = await fetch("/api/docs/search?" + params.toString());
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "search failed");
      setHits(data.hits || []);
    } catch (err) {
      setHits([]);
      onNotify("Search failed", err.message, "bad");
    }
  }

  async function onIndex() {
    if (!featureId) return;
    if (!window.confirm("Rebuild PageIndex trees and vector embeddings for this feature?")) {
      return;
    }
    try {
      const res = await fetch(`/api/features/${featureId}/docs-index`, {
        method: "POST",
        headers: apiHeaders(),
      });
      const data = await res.json();
      if (res.status === 401) {
        throw new Error("unauthorized: set localStorage agentic_org_api_token");
      }
      if (!res.ok) throw new Error(data.detail || "index failed");
      onNotify("Docs indexed",
        `${data.files_indexed} files | ${data.vector_chunks} chunks`, "ok");
    } catch (err) {
      onNotify("Index failed", err.message, "bad");
    }
  }

  return h(Panel, {
    title: "Documents",
    className: "grow",
    head: h("div", { className: "actions", style: { marginLeft: "auto" } },
      h("button", {
        className: "btn", disabled: !featureId || busy,
        onClick: onIndex,
      }, "Re-index")),
  },
    h("form", { className: "search-row", onSubmit: onSearch },
      h("input", {
        value: query,
        onChange: (e) => setQuery(e.target.value),
        placeholder: "Hybrid search across feature docs...",
        disabled: !featureId,
      }),
      h("button", { className: "btn primary", type: "submit", disabled: !featureId },
        "Search")),
    h("div", { className: "tabs" },
      DOC_TABS.map(([key, label]) => h("button", {
        key, type: "button",
        className: "tab" + (view === "doc" && tab === key ? " on" : ""),
        onClick: () => { setView("doc"); setTab(key); },
      }, label)),
      h("button", {
        type: "button",
        className: "tab" + (view === "search" ? " on" : ""),
        onClick: () => setView("search"),
      }, "Results")),
    view === "search"
      ? (!hits ? h(Empty, { text: "Run a search to see hybrid hits" })
        : hits.length === 0 ? h(Empty, { text: "No matching sections" })
        : hits.map((hit, i) => h("div", { key: i, className: "hit" },
            h("div", { className: "t" }, hit.title || hit.node_id),
            h("div", { className: "m" },
              (hit.method || "search") + " | score " +
              (hit.score != null ? Number(hit.score).toFixed(2) : "-") +
              (hit.doc_path ? " | " + hit.doc_path : "")),
            h("div", { className: "s" },
              hit.summary || (hit.text || "").slice(0, 220)))))
      : (!featureId ? h(Empty, { text: "Select a feature" })
        : loading ? h(Empty, { text: "Loading artifact..." })
        : !doc || !doc.exists
          ? h(Empty, { text: "Artifact not produced yet" })
          : h("div", { className: "doc" }, renderMarkdown(doc.content))));
}

/* ------------------------------------------------------------- events */

const FILTERS = {
  ALL: () => true,
  FLOW: (e) => e.event_type.startsWith("workflow."),
  AGENTS: (e) => [
    "intake.classified", "repository.mapped", "brain.updated",
    "charter.drafted", "plan.created", "implementation.succeeded",
    "merge.succeeded", "release.succeeded",
  ].includes(e.event_type),
  GATES: (e) => e.event_type.startsWith("approval.") ||
                e.event_type === "release.approval.requested" ||
                e.event_type === "command.issued",
  RISK: (e) => ["workflow.blocked", "budget.exceeded",
                "checkpoint.restored"].includes(e.event_type),
  DOCS: (e) => e.event_type === "docs.indexed",
};

function EventLog({ events, onPick }) {
  const [filter, setFilter] = React.useState("ALL");
  const [open, setOpen] = React.useState(null);
  const rows = events.filter(FILTERS[filter]);

  return h(Panel, {
    title: "Live events",
    count: rows.length,
    className: "grow",
    bodyClass: "tight",
  },
    h("div", { className: "filter-row" },
      Object.keys(FILTERS).map((key) => h("button", {
        key, className: "filter" + (filter === key ? " on" : ""),
        onClick: () => setFilter(key),
      }, key))),
    rows.length === 0
      ? h(Empty, { text: "No events match filter" })
      : rows.map((ev) => h("div", {
          key: ev.event_id,
          className: "event",
          onClick: () => {
            setOpen(open === ev.event_id ? null : ev.event_id);
            if (ev.workflow_id) onPick(ev.workflow_id);
          },
        },
          h("div", { className: "event-time" }, clockTime(ev.timestamp)),
          h("div", { className: "event-mark " + tone(ev.event_type) }),
          h("div", null,
            h("div", { className: "event-type" }, ev.event_type),
            h("div", { className: "event-reason" }, eventSummary(ev)),
            open === ev.event_id
              ? h("pre", { className: "event-payload" },
                  JSON.stringify({
                    event_id: ev.event_id,
                    agent_role: ev.agent_role,
                    workflow_id: ev.workflow_id,
                    tokens: [ev.tokens_in, ev.tokens_out],
                    cost_usd: ev.cost_usd,
                    payload: ev.payload,
                  }, null, 2))
              : null))));
}

/* ------------------------------------------------------------- actions */

function apiHeaders(extra) {
  const headers = Object.assign({ "Content-Type": "application/json" }, extra || {});
  const token = window.localStorage.getItem("agentic_org_api_token") || "";
  if (token) headers["X-Agentic-Org-Token"] = token;
  return headers;
}

function ActionBar({ workflow, feature, busy, onRun, onResume, onRevert, canRun }) {
  const canResume = workflow && !workflow.is_running &&
    workflow.state !== "COMPLETED" && workflow.state !== "BLOCKED" &&
    (workflow.approval_granted || workflow.release_approval_granted ||
     ["PLANNED", "VALIDATING", "REVIEWING", "READY_FOR_RELEASE"].includes(workflow.state));
  const checkpoint = workflow && workflow.checkpoints && workflow.checkpoints[0];
  const launchOk = canRun !== false;

  return h("div", { className: "actions" },
    h("button", {
      className: "btn primary", disabled: !feature || busy || !launchOk,
      title: launchOk ? "Launch Mode A run" : "Product has no component path",
      onClick: () => onRun(feature),
    }, "Launch run"),
    h("button", {
      className: "btn", disabled: !canResume || busy,
      onClick: () => onResume(workflow),
    }, "Resume"),
    h("button", {
      className: "btn danger", disabled: !checkpoint || busy,
      onClick: () => onRevert(workflow, checkpoint),
    }, "Revert checkpoint"));
}

/* ------------------------------------------------------------------- app */

function App() {
  const [snap, setSnap] = React.useState(null);
  const [link, setLink] = React.useState("connecting");
  const [selectedProduct, setSelectedProduct] = React.useState(
    () => window.localStorage.getItem("agentic_org_product") || null);
  const [selectedWorkflow, setSelectedWorkflow] = React.useState(null);
  const [selectedFeature, setSelectedFeature] = React.useState(null);
  const [toasts, setToasts] = React.useState([]);
  const [busy, setBusy] = React.useState(false);
  const [now, setNow] = React.useState(new Date());

  React.useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const notify = React.useCallback((title, body, kind) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((prev) => [...prev, { id, title, body, kind }]);
    setTimeout(() => setToasts((prev) => prev.filter((x) => x.id !== id)), 6000);
  }, []);

  const refresh = React.useCallback(async () => {
    try {
      const res = await fetch("/api/state");
      setSnap(await res.json());
    } catch (err) { /* stream recovers */ }
  }, []);

  React.useEffect(() => {
    let source;
    let poller;
    try {
      source = new EventSource("/api/stream");
      source.onopen = () => setLink("live");
      source.addEventListener("state", (msg) => {
        setLink("live");
        setSnap(JSON.parse(msg.data));
      });
      source.onerror = () => {
        setLink("polling");
        if (!poller) poller = setInterval(refresh, 3000);
      };
    } catch (err) {
      setLink("polling");
      poller = setInterval(refresh, 3000);
    }
    refresh();
    return () => { if (source) source.close(); if (poller) clearInterval(poller); };
  }, [refresh]);

  const products = (snap && (snap.products || snap.projects)) || [];
  const allWorkflows = (snap && snap.workflows) || [];
  const allFeatures = (snap && snap.features) || [];

  const product = React.useMemo(() => {
    if (!products.length) return null;
    const byName = products.find((p) => p.name === selectedProduct);
    return byName || products[0];
  }, [products, selectedProduct]);

  React.useEffect(() => {
    if (product && product.name !== selectedProduct) {
      setSelectedProduct(product.name);
      window.localStorage.setItem("agentic_org_product", product.name);
    }
  }, [product, selectedProduct]);

  const features = React.useMemo(() => {
    if (!product) return [];
    return allFeatures.filter((f) => f.project_name === product.name);
  }, [allFeatures, product]);

  const workflows = React.useMemo(() => {
    if (!product) return [];
    return allWorkflows.filter((w) => w.project_name === product.name);
  }, [allWorkflows, product]);

  const workflow = React.useMemo(() => {
    if (!workflows.length) return null;
    const found = workflows.find((w) => w.id === selectedWorkflow);
    return found || workflows[0];
  }, [workflows, selectedWorkflow]);

  const feature = React.useMemo(() => {
    if (!features.length) return null;
    if (selectedFeature) {
      const found = features.find((f) => f.id === selectedFeature);
      if (found) return found;
    }
    if (workflow) {
      const found = features.find((f) => f.id === workflow.feature_id);
      if (found) return found;
    }
    return features[0];
  }, [features, selectedFeature, workflow]);

  function selectProduct(name) {
    setSelectedProduct(name);
    window.localStorage.setItem("agentic_org_product", name);
    setSelectedFeature(null);
    setSelectedWorkflow(null);
  }

  async function post(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: apiHeaders(),
      body: JSON.stringify(body || {}),
    });
    const data = await res.json().catch(() => ({}));
    if (res.status === 401) {
      throw new Error(
        "unauthorized: store AGENTIC_ORG_API_TOKEN in localStorage key agentic_org_api_token"
      );
    }
    if (!res.ok) throw new Error(data.detail || `request failed (${res.status})`);
    return data;
  }

  async function onRun(target) {
    if (!target) return;
    const confirmed = window.confirm(
      `Launch an autonomous run for ${target.project_name}/${target.name}?\n\n` +
      "This starts real agent work against a budget cap.");
    if (!confirmed) return;
    setBusy(true);
    try {
      const data = await post(`/api/features/${target.id}/run`,
        { budget_usd: 8, max_iterations: 12, started_by: "command-center" });
      setSelectedWorkflow(data.workflow_id);
      notify("Run launched", `${target.project_name}/${target.name}`, "ok");
    } catch (err) {
      notify("Launch failed", err.message, "bad");
    } finally { setBusy(false); refresh(); }
  }

  async function onDecide(target, approve, gate) {
    if (!target) return;
    const g = gate || pendingGateFor(target) || "plan-approval";
    if (approve) {
      const confirmed = window.confirm(
        `Approve the ${g} gate for ${target.id}?\n\n` +
        "The workflow may resume and consume model budget.");
      if (!confirmed) return;
    }
    setBusy(true);
    try {
      await post(`/workflows/${target.id}/approval`, {
        approve, gate: g, decided_by: "command-center",
        reason: approve ? "Approved from command center"
                        : "Rejected from command center",
      });
      notify(approve ? "Gate approved" : "Gate rejected", g, approve ? "ok" : "warn");
      if (approve) {
        const job = await post(`/api/workflows/${target.id}/resume`, {});
        notify("Resuming workflow", job.job.label, "ok");
      }
    } catch (err) {
      notify("Decision failed", err.message, "bad");
    } finally { setBusy(false); refresh(); }
  }

  async function onResume(target) {
    if (!target) return;
    setBusy(true);
    try {
      const data = await post(`/api/workflows/${target.id}/resume`, {});
      notify("Resume issued", data.job.label, "ok");
    } catch (err) {
      notify("Resume failed", err.message, "bad");
    } finally { setBusy(false); refresh(); }
  }

  async function onRevert(target, checkpoint) {
    if (!target || !checkpoint) return;
    const ok = window.confirm(
      `Restore repository to checkpoint ${checkpoint.id}?\n\n` +
      "Working tree resets to that commit; history is preserved as tags.");
    if (!ok) return;
    setBusy(true);
    try {
      const data = await post(`/api/workflows/${target.id}/revert`,
        { checkpoint_id: checkpoint.id, decided_by: "command-center" });
      notify("Checkpoint restored", data.restored_to.slice(0, 10), "warn");
    } catch (err) {
      notify("Revert failed", err.message, "bad");
    } finally { setBusy(false); refresh(); }
  }

  if (!snap) {
    return h("div", { className: "shell", style: { display: "block", padding: 24 } },
      h(Panel, { title: "Connecting" },
        h(Empty, { text: "Connecting to orchestrator..." })));
  }

  const sys = snap.system;
  const pending = snap.pending_approvals || [];
  const runningJobs = (snap.jobs || []).filter((j) => j.status === "running");
  const theaterEvents = workflow
    ? (snap.events || []).filter((e) => e.workflow_id === workflow.id)
    : (snap.events || []);

  /* Prefer workflow-detail depth: snapshot events are global (60). Theater
     uses those filtered by workflow; agent_runs come from workflow object. */

  const productRunnable = product && (product.runnable || product.primary_path || product.repo_path);
  const productEvents = (snap.events || []).filter((e) => {
    if (!product) return true;
    if (e.project_id && product.id && e.project_id === product.id) return true;
    const wf = allWorkflows.find((w) => w.id === e.workflow_id);
    return wf && wf.project_name === product.name;
  });

  return h(React.Fragment, null,
    h("header", { className: "topbar" },
      h("div", { className: "brand" },
        h("div", { className: "brand-mark", "aria-hidden": "true" }),
        h("div", null,
          h("h1", null, "Agentic Org"),
          h("div", { className: "tagline" }, "Command Center | product-scoped | reversible"))),
      h("label", { className: "product-switch", style: { display: "flex", flexDirection: "column", gap: 2 } },
        h("span", { className: "faint", style: { fontSize: 10, fontWeight: 600, letterSpacing: "0.06em" } }, "PRODUCT"),
        h("select", {
          value: product ? product.name : "",
          onChange: (e) => selectProduct(e.target.value),
          style: {
            minWidth: 180, padding: "6px 10px", borderRadius: 6,
            border: "1px solid var(--border)", font: "inherit", fontWeight: 600,
            background: "#fff", color: "var(--text)",
          },
        },
          products.length === 0
            ? h("option", { value: "" }, "No products")
            : products.map((p) => h("option", { key: p.name, value: p.name },
                p.name + " (" + (p.shape || "mono") + ")")))),
      h("div", { className: "topbar-spacer" }),
      h(ActionBar, {
        workflow, feature, busy, onRun, onResume, onRevert,
        canRun: !!productRunnable,
      }),
      h(Chip, {
        kind: link === "live" ? "ok" : "warn", live: link === "live",
        label: link === "live" ? "Link live" : "Link " + link,
      }),
      h(Chip, {
        kind: sys.event_chain_valid ? "ok" : "bad",
        label: sys.event_chain_valid ? "Audit chain ok" : "Audit chain broken",
      }),
      h(Chip, {
        kind: sys.model_gateway_available ? "info" : "warn",
        label: (sys.model_provider || "model") +
          (sys.model_gateway_available ? " online" : " offline"),
      }),
      runningJobs.length
        ? h(Chip, { kind: "warn", live: true,
                    label: runningJobs.length + " job active" })
        : null,
      h("div", { className: "clock" }, now.toTimeString().slice(0, 8))),

    h(PipelineStrip, { workflow }),

    h("div", { className: "shell" },
      h("div", { className: "col scroll left-col" },
        h(Panel, {
          title: "Product home",
          count: product ? (product.shape || "mono") : null,
        },
          !product ? h(Empty, { text: "Create a product (agentctl product-init)" })
            : h(React.Fragment, null,
                h("div", { className: "metric-label" },
                  h("span", null, product.name),
                  h("span", null, productRunnable ? "runnable" : "no path")),
                h("div", { className: "muted", style: { fontSize: 11, marginBottom: 8 } },
                  "Components (suggest-only autonomy)"),
                !(product.components || []).length
                  ? h(Empty, { text: "No components — configure product.yaml" })
                  : (product.components || []).map((c) => h("div", {
                      key: c.id, className: "checkpoint",
                    },
                      h("span", { className: "cid" }, c.id),
                      h("span", { className: "muted" }, c.kind),
                      h("span", {
                        className: "muted",
                        style: { marginLeft: "auto", maxWidth: 100, overflow: "hidden",
                                 textOverflow: "ellipsis", whiteSpace: "nowrap" },
                        title: c.path || "",
                      }, c.path ? "linked" : "missing"))))),
        h(Panel, { title: "Features", count: features.length, className: "grow" },
          !product ? h(Empty, { text: "Select a product" })
          : features.length === 0
            ? h(Empty, { text: "No features in this product" })
            : features.map((f) => h("button", {
                key: f.id,
                className: "unit" + (feature && f.id === feature.id ? " selected" : ""),
                onClick: () => {
                  setSelectedFeature(f.id);
                  if (f.latest_workflow) setSelectedWorkflow(f.latest_workflow);
                },
              },
                h("div", { className: "unit-title" },
                  h("span", null, f.name),
                  h("span", { className: stateClass(f.latest_state),
                              style: { marginLeft: "auto" } }, f.latest_state)),
                h("div", { className: "unit-sub" },
                  h("span", null, f.workflow_count + " runs"))))),
        h(Panel, { title: "Workflows", count: workflows.length, className: "grow" },
          workflows.length === 0
            ? h(Empty, { text: "No workflows in this product" })
            : workflows.map((w) => h("button", {
                key: w.id,
                className: "unit" + (workflow && w.id === workflow.id ? " selected" : ""),
                onClick: () => {
                  setSelectedWorkflow(w.id);
                  setSelectedFeature(w.feature_id);
                },
              },
                h("div", { className: "unit-title" },
                  h("span", { className: "mono", style: { fontSize: 11 } },
                    w.id.slice(-10)),
                  w.is_running ? h("span", { className: "dot live",
                    style: { width: 7, height: 7, borderRadius: "50%",
                             background: "var(--warn)", display: "inline-block" } }) : null,
                  h("span", { className: stateClass(w.state),
                              style: { marginLeft: "auto" } }, w.state)),
                h("div", { className: "unit-sub" },
                  h("span", null, w.feature_name || "-"),
                  h("span", null, money(w.spent.cost_usd)),
                  h("span", null, clockTime(w.updated_at))))))),

      h("div", { className: "col theater-col" },
        h(AgentTheater, {
          workflow,
          events: theaterEvents.length
            ? theaterEvents
            : (snap.events || []).filter((e) => !workflow || e.workflow_id === workflow.id),
        })),

      h("div", { className: "col scroll right-col" },
        h(SuggestionRail, { product, feature, workflow }),
        h(GuardrailsRail, {
          workflow, totals: snap.totals || {}, pending, busy, onDecide,
        }),
        h(Panel, {
          title: "Checkpoints",
          count: workflow ? (workflow.checkpoints || []).length : 0,
        },
          !workflow || !(workflow.checkpoints || []).length
            ? h(Empty, { text: "No checkpoints" })
            : workflow.checkpoints.map((cp) => h("div", {
                key: cp.id, className: "checkpoint",
              },
                h("span", { className: "cid" }, cp.id.slice(-8)),
                h("span", { className: "muted" }, cp.kind),
                h("span", { className: "muted", style: { marginLeft: "auto" } },
                  clockTime(cp.created_at)))))),

      h("div", { className: "bottom-row" },
        h(DocsPanel, { feature, busy, onNotify: notify }),
        h(EventLog, {
          events: productEvents.length ? productEvents : (snap.events || []),
          onPick: (id) => setSelectedWorkflow(id),
        }))),

    h("div", { className: "toasts" },
      toasts.map((t) => h("div", { key: t.id, className: "toast " + (t.kind || "") },
        h("div", { className: "t" }, t.title),
        h("div", null, t.body)))));
}

ReactDOM.createRoot(document.getElementById("root")).render(h(App));
