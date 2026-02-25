// static/telegram_control.js
(function () {
  const $ = (s) => document.querySelector(s);
  const st = $("#st"), log = $("#log");
  function status(msg, kind) {
    st.textContent = msg;
    st.className = "badge" + (kind ? " " + kind : "");
  }
  function jwt() {
    try { return localStorage.getItem("jwt") || ""; } catch { return ""; }
  }
  async function jfetch(url, opt = {}) {
    const headers = Object.assign(
      { "Content-Type": "application/json" },
      jwt() ? { "Authorization": "Bearer " + jwt() } : {}
    );
    const resp = await fetch(url, Object.assign({ method: "GET", headers }, opt));
    const raw = await resp.text();
    let js = null;
    try { js = JSON.parse(raw); } catch {}
    return { ok: resp.ok, status: resp.status, json: js, raw };
  }
  function appendLog(...args) {
    const line = args.map(x => typeof x === "string" ? x : JSON.stringify(x)).join(" ");
    log.textContent = (line + "\n" + log.textContent).slice(0, 20000);
  }

  // Actions
  async function loadMe() {
    status("getTe request...");
    const r = await jfetch("/tg/ctrl/me");
    appendLog("GET /tg/ctrl/me →", r.status, r.json || r.raw);
    status(r.ok ? "OK /me" : "ERR /me", r.ok ? "ok" : "err");
    if (r.ok && r.json && r.json.result) {
      const me = r.json.result.result || r.json.result;
      // avtozapolnenie
      $("#name").value = me.name || $("#name").value || "Claire";
    }
  }

  async function saveProfile() {
    const body = {
      name: ($("#name").value || "Claire").trim(),
      description: ($("#desc").value || "Assistant").trim(),
      short_description: ($("#sdesc").value || "Assistant").trim()
    };
    status("saving profile...");
    const r = await jfetch("/tg/ctrl/bot/profile", { method: "POST", body: JSON.stringify(body) });
    appendLog("POST /tg/ctrl/bot/profile →", r.status, r.json || r.raw);
    status(r.ok ? "OK profil" : "ERR profil", r.ok ? "ok" : "err");
  }

  async function saveCmds() {
    let cmds = [];
    try { cmds = JSON.parse($("#cmds").value || "[]"); }
    catch (e) { alert("Nevernyy JSON komand"); return; }
    status("ustanovka komand…");
    const r = await jfetch("/tg/ctrl/bot/commands", { method: "POST", body: JSON.stringify({ commands: cmds }) });
    appendLog("POST /tg/ctrl/bot/commands →", r.status, r.json || r.raw);
    status(r.ok ? "OK komandy" : "ERR komandy", r.ok ? "ok" : "err");
  }

  function loadDefault() {
    $("#cmds").value = JSON.stringify([
      { command: "start", text: "Nachat" },
      { command: "help", text: "Pomosch" },
      { command: "whoami", text: "Kto ty?" }
    ], null, 2);
  }

  // Bind
  $("#loadMe").addEventListener("click", loadMe);
  $("#saveProfile").addEventListener("click", saveProfile);
  $("#saveCmds").addEventListener("click", saveCmds);
  $("#loadDefault").addEventListener("click", loadDefault);

  // Boot
  if (!jwt()) {
    status("Need ZhVT (admin/ops)", "warn");
  } else {
    status("JWT nayden", "ok");
    loadMe();
  }
})();
