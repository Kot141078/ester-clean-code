// Simple panel: update healthtn/metrics and event feed/trace/events
(async function () {
  async function fetchJSON(url, opts) {
    try {
      const r = await fetch(url, opts || {});
      const t = await r.text();
      try { return JSON.parse(t); } catch { return { raw: t, status: r.status }; }
    } catch (e) {
      return { error: String(e) };
    }
  }

  async function refreshHealth() {
    const data = await fetchJSON('/health');
    console.log('[health]', data);
  }

  async function refreshTrace() {
    const data = await fetchJSON('/trace/events');
    const box = document.getElementById('trace-box');
    if (!box) return;
    const events = (data && data.events) ? data.events.slice(-50) : [];
    box.innerHTML = '';
    for (const e of events.reverse()) {
      const div = document.createElement('div');
      div.textContent = e;
      div.className = 'trace-item';
      box.appendChild(div);
    }
  }

  setInterval(refreshHealth, 10000);
  setInterval(refreshTrace, 8000);
  refreshHealth();
  refreshTrace();
})();
