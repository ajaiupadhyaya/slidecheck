/* ============================================================
   SlideCheck — interactive remediation studio (vanilla JS, no build)

   SECURITY: every server-derived string reaches the DOM through
   `textContent` (or `esc()` when a string must be composed). The only
   `innerHTML` used is for fully-static, author-written markup (icons)
   with no interpolation of server data. Thumbnails set `img.src` from
   the analyze service's data: URI, which is safe.
   ============================================================ */

const PW_KEY = "slidecheck-password";
const $ = (id) => document.getElementById(id);

/* ---- scoring (mirrors the spec's client formula) ---- */
const WEIGHT = { error: 8, warning: 3, info: 1 };
function computeScore(findings, acceptedIds) {
  let penalty = 0;
  for (const f of findings) {
    if (acceptedIds.has(f.id)) continue;
    penalty += WEIGHT[f.severity] || 0;
  }
  return Math.max(0, 100 - penalty);
}
function gradeFor(s) {
  return s >= 95 ? "A" : s >= 85 ? "B" : s >= 70 ? "C" : s >= 55 ? "D" : "F";
}

/* ---- action taxonomy ---- */
const TEXT_ACTIONS = new Set([
  "set_alt_text", "set_title", "set_link_text", "set_doc_title", "set_doc_language",
]);
const AI_ACTIONS = new Set([
  "set_alt_text", "set_title", "set_link_text", "set_doc_title",
]);

/* ---- category presentation (static, author-authored) ---- */
const CATEGORY = {
  images:    { label: "Image",    icon: '<path d="M4 5h16v14H4z" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="9" cy="10" r="1.6" fill="currentColor"/><path d="M5 18l4.5-5 3 3L16 12l3 6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>' },
  text:      { label: "Text",     icon: '<path d="M5 5h14M5 5v2M19 5v2M12 5v14M9 19h6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>' },
  color:     { label: "Color",    icon: '<circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M12 4a8 8 0 0 0 0 16z" fill="currentColor"/>' },
  links:     { label: "Link",     icon: '<path d="M9 12a3 3 0 0 1 3-3h3a3 3 0 0 1 0 6h-1M15 12a3 3 0 0 1-3 3H9a3 3 0 0 1 0-6h1" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>' },
  document:  { label: "Document", icon: '<path d="M7 3h7l4 4v14H7z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M14 3v4h4" fill="none" stroke="currentColor" stroke-width="1.6"/>' },
  structure: { label: "Structure",icon: '<path d="M4 6h16M4 12h16M4 18h10" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>' },
  media:     { label: "Media",    icon: '<rect x="4" y="6" width="16" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M10 9.5l4 2.5-4 2.5z" fill="currentColor"/>' },
  motion:    { label: "Motion",   icon: '<path d="M5 12h6m0 0l-2-2m2 2l-2 2M13 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>' },
};
function categoryMeta(c) { return CATEGORY[c] || { label: c || "Issue", icon: '<circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="1.6"/>' }; }

const CHECK_ICON = '<svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4 4 10-10" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

/* ============================================================
   Gate
   ============================================================ */
function showApp() { $("gate").hidden = true; $("app").hidden = false; }
function showGate(msg) {
  $("app").hidden = true;
  $("gate").hidden = false;
  $("gate-error").textContent = msg || "";
}

/* ============================================================
   Init / wiring
   ============================================================ */
