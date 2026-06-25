const PW_KEY = "slidecheck-password";
const $ = (id) => document.getElementById(id);

function showApp() { $("gate").hidden = true; $("app").hidden = false; }
function showGate(msg) {
  $("app").hidden = true; $("gate").hidden = false;
  $("gate-error").textContent = msg || "";
}

function init() {
  if (sessionStorage.getItem(PW_KEY)) showApp(); else showGate("");
  $("unlock").addEventListener("click", () => {
    const pw = $("password").value.trim();
    if (!pw) { $("gate-error").textContent = "Please enter the password."; return; }
    sessionStorage.setItem(PW_KEY, pw);
    showApp();
  });
  $("password").addEventListener("keydown", (e) => { if (e.key === "Enter") $("unlock").click(); });

  const dz = $("dropzone"), input = $("file-input");
  dz.addEventListener("click", () => input.click());
  dz.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } });
  input.addEventListener("change", () => { if (input.files.length) upload(input.files); });
  ["dragenter", "dragover"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("drag"); }));
  dz.addEventListener("drop", (e) => { if (e.dataTransfer.files.length) upload(e.dataTransfer.files); });
}

async function upload(fileList) {
  const files = [...fileList].filter((f) => f.name.toLowerCase().endsWith(".pptx"));
  if (!files.length) { $("status").textContent = "Please choose a PowerPoint (.pptx) file."; return; }
  $("results").innerHTML = "";
  $("status").textContent = files.length > 1
    ? `Checking ${files.length} files… generating alt text…`
    : "Checking your slides… generating alt text…";

  const fd = new FormData();
  files.forEach((f) => fd.append("files", f, f.name));
  let resp;
  try {
    resp = await fetch("/api/process", {
      method: "POST",
      headers: { "x-slidecheck-password": sessionStorage.getItem(PW_KEY) || "" },
      body: fd,
    });
  } catch {
    $("status").textContent = "Could not reach the server. Please try again.";
    return;
  }

  if (resp.status === 401) { sessionStorage.removeItem(PW_KEY); showGate("That password didn't work. Try again."); $("status").textContent = ""; document.getElementById("password").focus(); return; }
  if (!resp.ok) {
    let detail = `Something went wrong (error ${resp.status}).`;
    try { const j = await resp.json(); if (j.detail) detail = j.detail; } catch {}
    $("status").textContent = detail;
    return;
  }

  const data = await resp.json();
  $("status").textContent = "Done.";
  render(data.files);
}

function render(files) {
  const root = $("results");
  if (files.length > 1) root.appendChild(overviewTable(files));
  files.forEach((f) => root.appendChild(fileCard(f)));
}

function overviewTable(files) {
  const t = document.createElement("table");
  t.className = "overview";
  // thead is 100% static markup — no user data
  t.innerHTML = "<thead><tr><th>File</th><th>Errors</th><th>Warnings</th><th>Auto-fixed</th><th>Needs manual fix</th></tr></thead>";
  const body = document.createElement("tbody");
  files.forEach((f) => {
    const s = f.summary || {};
    const row = document.createElement("tr");
    if (f.error) {
      // esc() used for both user-derived strings — safe
      row.innerHTML = `<td>${esc(f.filename)}</td><td colspan="4" class="error">Could not process: ${esc(f.error)}</td>`;
    } else {
      // Build cells with textContent so summary counts are never interpreted as HTML
      const cells = [
        { text: f.filename },
        { text: num(s.error), cls: "num" },
        { text: num(s.warning), cls: "num" },
        { text: num(s.auto_fixed), cls: "num" },
        { text: num(s.manual), cls: "num" },
      ];
      cells.forEach(({ text, cls }) => {
        const td = document.createElement("td");
        if (cls) td.className = cls;
        td.textContent = text;
        row.appendChild(td);
      });
    }
    body.appendChild(row);
  });
  t.appendChild(body);
  return t;
}

function fileCard(f) {
  const card = document.createElement("div");
  card.className = "file-card";
  const h = document.createElement("h2");
  h.textContent = f.filename;
  card.appendChild(h);

  if (f.error) {
    const p = document.createElement("p");
    p.className = "error";
    p.textContent = `Could not process this file: ${f.error}`;
    card.appendChild(p);
    return card;
  }

  const s = f.summary || {};
  const issues = num(s.error) + num(s.warning);
  const badges = document.createElement("div");
  badges.className = "badges";
  // Build each badge with textContent — no HTML interpretation of server data
  [
    { text: `${issues} issue(s) found`, cls: issues ? "err" : "ok" },
    { text: `${num(s.auto_fixed)} auto-fixed`, cls: "ok" },
    { text: `${num(s.manual)} need a manual fix`, cls: "" },
  ].forEach(({ text, cls }) => {
    const span = document.createElement("span");
    span.className = "badge" + (cls ? " " + cls : "");
    span.textContent = text;
    badges.appendChild(span);
  });
  card.appendChild(badges);

  const dl = document.createElement("div");
  dl.className = "downloads";
  dl.appendChild(downloadButton(
    "Download fixed PowerPoint", f.fixed_filename,
    b64ToBlob(f.fixed_pptx_b64, "application/vnd.openxmlformats-officedocument.presentationml.presentation")));
  dl.appendChild(downloadButton(
    "Download report", reportName(f.filename),
    new Blob([f.report_html], { type: "text/html" })));
  card.appendChild(dl);

  const frame = document.createElement("iframe");
  frame.className = "report-frame";
  frame.title = `Accessibility report for ${f.filename}`;
  frame.setAttribute("sandbox", "");  // block scripts in user-derived report HTML; inline CSS still renders
  frame.srcdoc = f.report_html;
  card.appendChild(frame);
  return card;
}

function downloadButton(label, filename, blob) {
  const a = document.createElement("a");
  a.textContent = label;
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.className = "download";
  const btn = document.createElement("button");
  btn.type = "button";
  btn.textContent = label;
  btn.addEventListener("click", () => {
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 0);
  });
  return btn;
}

/** Coerce a summary count to a safe integer — prevents non-numeric server values from being rendered as HTML. */
function num(v) { return Math.max(0, parseInt(v, 10) || 0); }
function reportName(filename) {
  return filename.replace(/\.pptx$/i, "") + "_a11y_report.html";
}
function b64ToBlob(b64, type) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Blob([bytes], { type });
}
function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

init();
