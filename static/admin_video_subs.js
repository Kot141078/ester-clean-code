(function(){
  const E = id => document.getElementById(id);
  const tbody = E('tbody');
  const out = E('out');

  function row(s){
    const tr = document.createElement('tr');
    const urlq = s.kind === 'ytsearch' ? (s.query||'') : (s.url||'');
    const tags = (s.tags||[]).map(t=>`<span class="pill">${t}</span>`).join(' ');
    tr.innerHTML =
      `<td>${s.id||''}</td>`+
      `<td>${parseInt(s.enabled||0) ? '1' : '0'}</td>`+
      `<td>${s.kind||''}</td>`+
      `<td>${urlq}</td>`+
      `<td>${s.limit||3}</td>`+
      `<td>${tags}</td>`+
      `<td>
        <button data-op="toggle" data-id="${s.id}" class="btn-alt">toggle</button>
        <button data-op="del" data-id="${s.id}" class="btn-danger">del</button>
      </td>`;
    return tr;
  }

  async function reload(){
    try{
      const r = await fetch('/proactive/video/subs');
      const j = await r.json();
      tbody.innerHTML = '';
      (j.subscriptions||[]).forEach(s => tbody.appendChild(row(s)));
    }catch(e){
      out.textContent = 'Loading error:'+e;
    }
  }

  async function save(){
    const body = {
      id: E('id').value.trim(),
      kind: E('kind').value,
      url: E('url').value.trim(),
      query: E('query').value.trim(),
      limit: parseInt(E('limit').value||'3',10),
      tags: E('tags').value.split(',').map(x=>x.trim()).filter(Boolean),
      enabled: E('enabled').checked ? 1 : 0
    };
    if(!body.id){ out.textContent='Need ID'; return; }
    if(body.kind==='ytsearch' && !body.query){ out.textContent='Need cuers for otsearch'; return; }
    if((body.kind==='rss' || body.kind==='direct') && !body.url){ out.textContent='Need URL for rss/direct'; return; }
    try{
      const r = await fetch('/proactive/video/subs', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
      const j = await r.json();
      out.textContent = JSON.stringify(j, null, 2);
      await reload();
    }catch(e){
      out.textContent = 'Saving error:'+e;
    }
  }

  async function onTableClick(ev){
    const btn = ev.target.closest('button[data-op]');
    if(!btn) return;
    const id = btn.getAttribute('data-id');
    const op = btn.getAttribute('data-op');
    if(op==='del'){
      if(!confirm('Udalit '+id+' ?')) return;
      try{
        const r = await fetch('/proactive/video/subs/'+encodeURIComponent(id), {method:'DELETE'});
        const j = await r.json();
        out.textContent = JSON.stringify(j, null, 2);
        await reload();
      }catch(e){
        out.textContent = 'Uninstall error:'+e;
      }
    }else if(op==='toggle'){
      // Get the current record, invert enabled
      try{
        const r0 = await fetch('/proactive/video/subs');
        const j0 = await r0.json();
        const rec = (j0.subscriptions||[]).find(x=>String(x.id)===String(id));
        if(!rec){ out.textContent='Ne naydeno'; return; }
        const newEnabled = rec.enabled ? 0 : 1;
        const r = await fetch('/proactive/video/subs/'+encodeURIComponent(id)+'/toggle', {
          method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({enabled:newEnabled})
        });
        const j = await r.json();
        out.textContent = JSON.stringify(j, null, 2);
        await reload();
      }catch(e){
        out.textContent = 'Toggle error:'+e;
      }
    }
  }

  async function run(){
    try{
      const r = await fetch('/proactive/video/run', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({mode:'subs'})});
      const j = await r.json();
      out.textContent = JSON.stringify(j, null, 2);
    }catch(e){
      out.textContent = 'Startup error:'+e;
    }
  }

  E('save').addEventListener('click', save);
  E('reload').addEventListener('click', reload);
  E('run').addEventListener('click', run);
  tbody.addEventListener('click', onTableClick);
  reload();
})();