function init() {
  if (sessionStorage.getItem(PW_KEY)) showApp(); else showGate("");

  $("gate-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const pw = $("password").value.trim();
    if (!pw) { $("gate-error").textContent = "Enter the password to continue."; $("password").focus(); return; }

    // Validate the password against the server BEFORE entering the app, so a
    // wrong password is caught here instead of silently bouncing the user back
    // to the gate on their first upload.
    const submitBtn = $("unlock");
    if (submitBtn) submitBtn.disabled = true;
    $("gate-error").textContent = "Checking…";

    let resp;
    try {
      resp = await fetch("/api/auth", {
        method: "POST",
        headers: { "x-slidecheck-password": pw },
      });
    } catch {
      $("gate-error").textContent = "Couldn't reach the server. Check your connection and try again.";
      if (submitBtn) submitBtn.disabled = false;
      return;
    }

    if (submitBtn) submitBtn.disabled = false;

    if (resp.status === 401) {
      $("gate-error").textContent = "That password didn't work. Try again.";
      $("password").select();
      return;
    }
    if (!resp.ok) {
      $("gate-error").textContent = resp.status === 503
        ? "The server isn't configured yet. Please contact whoever set this up."
        : `Something went wrong (error ${resp.status}). Try again.`;
      return;
    }

    sessionStorage.setItem(PW_KEY, pw);
    $("gate-error").textContent = "";
    showApp();
    $("dropzone").focus();
  });

  const dz = $("dropzone");
  const input = $("file-input");
  dz.addEventListener("click", () => input.click());
  dz.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") { e.preventDefault(); input.click(); }
  });
  input.addEventListener("change", () => { if (input.files.length) analyzeFiles(input.files); input.value = ""; });
  ["dragenter", "dragover"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("drag"); }));
  dz.addEventListener("drop", (e) => { if (e.dataTransfer.files.length) analyzeFiles(e.dataTransfer.files); });
}

/* ---- status helpers ---- */
function setStatus(text, busy) {
  const el = $("status");
  el.hidden = false;
  el.classList.toggle("error-state", busy === "error");
  $("status-text").textContent = text;
  el.querySelector(".spinner").style.display = busy === true ? "" : "none";
}
function clearStatus() { $("status").hidden = true; }

function handle401() {
  sessionStorage.removeItem(PW_KEY);
  showGate("That password didn't work. Try again.");
  clearStatus();
  $("password").focus();
}

/* ============================================================
   Analyze
   ============================================================ */
async function analyzeFiles(fileList) {
  const files = [...fileList].filter((f) => f.name.toLowerCase().endsWith(".pptx"));
  if (!files.length) { setStatus("Choose a PowerPoint (.pptx) file to check.", "error"); return; }

  $("results").replaceChildren();
  setStatus(files.length > 1
    ? `Analyzing ${files.length} files… generating suggestions…`
    : "Analyzing… generating suggestions…", true);

  const fd = new FormData();
  files.forEach((f) => fd.append("files", f, f.name));

  let resp;
  try {
    resp = await fetch("/api/analyze", {
      method: "POST",
      headers: { "x-slidecheck-password": sessionStorage.getItem(PW_KEY) || "" },
      body: fd,
    });
  } catch {
    setStatus("Couldn't reach the server. Check your connection and try again.", "error");
    return;
  }

  if (resp.status === 401) { handle401(); return; }
  if (!resp.ok) {
    let detail = `Something went wrong (error ${resp.status}).`;
    try { const j = await resp.json(); if (j.detail) detail = String(j.detail); } catch { /* ignore */ }
    setStatus(detail, "error");
    return;
  }

  let data;
  try { data = await resp.json(); } catch { setStatus("The server sent a response we couldn't read.", "error"); return; }
  clearStatus();

  const root = $("results");
  (data.files || []).forEach((file, i) => {
    root.appendChild(buildDossier(file, files[i] || null));
  });
}

/* ============================================================
   Dossier (per file)
   ============================================================ */
let _uid = 0;
const nextId = () => `sc-${++_uid}`;

function buildDossier(file, originalFile) {
  const section = el("section", "dossier");
  section.setAttribute("aria-labelledby", "");

  if (file.error || !file.analysis) {
    section.classList.add("dossier-error");
    const head = el("div", "dossier-head");
    const h = el("h2", "filename"); h.textContent = file.filename || "Unknown file";
    head.appendChild(h);
    section.appendChild(head);
    const p = el("p", "dossier-error-msg");
    p.textContent = "We couldn't open this file: " + (file.error || "unknown error");
    section.appendChild(p);
    return section;
  }

  const findings = file.analysis.findings || [];
  const coverage = file.analysis.coverage || [];

  const state = {
    file: originalFile,
    filename: file.filename,
    findings,
    status: new Map(),   // id -> "open" | "accepted" | "skipped"
    plan: new Map(),     // id -> plan item
    refs: {},            // live DOM refs (gauge, summary, export button…)
  };
  findings.forEach((f) => state.status.set(f.id, "open"));

  /* ---- head: filename + gauge ---- */
  const head = el("div", "dossier-head");
  const titleWrap = el("div");
  const h2 = el("h2", "filename");
  const hid = nextId();
  h2.id = hid;
  h2.textContent = file.filename;
  section.setAttribute("aria-labelledby", hid);
  titleWrap.appendChild(h2);
  head.appendChild(titleWrap);

  const band = el("div", "score-band");
  const gauge = buildGauge();
  const meta = el("div", "score-meta");
  const summary = el("p", "summary-line");
  summary.setAttribute("aria-live", "polite");
  meta.appendChild(summary);
  band.appendChild(gauge.el);
  band.appendChild(meta);
  head.appendChild(band);
  section.appendChild(head);

  state.refs.gauge = gauge;
  state.refs.summary = summary;

  /* ---- body ---- */
  const body = el("div", "dossier-body");
  if (coverage.length) body.appendChild(buildCoverage(coverage));
  body.appendChild(buildWorklist(state));
  section.appendChild(body);

  /* ---- export bar ---- */
  section.appendChild(buildExportBar(state));

  updateScore(state);
  return section;
}

