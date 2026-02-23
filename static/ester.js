(function () {
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  // Tabs
  $$(".nav a").forEach(a => {
    a.addEventListener("click", (e) => {
      e.preventDefault();
      $$(".nav a").forEach(x => x.classList.remove("active"));
      a.classList.add("active");
      const tab = a.getAttribute("data-tab");
      $$(".tab").forEach(x => x.classList.remove("active"));
      $("#tab-" + tab).classList.add("active");
    });
  });

  // Chat
  const log = $("#chat-log");
  function pushUser(text) {
    const el = document.createElement("div");
    el.className = "chat-item";
    el.innerHTML = `<span class="who">Vy:</span> ${escapeHtml(text)}`;
    log.appendChild(el); log.scrollTop = log.scrollHeight;
  }
  function pushAI(text) {
    const el = document.createElement("div");
    el.className = "chat-item";
    el.innerHTML = `<span class="who ai">Ester:</span> ${escapeHtml(text)}`;
    log.appendChild(el); log.scrollTop = log.scrollHeight;
  }
  function escapeHtml(s){ return (s||"").replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

  $("#chat-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = $("#query").value.trim();
    if (!q) return;
    pushUser(q);
    $("#query").value = "";
    const mode = $("#mode").value;
    const use_rag = $("#use_rag").checked;
    const r = await fetch("/chat/message", {
      method: "POST",
      headers: {"Content-Type":"application/json", "Authorization": window.localStorage.getItem("jwt") || ""},
      body: JSON.stringify({ query: q, mode, use_rag, temperature: 0.0 })
    });
    if (r.status !== 200) { pushAI("Oshibka: " + r.status); return; }
    const j = await r.json();
    pushAI(j.answer || "");
    $("#agenda").innerHTML = (j.proactive?.agenda || []).map(x => `<li>${escapeHtml(x)}</li>`).join("");
    $("#emotions").textContent = JSON.stringify(j.emotions || {}, null, 2);
  });

  // Feed
  async function loadFeed() {
    const limit = parseInt($("#feed-limit").value || "20", 10);
    const tags = ($("#feed-tags").value || "tg,dream,proactive,share").trim();
    const r = await fetch(`/feed/latest?limit=${limit}&tags=${encodeURIComponent(tags)}`, {
      headers: {"Authorization": window.localStorage.getItem("jwt") || ""}
    });
    if (r.status !== 200) { $("#feed-list").innerHTML = `<div class="mono">Oshibka: ${r.status}</div>`; return; }
    const j = await r.json();
    const items = j.items || [];
    $("#feed-list").innerHTML = items.map(it => `
      <div class="feed-item">
        <div class="tags">${(it.tags||[]).map(t=>`<code>${escapeHtml(t)}</code>`).join(" ")}</div>
        <div class="text">${escapeHtml(it.text || "")}</div>
      </div>
    `).join("");
  }
  $("#feed-refresh").addEventListener("click", loadFeed);
  // initial load
  loadFeed();

  // Upload
  $("#upload-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const files = $("#file-input").files;
    if (!files || !files.length) return;
    const out = [];
    for (const f of files) {
      const fd = new FormData();
      fd.append("file", f, f.name);
      const r = await fetch("/ingest/file", {
        method: "POST",
        headers: {"Authorization": window.localStorage.getItem("jwt") || ""},
        body: fd
      });
      const j = await r.json().catch(()=>({}));
      out.push({name: f.name, status: r.status, resp: j});
    }
    $("#upload-status").textContent = JSON.stringify(out, null, 2);
  });

  // Share
  $("#share-send").addEventListener("click", async () => {
    const html = $("#share-html").value;
    const title = $("#share-title").value || "untitled";
    const url = $("#share-url").value || "";
    const r = await fetch("/share/capture", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ url, title, html, text: html ? "" : html, selection: "", tags: ["ui"], note: null })
    });
    const j = await r.json().catch(()=>({}));
    $("#share-report").textContent = JSON.stringify(j, null, 2);
  });

  // Status
  async function loadStatus() {
    const g = await fetch("/session/guardian/status", { headers: {"Authorization": window.localStorage.getItem("jwt") || ""}});
    if (g.status === 200) $("#guardian-status").textContent = JSON.stringify(await g.json(), null, 2);
    const p = await fetch("/providers/status", { headers: {"Authorization": window.localStorage.getItem("jwt") || ""}});
    if (p.status === 200) $("#providers-status").textContent = JSON.stringify(await p.json(), null, 2);
  }
  loadStatus();
})();
