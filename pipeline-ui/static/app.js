"use strict";

const state = {
  stages: [],
  currentJob: null,
  currentEventSource: null,
  runningJobs: new Set(),
  selectedActivity: null,
  catalog: [],
  catalogSelected: new Set(),
};

// ---------- bootstrap ----------
async function init() {
  setStatus("loading…");
  try {
    const res = await fetch("/api/stages");
    const data = await res.json();
    state.stages = data.stages;
    renderPipeline();
    setStatus("connected", "ok");
  } catch (e) {
    setStatus("offline", "err");
    console.error(e);
    return;
  }
  bindTabs();
  bindModal();
  bindLogs();
  bindCatalog();
  loadJobs();
  setInterval(loadJobs, 4000);
}

function setStatus(text, cls) {
  const el = document.getElementById("status-indicator");
  el.textContent = text;
  el.className = "status" + (cls ? " " + cls : "");
}

// ---------- tabs ----------
function bindTabs() {
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById("view-" + btn.dataset.tab).classList.add("active");
      if (btn.dataset.tab === "jobs") loadJobs();
      if (btn.dataset.tab === "catalog" && !state.catalog.length) loadCatalog();
    });
  });
}

// ---------- pipeline ----------
function renderPipeline() {
  const root = document.getElementById("pipeline-graph");
  root.innerHTML = "";
  for (const stage of state.stages) {
    const el = document.createElement("div");
    el.className = "stage";
    el.style.setProperty("--stage-color", stage.color);

    const head = document.createElement("div");
    head.className = "stage-head";
    head.innerHTML = `<span class="icon">${stage.icon}</span><h2>${escapeHtml(stage.title)}</h2>`;
    el.appendChild(head);

    const grid = document.createElement("div");
    grid.className = "activity-grid";
    for (const act of stage.activities) {
      const card = document.createElement("div");
      card.className = "activity";
      card.dataset.activityId = act.id;

      const cmdHint = act.cmd.join(" ");
      let badges = "";
      if (act.danger) badges += `<span class="badge">PROD</span>`;
      else if (act.long_running) badges += `<span class="badge long">LONG</span>`;

      card.innerHTML = `
        ${badges}
        <h3>${escapeHtml(act.title)}</h3>
        <p>${escapeHtml(act.description)}</p>
        <div class="cmd-hint">$ ${escapeHtml(cmdHint)}</div>
      `;
      card.addEventListener("click", () => openModal(stage, act));
      grid.appendChild(card);
    }
    el.appendChild(grid);
    root.appendChild(el);
  }
}

// ---------- modal ----------
function bindModal() {
  document.getElementById("modal-close").addEventListener("click", closeModal);
  document.getElementById("modal-cancel").addEventListener("click", closeModal);
  document.getElementById("modal-run").addEventListener("click", runFromModal);
  document.getElementById("modal").addEventListener("click", (e) => {
    if (e.target.id === "modal") closeModal();
  });
}

function openModal(stage, act) {
  state.selectedActivity = act;
  document.getElementById("modal-title").textContent = act.title;
  document.getElementById("modal-desc").textContent = act.description;
  document.getElementById("modal-cmd").textContent = "$ " + act.cmd.join(" ");

  const form = document.getElementById("modal-form");
  form.innerHTML = "";
  for (const p of act.params || []) {
    const wrap = document.createElement("label");
    wrap.dataset.name = p.name;
    if (p.kind === "bool") {
      wrap.className = "row-bool";
      wrap.innerHTML = `<input type="checkbox" name="${p.name}"/> <span>${escapeHtml(p.label)}</span>`;
    } else if (p.kind === "select") {
      const opts = (p.choices || []).map((c) => `<option value="${escapeHtml(c)}">${escapeHtml(c || "(default)")}</option>`).join("");
      wrap.innerHTML = `<span>${escapeHtml(p.label)}</span><select name="${p.name}">${opts}</select>`;
    } else if (p.kind === "textarea") {
      wrap.innerHTML = `<span>${escapeHtml(p.label)}</span><textarea name="${p.name}" rows="3" placeholder="${escapeHtml(p.placeholder || "")}">${escapeHtml(String(p.default || ""))}</textarea>`;
    } else {
      wrap.innerHTML = `<span>${escapeHtml(p.label)}</span><input type="text" name="${p.name}" value="${escapeHtml(String(p.default || ""))}" placeholder="${escapeHtml(p.placeholder || "")}"/>`;
    }
    if (p.help) {
      const h = document.createElement("div");
      h.className = "muted";
      h.textContent = p.help;
      wrap.appendChild(h);
    }
    form.appendChild(wrap);
  }
  if (act.danger) {
    const warn = document.createElement("div");
    warn.style.cssText = "color:var(--err);font-size:12px;font-weight:600;padding:8px 10px;background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.4);border-radius:6px;";
    warn.textContent = "⚠ Production-impacting. Double-check args before running.";
    form.appendChild(warn);
  }
  document.getElementById("modal").classList.remove("hidden");
}