/* ---- SVG gauge ---- */
function buildGauge() {
  const NS = "http://www.w3.org/2000/svg";
  const R = 46, C = 2 * Math.PI * R;
  const wrap = el("div", "gauge");
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 104 104");
  svg.setAttribute("aria-hidden", "true");
  const track = document.createElementNS(NS, "circle");
  const value = document.createElementNS(NS, "circle");
  for (const c of [track, value]) {
    c.setAttribute("cx", "52"); c.setAttribute("cy", "52"); c.setAttribute("r", String(R));
    c.setAttribute("fill", "none"); c.setAttribute("stroke-width", "8");
  }
  track.setAttribute("class", "track");
  value.setAttribute("class", "value");
  value.setAttribute("stroke-dasharray", String(C));
  value.setAttribute("stroke-dashoffset", String(C));
  svg.appendChild(track); svg.appendChild(value);
  wrap.appendChild(svg);

  const center = el("div", "gauge-center");
  const num = el("span", "gauge-num"); num.textContent = "—";
  const grd = el("span", "gauge-grade"); grd.textContent = "score";
  center.appendChild(num); center.appendChild(grd);
  wrap.appendChild(center);

  return {
    el: wrap,
    set(score, grade) {
      wrap.setAttribute("data-grade", grade);
      value.setAttribute("stroke-dashoffset", String(C * (1 - score / 100)));
      num.textContent = String(score);
      grd.textContent = "Grade " + grade;
    },
  };
}

/* ============================================================
   Coverage matrix
   ============================================================ */
