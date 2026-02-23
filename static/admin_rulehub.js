(function(){
  const E = id => document.getElementById(id);
  const tbody = E('tbody');
  const state = E('state');
  const cfg = E('cfg');
  const cfg_out = E('cfg_out');

  function tr(ev){
    const tr = document.createElement('tr');
    tr.innerHTML =
      `<td>${ev.ts||''}</td>`+
      `<td><span class="pill">${ev.status||''}</span></td>`+
      `<td>${(ev.actions||[]).join(', ')}</td>`+
      `<td>${ev.duration_ms||0}</td>`+
      `<td class="muted">${ev.error ? ('err: '+ev.error) : (ev.result_hint||'')}</td>`;
    return tr;
  }

  async function loadState(){
    try{
      const r = await fetch('/rulehub/state');
      const j = await r.json();
      state.textContent = JSON.stringify(j, null, 2);
    }catch(e){
      state.textContent = 'Oshibka: '+e;
    }
  }

  async function loadEvents(){
    try{
      const r = await fetch('/rulehub/last?limit=100');
      const j = await r.json();
      tbody.innerHTML = '';
      (j.events||[]).reverse().forEach(ev => tbody.appendChild(tr(ev)));
    }catch(e){
      tbody.innerHTML = '<tr><td colspan="5">Oshibka zagruzki</td></tr>';
    }
  }

  async function toggle(){
    try{
      const cur = await (await fetch('/rulehub/state')).json();
      const newEnabled = cur.enabled ? 0 : 1;
      const r = await fetch('/rulehub/toggle', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({enabled:newEnabled})});
      const j = await r.json();
      state.textContent = JSON.stringify(j, null, 2);
      await loadState();
    }catch(e){
      state.textContent = 'Oshibka toggle: '+e;
    }
  }

  async function loadCfg(){
    try{
      const r = await fetch('/rulehub/config');
      const j = await r.json();
      cfg.value = j.yaml || '';
    }catch(e){
      cfg_out.textContent = 'Oshibka zagruzki YAML: '+e;
    }
  }

  async function saveCfg(){
    try{
      const r = await fetch('/rulehub/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({yaml: cfg.value})});
      const j = await r.json();
      cfg_out.textContent = JSON.stringify(j, null, 2);
    }catch(e){
      cfg_out.textContent = 'Oshibka sokhraneniya YAML: '+e;
    }
  }

  E('reload').addEventListener('click', loadEvents);
  E('toggle').addEventListener('click', toggle);
  E('load_cfg').addEventListener('click', loadCfg);
  E('save_cfg').addEventListener('click', saveCfg);
  loadState();
  loadEvents();
})();
