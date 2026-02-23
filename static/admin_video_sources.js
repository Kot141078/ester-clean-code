(function(){
  const E = id => document.getElementById(id);
  async function loadCaps(){
    try{
      const r = await fetch('/metrics/video_ex');
      const t = await r.text();
      const lines = t.trim().split('\n').map(s => s.trim());
      const obj = {};
      lines.forEach(s => { const [k,v] = s.split(/\s+/); obj[k]=v; });
      E('caps').textContent = JSON.stringify(obj, null, 2);
    }catch(e){
      E('caps').textContent = 'Oshibka: '+e;
    }
  }
  async function probe(){
    const v = E('url').value.trim();
    if(!v){ E('out').textContent='Vvedite URL ili put'; return; }
    const u = v.startsWith('http') ? '/ingest/video/universal/probe?url='+encodeURIComponent(v)
                                   : '/ingest/video/universal/probe?path='+encodeURIComponent(v);
    const r = await fetch(u);
    const j = await r.json();
    E('out').textContent = JSON.stringify(j, null, 2);
  }
  async function fetchDo(){
    const v = E('url').value.trim();
    if(!v){ E('out').textContent='Vvedite URL ili put'; return; }
    const body = v.startsWith('http') ? {url:v, want:{subs:true, summary:true, meta:true}}
                                      : {path:v, want:{subs:true, summary:true, meta:true}};
    const r = await fetch('/ingest/video/universal/fetch', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
    const j = await r.json();
    E('out').textContent = JSON.stringify(j, null, 2);
  }
  E('btnProbe').addEventListener('click', probe);
  E('btnFetch').addEventListener('click', fetchDo);
  loadCaps();
})();
