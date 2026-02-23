(function(){
  const E = id => document.getElementById(id);

  async function search(){
    const q = E('q').value.trim();
    if(!q){ E('out').textContent = 'Vvedite zapros'; return; }
    const dump = E('dump').value.trim();
    const body = { q, k: 8 };
    if(dump) body.scope = { dump };
    const r = await fetch('/video/qa/search', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
    const j = await r.json();
    if(!j.ok){ E('out').textContent = JSON.stringify(j,null,2); return; }
    const items = j.items || [];
    let html = '';
    if(items.length === 0){ html = '<div class="muted">Nichego ne naydeno.</div>'; }
    for(const it of items){
      const meta = it.meta || {};
      const url = meta.url_ts || (meta.src && meta.src.url) || '';
      const start = meta.start != null ? meta.start.toFixed(1) : '';
      const end = meta.end != null ? meta.end.toFixed(1) : '';
      html += `<div class="card">
        <div class="muted">score=${(it.score||0).toFixed(3)} ${start && end ? ` | ${start}s–${end}s` : ''}</div>
        <pre>${(it.text||'').replace(/[<>&]/g, c=>({"<":"&lt;",">":"&gt;","&":"&amp;"}[c]))}</pre>
        ${url ? `<div><a href="${url}" target="_blank">Otkryt v istochnike</a></div>` : ''}
      </div>`;
    }
    E('out').innerHTML = html;
  }

  async function listDumps(){
    const r = await fetch('/video/index/dumps');
    const j = await r.json();
    E('out').textContent = JSON.stringify(j, null, 2);
  }

  E('btnSearch').addEventListener('click', search);
  E('btnList').addEventListener('click', listDumps);
})();
