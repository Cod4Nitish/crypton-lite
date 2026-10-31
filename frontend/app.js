// CRYPTON Lite UI: one state store -> one render(). Every change goes through setState.
const $ = (id) => document.getElementById(id);
const api = async (path, opts = {}) => {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts, body: opts.body && JSON.stringify(opts.body) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || r.statusText);
  return data;
};
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
};

const state = { tasks: [], filter: "all", query: "", history: [], speak: store.get("speak", false), known: new Set() };
function setState(patch) { Object.assign(state, patch); render(); }

// ---- date helpers -----------------------------------------------------------
const today = () => new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD in local time
function dueInfo(t) {
  if (!t.due) return null;
  const days = Math.round((new Date(t.due) - new Date(today())) / 86400000);
  if (t.done || Number.isNaN(days)) return { cls: "", label: t.due };
  if (days < 0) return { cls: "over", label: `overdue ${-days}d` };
  if (days === 0) return { cls: "today", label: "today" };
  if (days === 1) return { cls: "", label: "tomorrow" };
  return { cls: "", label: t.due };
}
const isOverdue = (t) => !t.done && dueInfo(t)?.cls === "over";

// ---- render -----------------------------------------------------------------
function render() {
  const { tasks, filter, query } = state;
  const open = tasks.filter((t) => !t.done);
  const pct = tasks.length ? Math.round(((tasks.length - open.length) / tasks.length) * 100) : 0;
  $("s-open").textContent = open.length;
  $("s-high").textContent = open.filter((t) => t.priority === "high").length;
  $("s-over").textContent = open.filter(isOverdue).length;
  $("pct").textContent = pct + "%";
  $("ring").style.strokeDasharray = `${pct} 100`;
  $("count").textContent = tasks.length || "";
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("on", b.dataset.f === filter));

  const q = query.trim().toLowerCase();
  const shown = tasks
    .filter((t) => filter === "all" || (filter === "open" ? !t.done : t.done))
    .filter((t) => !q || t.title.toLowerCase().includes(q));

  $("tasks").innerHTML = shown.map((t) => {
    const d = dueInfo(t);
    const fresh = state.known.size && !state.known.has(t.id);
    return `<li class="${t.done ? "done" : ""} ${fresh ? "new" : ""} ${isOverdue(t) ? "late" : ""}" data-id="${t.id}">
      <button class="check" data-act="toggle" aria-label="${t.done ? "Reopen" : "Complete"}">${t.done ? "✓" : ""}</button>
      <span class="title">${esc(t.title)}</span>
      ${d ? `<span class="due ${d.cls}">${esc(d.label)}</span>` : ""}
      <button class="pill ${esc(t.priority)}" data-act="cycle" title="Change priority">${esc(t.priority)}</button>
      <button class="del" data-act="delete" aria-label="Delete">✕</button>
    </li>`;
  }).join("") || `<li class="empty">${q ? "No matches." : filter === "done" ? "Nothing done yet. You've got this." : "All clear. Ask CRYPTON to add a task."}</li>`;
  state.known = new Set(tasks.map((t) => t.id));
  $("speak").textContent = state.speak ? "🔊 Voice on" : "🔈 Voice off";
  $("speak").setAttribute("aria-pressed", state.speak);
}

// ---- feedback ---------------------------------------------------------------
let toastTimer;
function toast(text, undo) {
  $("toast-text").textContent = text;
  $("toast-undo").hidden = !undo;
  $("toast-undo").onclick = async () => { $("toast").classList.remove("show"); await undo(); loadTasks(); };
  $("toast").classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $("toast").classList.remove("show"), undo ? 5000 : 2500);
}

function bubble(cls, html) {
  const d = document.createElement("div");
  d.className = `bubble ${cls}`;
  d.innerHTML = html;
  $("log").append(d);
  $("log").scrollTop = $("log").scrollHeight;
  d.scrollIntoView({ block: "nearest", behavior: "smooth" });
  return d;
}

function say(text) {
  if (!state.speak || !("speechSynthesis" in window)) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 1.05;
  speechSynthesis.speak(u);
}

// ---- data -------------------------------------------------------------------
async function loadTasks() { setState({ tasks: await api("/api/tasks") }); }

const TOOL_ICON = { create_task: "＋", list_tasks: "☰", complete_task: "✓", update_task: "✎", delete_task: "✕" };

