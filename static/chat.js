(function () {
  const elLog = () => document.getElementById('chat-log');
  const elInput = () => document.getElementById('chat-input');
  const elSend = () => document.getElementById('chat-send');
  const elProv = () => document.getElementById('chat-provider');

  const state = {
    sid: localStorage.getItem('ester_sid') || 'default',
    provider: localStorage.getItem('ester_provider') || 'auto',
  };

  function setProvider(v) {
    state.provider = v || 'auto';
    localStorage.setItem('ester_provider', state.provider);
  }

  function addBubble(text, who) {
    const wrap = document.createElement('div');
    wrap.style.margin = '6px 0';
    wrap.style.display = 'flex';
    wrap.style.justifyContent = who === 'you' ? 'flex-end' : 'flex-start';

    const b = document.createElement('div');
    b.textContent = text;
    b.style.maxWidth = '72%';
    b.style.whiteSpace = 'pre-wrap';
    b.style.padding = '8px 10px';
    b.style.borderRadius = '12px';
    b.style.border = '1px solid var(--border,#333)';
    b.style.background = who === 'you' ? 'rgba(255,255,255,.07)' : 'rgba(0,0,0,.07)';
    wrap.appendChild(b);

    elLog().appendChild(wrap);
    elLog().scrollTop = elLog().scrollHeight;
  }

  async function loadHistory() {
    try {
      const r = await fetch('/chat/history', { method: 'GET' });
      if (!r.ok) return;
      const data = await r.json();
      elLog().innerHTML = ''; // clear placeholder
      (data.history || []).forEach(item => {
        addBubble(item.user || item.input || item.prompt || '', 'you');
        addBubble(item.assistant || item.output || item.answer || '', 'ai');
      });
    } catch (e) {
      // noop
    }
  }

  async function sendMessage(text) {
    const body = {
      message: text,
      sid: state.sid,
    };
    // tolko esli yavno vybran provayder, krome auto
    if (state.provider && state.provider !== 'auto') body.mode = state.provider;

    const r = await fetch('/chat/message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (r.status === 204) {
      return { ok: false, answer: '(pustoy otvet, 204)' };
    }

    const data = await r.json().catch(() => ({}));
    if (data.sid) {
      state.sid = data.sid;
      localStorage.setItem('ester_sid', state.sid);
    }
    return data;
  }

  function wire() {
    // ustanovit selekt provaydera
    elProv().value = state.provider;
    elProv().addEventListener('change', e => setProvider(e.target.value));

    async function handleSend() {
      const text = (elInput().value || '').trim();
      if (!text) return;
      elInput().value = '';
      addBubble(text, 'you');
      const res = await sendMessage(text);
      addBubble(res.answer || '(net otveta)', 'ai');
    }

    elSend().addEventListener('click', handleSend);
    elInput().addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    });

    loadHistory();
  }

  // zapusk kogda DOM gotov
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wire);
  } else {
    wire();
  }
})();