function buildCoverage(rows) {
  const counts = rows.reduce((a, r) => { a[r.status] = (a[r.status] || 0) + 1; return a; }, {});
  const details = el("details", "coverage");
  const summary = el("summary");
  const label = document.createTextNode("Standards coverage ");
  summary.appendChild(label);
  const cnt = el("span", "count");
  cnt.textContent = `(${counts.PASS || 0} pass · ${counts.FAIL || 0} fail · ${counts.NEEDS_REVIEW || 0} review)`;
  summary.appendChild(cnt);
  details.appendChild(summary);

  const inner = el("div", "coverage-inner");
  const note = el("p", "coverage-note");
  note.textContent = "508 = WCAG 2.0 A/AA (the legal floor); 2.1 / 2.2 success criteria are best practice.";
  inner.appendChild(note);

  const table = el("table", "cov-table");
  const cap = el("caption"); cap.textContent = "WCAG success criteria checked in this deck";
  table.appendChild(cap);
  const thead = el("thead");
  const trh = el("tr");
  ["SC", "Criterion", "Level", "Status"].forEach((t, i) => {
    const th = el("th"); th.scope = "col"; th.textContent = t;
    if (i === 2 || i === 3) th.style.whiteSpace = "nowrap";
    trh.appendChild(th);
  });
  thead.appendChild(trh); table.appendChild(thead);

  const tbody = el("tbody");
  rows.forEach((r) => {
    const tr = el("tr");

    const scTd = el("td", "cov-sc"); scTd.textContent = r.sc; tr.appendChild(scTd);

    const titleTd = el("td"); titleTd.textContent = r.title; tr.appendChild(titleTd);

    const lvTd = el("td");
    const badges = el("span", "cov-badges");
    const lv = el("span", "lv-badge");
    lv.textContent = `${r.level} · ${r.version}`;
    badges.appendChild(lv);
    if (r.section508) {
      const chip = el("span", "chip-508"); chip.textContent = "508";
      chip.title = "Section 508 (legal floor)";
      badges.appendChild(chip);
    }
    lvTd.appendChild(badges);
    tr.appendChild(lvTd);

    const stTd = el("td"); stTd.appendChild(statusPill(r.status)); tr.appendChild(stTd);
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  inner.appendChild(table);
  details.appendChild(inner);
  return details;
}

function statusPill(status) {
  const map = {
    PASS:         { cls: "pill-pass",   text: "Pass" },
    FAIL:         { cls: "pill-fail",   text: "Fail" },
    NEEDS_REVIEW: { cls: "pill-review", text: "Needs review" },
    N_A:          { cls: "pill-na",     text: "N/A" },
  };
  const m = map[status] || { cls: "pill-na", text: status };
  const span = el("span", "pill " + m.cls);
  span.textContent = m.text;
  return span;
}

/* ============================================================
   Worklist
   ============================================================ */
function buildWorklist(state) {
  const wrap = el("div", "worklist");
  const h3 = el("h3", "worklist-head"); h3.textContent = "Issues to resolve";
  wrap.appendChild(h3);
  const sub = el("p", "worklist-sub");
  sub.textContent = "Accept each fix to apply it; the score rises as you go. Items marked for manual review need a human decision.";
  wrap.appendChild(sub);

  if (!state.findings.length) {
    const clear = el("div", "all-clear");
    clear.appendChild(staticSvg(CHECK_ICON));
    const t = document.createTextNode("No accessibility issues found in this deck.");
    clear.appendChild(t);
    wrap.appendChild(clear);
    return wrap;
  }

  // group by slide (document-level findings first)
  const groups = new Map();
  for (const f of state.findings) {
    const key = f.category === "document" ? "doc" : f.slide_index;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(f);
  }
  const order = [...groups.keys()].sort((a, b) => {
    if (a === "doc") return -1;
    if (b === "doc") return 1;
    return a - b;
  });

  for (const key of order) {
    const grp = el("div", "slide-group");
    const lbl = el("p", "slide-label");
    lbl.textContent = key === "doc" ? "Document" : `Slide ${Number(key) + 1}`;
    grp.appendChild(lbl);
    for (const f of groups.get(key)) grp.appendChild(buildCard(f, state));
    wrap.appendChild(grp);
  }
  return wrap;
}

function buildCard(f, state) {
  const card = el("article", "card");
  card.dataset.sev = f.severity;
  card.dataset.id = f.id;

  // top row: category + SC ref
  const top = el("div", "card-top");
  const cat = el("span", "cat");
  const meta = categoryMeta(f.category);
  cat.appendChild(staticSvg(`<svg width="15" height="15" viewBox="0 0 24 24" aria-hidden="true">${meta.icon}</svg>`));
  const catLabel = document.createElement("span"); catLabel.textContent = meta.label;
  cat.appendChild(catLabel);
  top.appendChild(cat);

  const sc = el("span", "sc-ref");
  sc.textContent = scLabel(f);
  top.appendChild(sc);
  card.appendChild(top);

  // message + suggestion
  const msg = el("p", "card-msg"); msg.textContent = f.message || "Accessibility issue";
  card.appendChild(msg);
  if (f.suggestion) { const s = el("p", "card-suggestion"); s.textContent = f.suggestion; card.appendChild(s); }

  // evidence: thumbnail or current value
  if (f.thumbnail) {
    const tw = el("div", "thumb-wrap");
    const img = document.createElement("img");
    img.className = "thumb";
    img.src = f.thumbnail;   // data: URI from analyze service — safe
    img.alt = "";            // decorative in our UI
    tw.appendChild(img);
    card.appendChild(tw);
  } else if (f.current_value) {
    const lab = el("span", "snippet-label"); lab.textContent = "Current value";
    card.appendChild(lab);
    const snip = el("code", "snippet"); snip.textContent = f.current_value;
    card.appendChild(snip);
  }

  // fix region
  if (f.fixable && f.fix_action) {
    if (TEXT_ACTIONS.has(f.fix_action)) buildTextFix(card, f, state);
    else buildSimpleFix(card, f, state);
  } else {
    buildManual(card, f, state);
  }

  applyCardState(card, f, state);
  return card;
}

/* ---- text fix (editable) ---- */
function buildTextFix(card, f, state) {
  const wrap = el("div", "fix");
  const taId = nextId();
  const aiGenerated = AI_ACTIONS.has(f.fix_action) && !!f.suggested_value;

  const label = el("label", "fix-label");
  label.htmlFor = taId;
  if (aiGenerated) {
    const flag = el("span", "ai-flag"); flag.textContent = "AI";
    label.appendChild(flag);
    label.appendChild(document.createTextNode("AI suggestion — review before accepting"));
  } else {
    label.textContent = "Your fix";
  }
  wrap.appendChild(label);

  const ta = document.createElement("textarea");
  ta.id = taId;
  ta.value = f.suggested_value || "";
  ta.placeholder = "Type a fix…";
  ta.addEventListener("input", () => {
    const item = state.plan.get(f.id);
    if (item && item.action !== "mark_decorative") item.value = ta.value;
  });
  wrap.appendChild(ta);
  card.appendChild(wrap);

  const actions = el("div", "card-actions");
  const accept = btn("btn btn-primary", "Accept fix", () => acceptText(card, f, state, ta));
  const skip = btn("btn btn-quiet", "Skip", () => setCardState(card, f, state, "skipped"));
  actions.appendChild(accept);
  actions.appendChild(skip);
  if (f.fix_action === "set_alt_text") {
    actions.appendChild(btn("btn btn-ghost", "Mark as decorative instead",
      () => acceptDecorative(card, f, state)));
  }
  card.appendChild(actions);
  card._actions = actions;
}

/* ---- simple fix (no textarea) ---- */
function buildSimpleFix(card, f, state) {
  const wrap = el("div", "fix");
  const prop = el("p", "fix-proposal");
  describeProposal(prop, f);
  wrap.appendChild(prop);
  card.appendChild(wrap);

  const actions = el("div", "card-actions");
  actions.appendChild(btn("btn btn-primary", "Accept fix", () => acceptSimple(card, f, state)));
  actions.appendChild(btn("btn btn-quiet", "Skip", () => setCardState(card, f, state, "skipped")));
  card.appendChild(actions);
  card._actions = actions;
}

function describeProposal(p, f) {
  const lead = document.createElement("span");
  if (f.fix_action === "apply_contrast_color") {
    lead.textContent = "Recolor the text to ";
    p.appendChild(lead);
    const color = f.suggested_value || "";
    if (/^#?[0-9a-fA-F]{6}$/.test(color)) {
      const sw = el("span", "swatch"); sw.style.background = color.startsWith("#") ? color : "#" + color;
      p.appendChild(sw);
    }
    const val = el("span", "val"); val.textContent = color || "a compliant color"; p.appendChild(val);
    p.appendChild(document.createTextNode(" for sufficient contrast."));
  } else if (f.fix_action === "bump_font_size") {
    lead.textContent = "Increase the text to "; p.appendChild(lead);
    const val = el("span", "val"); val.textContent = (f.suggested_value || "18") + " pt"; p.appendChild(val);
    p.appendChild(document.createTextNode("."));
  } else if (f.fix_action === "set_table_header") {
    p.textContent = "Add a header row so the table's columns are announced.";
  } else if (f.fix_action === "mark_decorative") {
    p.textContent = "Mark this image as decorative so screen readers skip it.";
  } else {
    p.textContent = "Apply the recommended fix.";
  }
}

/* ---- manual review (never auto-fixed) ---- */
function buildManual(card, f, state) {
  const actions = el("div", "card-actions");
  const tag = el("span", "manual-tag");
  tag.appendChild(staticSvg('<svg width="13" height="13" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l9 16H3z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M12 10v4M12 16.5v.5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>'));
  tag.appendChild(document.createTextNode("Manual review"));
  actions.appendChild(tag);
  card.appendChild(actions);
}

/* ============================================================
   Accept / skip / toggle
   ============================================================ */
function planValue(f, ta) {
  const a = f.fix_action;
  if (TEXT_ACTIONS.has(a)) return ta ? ta.value : (f.suggested_value || "");
  if (a === "apply_contrast_color") return f.suggested_value;
  if (a === "bump_font_size") return f.suggested_value || "18";
  if (a === "set_table_header") return true;
  return null;
}

function acceptText(card, f, state, ta) {
  state.plan.set(f.id, { target: f.target, action: f.fix_action, value: planValue(f, ta) });
  setCardState(card, f, state, "accepted");
}
function acceptSimple(card, f, state) {
  state.plan.set(f.id, { target: f.target, action: f.fix_action, value: planValue(f, null) });
  setCardState(card, f, state, "accepted");
}
function acceptDecorative(card, f, state) {
  state.plan.set(f.id, { target: f.target, action: "mark_decorative", value: null });
  setCardState(card, f, state, "accepted", { decorative: true });
}

function setCardState(card, f, state, next, opts) {
  state.status.set(f.id, next);
  if (next !== "accepted") state.plan.delete(f.id);
  applyCardState(card, f, state, opts);
  updateScore(state);
}

/* render a card to match its current status */
function applyCardState(card, f, state, opts) {
  const status = state.status.get(f.id);
  card.classList.toggle("is-accepted", status === "accepted");
  card.classList.toggle("is-skipped", status === "skipped");

  if (!card._actions) return; // manual review cards have no toggleable actions

  const actions = card._actions;
  actions.replaceChildren();

  if (status === "accepted") {
    const flag = el("span", "accepted-flag");
    flag.appendChild(staticSvg(CHECK_ICON));
    const decorative = opts && opts.decorative;
    flag.appendChild(document.createTextNode(decorative ? "Will be marked decorative" : "Will be fixed"));
    actions.appendChild(flag);
    actions.appendChild(btn("btn btn-quiet", "Undo", () => setCardState(card, f, state, "open")));
  } else if (status === "skipped") {
    const flag = el("span", "skipped-flag"); flag.textContent = "Skipped";
    actions.appendChild(flag);
    actions.appendChild(btn("btn btn-quiet", "Reopen", () => setCardState(card, f, state, "open")));
  } else {
    rebuildOpenActions(card, f, state, actions);
  }
}

/* rebuild the open-state action buttons (Accept / Skip / decorative) */
function rebuildOpenActions(card, f, state, actions) {
  if (TEXT_ACTIONS.has(f.fix_action)) {
    const ta = card.querySelector("textarea");
    actions.appendChild(btn("btn btn-primary", "Accept fix", () => acceptText(card, f, state, ta)));
    actions.appendChild(btn("btn btn-quiet", "Skip", () => setCardState(card, f, state, "skipped")));
    if (f.fix_action === "set_alt_text") {
      actions.appendChild(btn("btn btn-ghost", "Mark as decorative instead", () => acceptDecorative(card, f, state)));
    }
  } else {
    actions.appendChild(btn("btn btn-primary", "Accept fix", () => acceptSimple(card, f, state)));
    actions.appendChild(btn("btn btn-quiet", "Skip", () => setCardState(card, f, state, "skipped")));
  }
}

/* ============================================================
   Live score + summary
   ============================================================ */
function updateScore(state) {
  const acceptedIds = new Set();
  for (const [id, st] of state.status) if (st === "accepted") acceptedIds.add(id);

  const score = computeScore(state.findings, acceptedIds);
  const grade = gradeFor(score);
  state.refs.gauge.set(score, grade);

  const fixableTotal = state.findings.filter((f) => f.fixable && f.fix_action).length;
  const manualTotal = state.findings.filter((f) => !(f.fixable && f.fix_action)).length;
  const accepted = acceptedIds.size;

  let text = `Grade ${grade} · ${score} / 100. `;
  if (!state.findings.length) {
    text = `Grade ${grade} · ${score} / 100. This deck looks accessible.`;
  } else {
    const parts = [];
    parts.push(`${accepted} of ${fixableTotal} ${plural(fixableTotal, "fix", "fixes")} accepted`);
    if (manualTotal) parts.push(`${manualTotal} ${plural(manualTotal, "item", "items")} need${manualTotal === 1 ? "s" : ""} manual review`);
    text += parts.join("; ") + ".";
  }
  state.refs.summary.textContent = text;

  if (state.refs.exportBtn) state.refs.exportBtn.disabled = accepted < 1;
}

/* ============================================================
   Export bar
   ============================================================ */
function buildExportBar(state) {
  const bar = el("div", "export-bar");

  const exportBtn = btn("btn btn-primary", "Download fixed PowerPoint", () => runExport(state, "pptx"));
  exportBtn.disabled = true;
  state.refs.exportBtn = exportBtn;
  bar.appendChild(exportBtn);

  bar.appendChild(btn("btn btn-ghost", "Download report", () => runExport(state, "report")));

  const status = el("span", "export-status");
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  state.refs.exportStatus = status;
  bar.appendChild(status);

  const note = el("p", "export-note");
  note.textContent = "Processed privately and never stored. You get a fixed copy — your original is untouched.";
  bar.appendChild(note);

  return bar;
}

async function runExport(state, which) {
  if (!state.file) { state.refs.exportStatus.textContent = "Original file unavailable — re-upload to export."; return; }
  const plan = [...state.plan.values()];
  if (which === "pptx" && !plan.length) { state.refs.exportStatus.textContent = "Accept at least one fix first."; return; }

  state.refs.exportStatus.textContent = which === "pptx" ? "Building your fixed file…" : "Building your report…";
  state.refs.exportBtn.disabled = true;

  const fd = new FormData();
  fd.append("files", state.file, state.filename);
  fd.append("plan", JSON.stringify(plan));

  let resp;
  try {
    resp = await fetch("/api/export", {
      method: "POST",
      headers: { "x-slidecheck-password": sessionStorage.getItem(PW_KEY) || "" },
      body: fd,
    });
  } catch {
    state.refs.exportStatus.textContent = "Couldn't reach the server. Try again.";
    updateScore(state);
    return;
  }

  if (resp.status === 401) { handle401(); return; }
  if (!resp.ok) {
    let detail = `Export failed (error ${resp.status}).`;
    try { const j = await resp.json(); if (j.detail) detail = String(j.detail); } catch { /* ignore */ }
    state.refs.exportStatus.textContent = detail;
    updateScore(state);
    return;
  }

  let data;
  try { data = await resp.json(); } catch { state.refs.exportStatus.textContent = "Couldn't read the server response."; updateScore(state); return; }
  const result = (data.files || [])[0];
  if (!result || result.error) {
    state.refs.exportStatus.textContent = result && result.error ? String(result.error) : "Export failed.";
    updateScore(state);
    return;
  }

  if (which === "pptx") {
    if (!result.fixed_pptx_b64) { state.refs.exportStatus.textContent = "No fixed file was produced."; updateScore(state); return; }
    const blob = b64ToBlob(result.fixed_pptx_b64,
      "application/vnd.openxmlformats-officedocument.presentationml.presentation");
    download(blob, result.fixed_filename || "accessible.pptx");
    state.refs.exportStatus.textContent = "Downloaded.";
  } else {
    const blob = new Blob([result.report_html || ""], { type: "text/html" });
    download(blob, reportName(state.filename));
    state.refs.exportStatus.textContent = "Report downloaded.";
  }
  updateScore(state);
}

/* ============================================================
   Small helpers
   ============================================================ */
function el(tag, cls) { const e = document.createElement(tag); if (cls) e.className = cls; return e; }
function btn(cls, label, onClick) {
  const b = document.createElement("button");
  b.type = "button"; b.className = cls; b.textContent = label;
  b.addEventListener("click", onClick);
  return b;
}
/* author-authored static SVG only — no server data interpolated */
function staticSvg(markup) { const s = document.createElement("span"); s.style.display = "inline-flex"; s.innerHTML = markup; return s; }

function plural(n, one, many) { return n === 1 ? one : many; }

function scLabel(f) {
  const refs = (f.sc_refs && f.sc_refs.length) ? f.sc_refs.join(", ") : "";
  const ver = f.wcag_version ? ` · ${f.wcag_version}` : "";
  if (refs) return `SC ${refs}${ver}`;
  return f.section508 ? "508" : (f.category || "WCAG");
}

function reportName(filename) {
  return String(filename || "presentation").replace(/\.pptx$/i, "") + "_a11y_report.html";
}
function download(blob, filename) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
function b64ToBlob(b64, type) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Blob([bytes], { type });
}
/* HTML-escape helper for any place a string must be composed into markup */
function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

init();