async function send(text) {
  text = text.trim();
  if (!text || $("send").disabled) return;
  bubble("user", esc(text));
  $("msg").value = "";
  $("send").disabled = true;
  $("core").classList.add("busy");
  const typing = bubble("bot typing", "Thinking");
  const t0 = performance.now();
  try {
    const data = await api("/api/chat", { method: "POST", body: { message: text, history: state.history } });
    const secs = ((performance.now() - t0) / 1000).toFixed(1);
    const tools = data.actions.map((a) =>
      `<div class="tool ${a.result.ok ? "" : "fail"}">${TOOL_ICON[a.tool] || "⚙"} ${esc(a.tool)}(${esc(JSON.stringify(a.args))}) → ${a.result.ok ? "ok" : esc(a.result.error)}</div>`).join("");
    typing.className = "bubble bot";
    typing.innerHTML = esc(data.reply) + tools + `<div class="meta">on-device · ${secs}s</div>`;
    state.history = [...state.history, { role: "user", content: text }, { role: "assistant", content: data.memory || data.reply }].slice(-6);
    setState({ tasks: data.tasks });
    say(data.reply);
  } catch (e) {
    typing.className = "bubble err";
    typing.textContent = "Error: " + e.message;
  } finally {
    $("send").disabled = false;
    $("core").classList.remove("busy");
    if (matchMedia("(pointer: fine)").matches) $("msg").focus();
  }
}

// ---- events -----------------------------------------------------------------
$("chat-form").addEventListener("submit", (e) => { e.preventDefault(); send($("msg").value); });
$("msg").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send($("msg").value); } });
$("chips").addEventListener("click", (e) => { if (e.target.tagName === "BUTTON") send(e.target.textContent); });
$("tabs").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) setState({ filter: b.dataset.f }); });
$("search").addEventListener("input", (e) => setState({ query: e.target.value }));

$("add-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const title = $("add-title").value.trim();
  if (!title) return;
  await api("/api/tasks", { method: "POST", body: { title, priority: $("add-priority").value } });
  $("add-title").value = "";
  loadTasks();
});

const NEXT = { low: "medium", medium: "high", high: "low" };
$("tasks").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-act]");
  const li = e.target.closest("li[data-id]");
  if (!btn || !li) return;
  const t = state.tasks.find((x) => x.id === Number(li.dataset.id));
  if (btn.dataset.act === "toggle") {
    await api(`/api/tasks/${t.id}`, { method: "PATCH", body: { done: !t.done } });
    toast(t.done ? "Reopened" : `Done: ${t.title}`, () => api(`/api/tasks/${t.id}`, { method: "PATCH", body: { done: t.done } }));
  } else if (btn.dataset.act === "cycle") {
    await api(`/api/tasks/${t.id}`, { method: "PATCH", body: { priority: NEXT[t.priority] } });
  } else if (btn.dataset.act === "delete") {
    li.classList.add("leaving");
    await api(`/api/tasks/${t.id}`, { method: "DELETE" });
    toast(`Deleted: ${t.title}`, () => api("/api/tasks/restore", { method: "POST", body: t }));
  }
  loadTasks();
});

$("speak").onclick = () => { state.speak = !state.speak; store.set("speak", state.speak); render(); if (state.speak) say("Voice replies on."); };
$("help").onclick = () => $("help-dlg").showModal();

document.addEventListener("keydown", (e) => {
  const inField = ["TEXTAREA", "INPUT", "SELECT"].includes(document.activeElement.tagName);
  if (e.key === "Escape") { $("search").value = ""; setState({ query: "" }); }
  if (inField) return;
  if (e.key === "/") { e.preventDefault(); $("msg").focus(); }
  else if (e.key.toLowerCase() === "v") $("speak").click();
  else if (e.key === "?") $("help").click();
});

// Browser speech fallback for when Wispr Flow is unavailable (Chrome/Edge; needs HTTPS on phones).
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
if (!SR) $("mic").hidden = true;
else {
  const rec = new SR();
  rec.lang = "en-US";
  rec.interimResults = true;
  rec.onresult = (e) => { $("msg").value = [...e.results].map((r) => r[0].transcript).join(""); };
  rec.onerror = (e) => toast("Mic: " + e.error);
  rec.onend = () => { $("mic").classList.remove("on"); send($("msg").value); };
  $("mic").onclick = () => {
    if ($("mic").classList.contains("on")) return rec.stop();
    $("mic").classList.add("on");
    rec.start();
  };
}

// ---- PWA: install button + offline shell --------------------------------------
let installEvt;
window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); installEvt = e; $("install").hidden = false; });
$("install").onclick = async () => {
  if (!installEvt) return;
  installEvt.prompt();
  await installEvt.userChoice;
  installEvt = null;
  $("install").hidden = true;
};
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});

async function health() {
  try {
    const h = await api("/api/health");
    const ok = h.ollama === "ok" && h.model_installed;
    $("status").className = "status " + (ok ? "ok" : "bad");
    $("status").textContent = ok ? `● Local AI · ${h.model}` : `● Ollama ${h.ollama}${h.model_installed ? "" : " · model missing"}`;
  } catch { $("status").className = "status bad"; $("status").textContent = "● API offline"; }
}

const hr = new Date().getHours();
$("greet").textContent = (hr < 12 ? "Good morning." : hr < 18 ? "Good afternoon." : "Good evening.") + " Say it, it's done.";
loadTasks();
health();
setInterval(health, 15000);
