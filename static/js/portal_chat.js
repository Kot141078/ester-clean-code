/* -*- coding: utf-8 -*-
 * static/js/portal_chat.js — Klientskaya logika portala (statusy integratsiy).
 *
 * MOSTY:
 * - (Yavnyy) /admin/integrations/check i /providers/status — obnovlyaem indikatory.
 * - (Skrytyy #1) Sokhranyaem suschestvuyuschiy chat API bez izmeneniy.
 * - (Skrytyy #2) Knopki rezhimov vliyayut na bekend cherez /ui/mode.
 *
 * ZEMNOY ABZATs:
 * I clicked the mode switch, sent a message, and it was immediately clear whether the required light was “on.”
 *
 * c=a+b
 */
(function(){
  const chat = document.getElementById('chat');
  const ta = document.getElementById('text');
  const btn = document.getElementById('send');
  const btnUpload = document.getElementById('btnUpload');
  const fileInput = document.getElementById('fileInput');
  const modeButtons = document.querySelectorAll('.mode button');
  const stLLM = document.getElementById('stLLM');
  const stLM = document.getElementById('stLM');
  const stTG = document.getElementById('stTG');
  const stWA = document.getElementById('stWA');
  const modelSel = document.getElementById('modelSel');
  const modelApply = document.getElementById('modelApply');
  let lastTs = 0;


async function loadModels() {
  if (!modelSel) return;
  try {
    const r = await fetch('/providers/models');
    const j = await r.json();
    if (!j.ok) return;
    modelSel.innerHTML = '';
    const preferred = j.preferred || '';
    const opt0 = document.createElement('option'); opt0.value=''; opt0.text='(po umolchaniyu)';
    modelSel.appendChild(opt0);
    for (const m of (j.models || [])) {
      const o = document.createElement('option');
      o.value = m.id; o.text = m.id;
      if (preferred && m.id === preferred) o.selected = true;
      modelSel.appendChild(o);
    }
  } catch(e) {}
}

async function applyModel() {
  try {
    const val = modelSel.value || '';
    if (!val) { /* sbrosim vybor */ }
    const r = await fetch('/ui/model', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({model: val})});
    const j = await r.json();
    addBubble('system', j.ok ? `Model ustanovlena: ${val || '(po umolchaniyu)'}` : 'Failed to apply model', (Date.now()/1000));
    refreshStatus();
  } catch(e) {}
}

if (modelSel && modelApply) {
  modelApply.addEventListener('click', applyModel);
  loadModels();
}




  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  }

  function addBubble(role, text, ts) {
    const div = el('div', 'bubble ' + (role || 'assistant'));
    const t = new Date(ts*1000).toLocaleTimeString();
    div.innerHTML = `<div style="opacity:.6;font-size:12px;margin-bottom:4px">${role} • ${t}</div>` + (text || '');
    div.style.alignSelf = (role === 'user') ? 'flex-end' : 'flex-start';
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
  }

  async function fetchFeed() {
    try {
      const r = await fetch(`/ui/chat/feed?since=${lastTs}`);
      const j = await r.json();
      if (j.ok && Array.isArray(j.items)) {
        for (const m of j.items) {
          addBubble(m.role, m.text, m.ts);
          if (m.ts > lastTs) lastTs = m.ts;
        }
      }
    } catch (e) {}
  }

  async function sendText() {
    const text = (ta.value || '').trim();
    if (!text) return;
    ta.value = '';
    try {
      const r = await fetch('/ui/chat/send', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text})});
      const j = await r.json();
      if (j.ok && Array.isArray(j.messages)) {
        for (const m of j.messages) {
          addBubble(m.role, m.text, m.ts);
          if (m.ts > lastTs) lastTs = m.ts;
        }
      }
    } catch (e) {}
  }

  async function loadMode() {
    try {
      const r = await fetch('/ui/modes');
      const j = await r.json();
      if (j.ok) {
        for (const b of modeButtons) {
          b.classList.toggle('active', b.getAttribute('data-mode') === j.mode);
        }
      }
    } catch (e) {}
  }

  function wireModes() {
    for (const b of modeButtons) {
      b.addEventListener('click', async () => {
        try {
          const mode = b.getAttribute('data-mode');
          const r = await fetch('/ui/mode', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({mode})});
          const j = await r.json();
          if (j.ok) {
            for (const bb of modeButtons) bb.classList.toggle('active', bb === b);
            refreshStatus(); // updates provider status
          }
        } catch (e) {}
      });
    }
  }

  async function uploadFile() {
    if (!fileInput.files || !fileInput.files[0]) return;
    const fd = new FormData();
    fd.append('file', fileInput.files[0]);
    try {
      const r = await fetch('/ui/chat/upload', {method:'POST', body: fd});
      const j = await r.json();
      addBubble('system', j.note || (j.ok ? 'Fayl prinyat' : 'Loading error'), (Date.now()/1000));
    } catch (e) {}
  }

  function setPill(elm, ok, text) {
    if (!elm) return;
    elm.classList.remove('ok','warn');
    elm.classList.add(ok ? 'ok' : 'warn');
    elm.textContent = text || (ok ? 'OK' : '—');
  }

  async function refreshStatus() {
    try {
      const r1 = await fetch('/providers/status'); const s1 = await r1.json();
      setPill(stLLM, !!s1.ok, s1.active_provider || '—');
      setPill(stLM, !!s1.lmstudio_probe, s1.lmstudio_probe ? 'dostupen' : 'net');
    } catch (e) {}
    try {
      const r2 = await fetch('/admin/integrations/check'); const s2 = await r2.json();
      const tge = s2.telegram && s2.telegram.enabled ? s2.telegram.bot_token : false;
      setPill(stTG, !!tge, tge ? 'vklyuchen' : '—');
      const wse = s2.whatsapp && s2.whatsapp.access_token ? true : false;
      setPill(stWA, !!wse, wse ? 'nastroen' : '—');
    } catch (e) {}
  }

  btn.addEventListener('click', sendText);
  ta.addEventListener('keydown', (e) => {
    if ((e.key === 'Enter' || e.keyCode === 13) && (e.ctrlKey || e.metaKey)) {
      e.preventDefault(); sendText();
    }
  });
  btnUpload.addEventListener('click', uploadFile);

  wireModes();
  loadMode();
  fetchFeed();
  refreshStatus();
  setInterval(fetchFeed, 2500);
  setInterval(refreshStatus, 10000);
})();
