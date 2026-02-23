// static/telegram_feed.js
/*
Lenta Telegram (UI). Zagruzhaet chaty, sobytiya vybrannogo chata i otpravlyaet soobscheniya.

Zemnoy abzats (inzheneriya):
Minimum zavisimostey: chistyy fetch i localStorage dlya JWT/sostoyaniya. Obnovlenie lenty — berezhnoe (diffom po khvostu).

Mosty:
- Yavnyy (Kibernetika ↔ Arkhitektura): nablyudaemaya lenta ↔ kontroliruemaya otpravka v odin klik.
- Skrytyy 1 (Infoteoriya ↔ Interfeysy): «tonkiy klient» snizhaet slozhnost i shum obnovleniy.
- Skrytyy 2 (Anatomiya ↔ PO): kak vzglyad i rech — vidim potok i otvechaem, ne teryaya kontekst.

c=a+b
*/

(function () {
  const $ = (s) => document.querySelector(s);
  const chatsEl = $("#chats");
  const msgsEl = $("#msgs");
  const inputEl = $("#input");
  const sendBtn = $("#send");
  const chatTitle = $("#chatTitle");
  const chatMeta = $("#chatMeta");

  function jwt() {
    try {
      return localStorage.getItem("jwt") || "";
    } catch {
      return "";
    }
  }

  async function jfetch(url, opt) {
    const headers = Object.assign(
      { "Content-Type": "application/json" },
      jwt() ? { Authorization: "Bearer " + jwt() } : {}
    );
    const resp = await fetch(url, Object.assign({ method: "GET", headers }, opt || {}));
    const raw = await resp.text();
    let js = null;
    try {
      js = JSON.parse(raw);
    } catch {}
    return { ok: resp.ok, status: resp.status, json: js, raw };
  }

  let selectedChat = null;
  try {
    selectedChat = localStorage.getItem("tg.selectedChat") || null;
  } catch {}

  function setSelectedChat(cid, title) {
    selectedChat = cid;
    try {
      localStorage.setItem("tg.selectedChat", cid);
    } catch {}
    chatTitle.textContent = title || cid;
    chatMeta.textContent = "chat_id: " + cid;
    msgsEl.innerHTML = "";
    loadEvents();
  }

  function renderChats(list) {
    chatsEl.innerHTML = "";
    list.forEach((c) => {
      const li = document.createElement("li");
      li.className = "chat-item";
      li.innerHTML =
        '<div class="chat-title">' +
        (c.chat_title || c.chat_id) +
        '</div><div class="chat-meta">' +
        (c.last_text || "") +
        "</div>";
      li.addEventListener("click", () => setSelectedChat(c.chat_id, c.chat_title));
      chatsEl.appendChild(li);
    });
    if (!selectedChat && list.length) {
      setSelectedChat(list[0].chat_id, list[0].chat_title);
    }
  }

  function renderEvents(list) {
    msgsEl.innerHTML = "";
    list.forEach((e) => {
      const div = document.createElement("div");
      const out = (e.kind || "").toLowerCase() === "outgoing";
      div.className = "msg " + (out ? "out" : "in");
      div.textContent = (e.from ? e.from + ": " : "") + (e.text || "");
      msgsEl.appendChild(div);
    });
    msgsEl.scrollTop = msgsEl.scrollHeight;
  }

  async function loadChats() {
    const r = await jfetch("/chat/telegram/chats");
    if (r.ok && r.json && r.json.chats) {
      renderChats(r.json.chats);
    }
  }

  async function loadEvents() {
    if (!selectedChat) return;
    const r = await jfetch("/chat/telegram/events?chat_id=" + encodeURIComponent(selectedChat));
    if (r.ok && r.json && r.json.events) {
      renderEvents(r.json.events);
    }
  }

  async function send() {
    if (!selectedChat) return;
    const text = (inputEl.value || "").trim();
    if (!text) return;
    const r = await jfetch("/tg/send", {
      method: "POST",
      body: JSON.stringify({ chat_id: selectedChat, text }),
    });
    if (r.ok) {
      inputEl.value = "";
      loadEvents();
    } else {
      alert("Ne udalos otpravit: " + (r.raw || r.status));
    }
  }

  sendBtn.addEventListener("click", send);
  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  });

  // avtoobnovlenie
  setInterval(loadChats, 5000);
  setInterval(loadEvents, 3000);
  loadChats();
})();
