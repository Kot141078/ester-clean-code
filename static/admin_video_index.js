(function(){
  const E = id => document.getElementById(id);

  async function build(){
    const v = E('src').value.trim();
    if(!v){ E('out').textContent='Ukazhi dump (rep_*.json) ili URL/put video'; return; }
    if(v.startsWith('http') || (!v.endsWith('.json') && !v.includes('rep_'))){
      // from_source
      const body = v.startsWith('http') ? {url:v} : {path:v};
      const r = await fetch('/video/index/from_source', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
      const j = await r.json();
      E('out').textContent = JSON.stringify(j, null, 2);
    }else{
      const r = await fetch('/video/index/build', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({dump:v})});
      const j = await r.json();
      E('out').textContent = JSON.stringify(j, null, 2);
    }
  }

  async function chapters(){
    const v = E('src').value.trim();
    if(!v){ E('out').textContent='Ukazhi dump (rep_*.json)'; return; }
    const u = '/video/index/chapters?dump='+encodeURIComponent(v);
    const r = await fetch(u);
    const j = await r.json();
    E('out').textContent = JSON.stringify(j, null, 2);
  }

  async function summarize(){
    const v = E('src').value.trim();
    if(!v){ E('out').textContent='Ukazhi dump (rep_*.json)'; return; }
    const body = {dump:v, start:60, end:180, max_chars:700};
    const r = await fetch('/video/index/summarize_window', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
    const j = await r.json();
    E('out').textContent = JSON.stringify(j, null, 2);
  }

  async function list(){
    const r = await fetch('/video/index/dumps');
    const j = await r.json();
    E('list').textContent = JSON.stringify(j, null, 2);
  }

  E('btnBuild').addEventListener('click', build);
  E('btnChapters').addEventListener('click', chapters);
  E('btnSum').addEventListener('click', summarize);
  E('btnList').addEventListener('click', list);
  list();
})();