function closeModal() {
  document.getElementById("modal").classList.add("hidden");
  state.selectedActivity = null;
}

async function runFromModal() {
  const act = state.selectedActivity;
  if (!act) return;
  const params = {};
  document.querySelectorAll("#modal-form [name]").forEach((el) => {
    if (el.type === "checkbox") params[el.name] = el.checked;
    else params[el.name] = el.value;
  });
  closeModal();
  await runActivity(act.id, params);
}

// ---------- run ----------
async function runActivity(activityId, params) {
  setStatus("starting " + activityId + "…");
  try {
    const res = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ activity_id: activityId, params: params || {} }),
    });
    if (!res.ok) {
      const t = await res.text();
      alert("Failed to start: " + t);
      setStatus("error", "err");
      return;
    }
    const { job } = await res.json();
    state.runningJobs.add(activityId);
    setRunningClass(activityId, true);
    switchTo("logs");
    streamJob(job);
    loadJobs();
  } catch (e) {
    alert("Error: " + e.message);
    setStatus("error", "err");
  }
}

function setRunningClass(activityId, isRunning) {
  document.querySelectorAll(`.activity[data-activity-id="${activityId}"]`).forEach((el) => {
    el.classList.toggle("running", isRunning);
  });
}

function switchTo(tab) {
  document.querySelector(`.tab[data-tab="${tab}"]`).click();
}

// ---------- streaming ----------
function streamJob(job) {
  if (state.currentEventSource) state.currentEventSource.close();
  state.currentJob = job;
  document.getElementById("log-title").textContent = `${job.title}  ·  ${job.id}  ·  $ ${job.cmd.join(" ")}`;
  const out = document.getElementById("log-output");
  out.textContent = "";

  const es = new EventSource(`/api/jobs/${job.id}/stream`);
  state.currentEventSource = es;
  es.onmessage = (ev) => {
    try {
      const d = JSON.parse(ev.data);
      if (d.line) {
        appendLog(d.line);
      }
    } catch (e) { /* noop */ }
  };
  es.addEventListener("done", (ev) => {
    try {
      const snap = JSON.parse(ev.data);
      const cls = snap.status === "success" ? "ok" : "err";
      setStatus(`${snap.status} (exit ${snap.exit_code})`, cls);
      state.runningJobs.delete(snap.activity_id);
      setRunningClass(snap.activity_id, false);
    } catch (_) {}
    es.close();
    loadJobs();
  });
  es.onerror = () => { /* let server reconnect or end */ };
}

function appendLog(line) {
  const out = document.getElementById("log-output");
  const atBottom = out.scrollTop + out.clientHeight >= out.scrollHeight - 30;
  out.textContent += line;
  if (atBottom) out.scrollTop = out.scrollHeight;
}

// ---------- jobs panel ----------
async function loadJobs() {
  try {
    const res = await fetch("/api/jobs");
    const { jobs } = await res.json();
    renderJobs(jobs);
    state.runningJobs.clear();
    document.querySelectorAll(".activity.running").forEach((el) => el.classList.remove("running"));
    for (const j of jobs) {
      if (j.status === "running") {
        state.runningJobs.add(j.activity_id);
        setRunningClass(j.activity_id, true);
      }
    }
  } catch (e) { /* noop */ }
}

function renderJobs(jobs) {
  const tbody = document.getElementById("jobs-tbody");
  if (!jobs.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="muted">No jobs yet — click any activity card to run one.</td></tr>`;
    return;
  }
  tbody.innerHTML = jobs.map((j) => {
    const dur = j.duration ? j.duration.toFixed(1) + "s" : "-";
    const started = new Date(j.started_at * 1000).toLocaleTimeString();
    return `<tr>
      <td><span class="status-pill ${j.status}">${j.status}</span></td>
      <td>${escapeHtml(j.title)}<div class="muted" style="font-family:var(--mono);font-size:11px">${escapeHtml(j.cmd.join(" "))}</div></td>
      <td>${started}</td>
      <td>${dur}</td>
      <td>${j.exit_code ?? "-"}</td>
      <td><button class="btn-ghost" data-job="${j.id}">view</button></td>
    </tr>`;
  }).join("");
  tbody.querySelectorAll("button[data-job]").forEach((b) => {
    b.addEventListener("click", async () => {
      const id = b.dataset.job;
      const r = await fetch(`/api/jobs/${id}`);
      const { job } = await r.json();
      switchTo("logs");
      streamJob(job);
    });
  });
}

document.getElementById("refresh-jobs").addEventListener("click", loadJobs);

// ---------- logs panel buttons ----------
function bindLogs() {
  document.getElementById("clear-log").addEventListener("click", () => {
    document.getElementById("log-output").textContent = "";
  });
  document.getElementById("stop-job").addEventListener("click", async () => {
    if (!state.currentJob) return;
    await fetch(`/api/jobs/${state.currentJob.id}/stop`, { method: "POST" });
    loadJobs();
  });
}

// ---------- catalog ----------
function bindCatalog() {
  document.getElementById("catalog-refresh").addEventListener("click", loadCatalog);
  document.getElementById("catalog-search").addEventListener("input", renderCatalogFiltered);
  document.getElementById("catalog-category").addEventListener("change", renderCatalogFiltered);
  document.getElementById("catalog-sort").addEventListener("change", renderCatalogFiltered);
  document.getElementById("catalog-recent-only").addEventListener("change", renderCatalogFiltered);
  document.getElementById("catalog-select-all").addEventListener("change", (e) => {
    const visible = Array.from(document.querySelectorAll(".catalog-row-check"));
    visible.forEach((cb) => {
      cb.checked = e.target.checked;
      if (e.target.checked) state.catalogSelected.add(cb.dataset.asin);
      else state.catalogSelected.delete(cb.dataset.asin);
    });
    updateDeleteBtn();
  });
  document.getElementById("catalog-delete-selected").addEventListener("click", deleteCatalogSelected);
}

async function loadCatalog() {
  document.getElementById("catalog-count").textContent = "loading…";
  try {
    const res = await fetch("/api/catalog");
    const data = await res.json();
    state.catalog = data.products;
    state.catalogSelected.clear();
    populateCategoryFilter();
    renderCatalogFiltered();
  } catch (e) {
    document.getElementById("catalog-tbody").innerHTML =
      `<tr><td colspan="9" class="muted" style="text-align:center;padding:30px">Failed to load catalog</td></tr>`;
  }
}

function populateCategoryFilter() {
  const cats = [...new Set(state.catalog.map((p) => p.category).filter(Boolean))].sort();
  const sel = document.getElementById("catalog-category");
  const prev = sel.value;
  sel.innerHTML = `<option value="">All categories</option>` +
    cats.map((c) => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("");
  if (cats.includes(prev)) sel.value = prev;
}

function getFilteredSorted() {
  const q = document.getElementById("catalog-search").value.toLowerCase();
  const cat = document.getElementById("catalog-category").value;
  const sort = document.getElementById("catalog-sort").value;
  const recentOnly = document.getElementById("catalog-recent-only").checked;

  let products = state.catalog.filter((p) => {
    if (cat && p.category !== cat) return false;
    if (q && !p.name.toLowerCase().includes(q)) return false;
    if (recentOnly && !p.date) return false;
    return true;
  });

  if (recentOnly) {
    const dates = [...new Set(products.map((p) => p.date).filter(Boolean))].sort().reverse();
    const recent = new Set(dates.slice(0, 3));
    products = products.filter((p) => recent.has(p.date));
  }

  products = [...products].sort((a, b) => {
    if (sort === "price-desc") return parsePrice(b.price) - parsePrice(a.price);
    if (sort === "score-desc") return (Number(b.score) || 0) - (Number(a.score) || 0);
    if (sort === "rating-desc") return (Number(b.rating) || 0) - (Number(a.rating) || 0);
    if (sort === "date-desc") return (b.date || "").localeCompare(a.date || "");
    return a.name.localeCompare(b.name);
  });

  return products;
}

function parsePrice(p) {
  const m = String(p || "").match(/[\d,]+(\.\d+)?/);
  return m ? parseFloat(m[0].replace(",", "")) : 0;
}

function renderCatalogFiltered() {
  const products = getFilteredSorted();
  const tbody = document.getElementById("catalog-tbody");

  if (!products.length) {
    tbody.innerHTML = `<tr><td colspan="9" class="muted" style="text-align:center;padding:30px">No products match filters.</td></tr>`;
    document.getElementById("catalog-count").textContent = "0 products";
    return;
  }

  document.getElementById("catalog-count").textContent = `${products.length} of ${state.catalog.length} products`;

  tbody.innerHTML = products.map((p) => {
    const checked = state.catalogSelected.has(p.asin) ? "checked" : "";
    const score = Number(p.score) || 0;
    const scoreCls = score >= 8 ? "score-hi" : score >= 6 ? "score-mid" : "score-lo";
    const rating = Number(p.rating) || 0;
    const ratingStars = rating >= 4.5 ? "⭐" : "";
    const asinSafe = escapeHtml(p.asin);
    return `<tr class="catalog-row" data-asin="${asinSafe}">
      <td><input type="checkbox" class="catalog-row-check" data-asin="${asinSafe}" ${checked}/></td>
      <td class="catalog-name" title="${escapeHtml(p.name)}">${escapeHtml(p.name.slice(0, 72))}${p.name.length > 72 ? "…" : ""}</td>
      <td><span class="cat-pill">${escapeHtml(p.category)}</span></td>
      <td class="catalog-price">${escapeHtml(p.price)}</td>
      <td>${ratingStars}${rating || "–"}</td>
      <td>${Number(p.reviews).toLocaleString() || "–"}</td>
      <td><span class="score-pill ${scoreCls}">${score}</span></td>
      <td class="muted">${escapeHtml(p.date)}</td>
      <td>
        ${p.url ? `<a href="${escapeHtml(p.url)}" target="_blank" class="btn-ghost btn-amz">Amazon ↗</a>` : ""}
        <button class="btn-warn btn-del" data-asin="${asinSafe}" title="Delete">✕</button>
      </td>
    </tr>`;
  }).join("");

  tbody.querySelectorAll(".catalog-row-check").forEach((cb) => {
    cb.addEventListener("change", (e) => {
      if (e.target.checked) state.catalogSelected.add(e.target.dataset.asin);
      else state.catalogSelected.delete(e.target.dataset.asin);
      updateDeleteBtn();
    });
  });

  tbody.querySelectorAll(".btn-del").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const asin = btn.dataset.asin;
      if (!asin) return;
      await deleteCatalogAsins([asin]);
    });
  });
}

function updateDeleteBtn() {
  const btn = document.getElementById("catalog-delete-selected");
  const n = state.catalogSelected.size;
  btn.disabled = n === 0;
  btn.textContent = n > 0 ? `Delete selected (${n})` : "Delete selected";
}

async function deleteCatalogSelected() {
  const asins = [...state.catalogSelected];
  if (!asins.length) return;
  if (!confirm(`Delete ${asins.length} product(s)? This cannot be undone.`)) return;
  await deleteCatalogAsins(asins);
}

async function deleteCatalogAsins(asins) {
  try {
    const res = await fetch("/api/catalog/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ asins }),
    });
    const data = await res.json();
    if (!res.ok) { alert("Delete failed: " + (data.error || res.status)); return; }
    asins.forEach((a) => state.catalogSelected.delete(a));
    updateDeleteBtn();
    await loadCatalog();
  } catch (e) {
    alert("Error: " + e.message);
  }
}

// ---------- utils ----------
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

init();
