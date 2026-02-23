(function(){
  const E = id => document.getElementById(id);
  async function POST(url, body){
    const r = await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});
    let j; try{ j = await r.json(); }catch(e){ j = {ok:false,error:'bad json'} }
    return j;
  }
  let lastId = null;
  E('btnIngest').addEventListener('click', async ()=>{
    const text = E('qtext').value||'';
    const path = E('qpath').value||'extensions/enabled/hello.txt';
    const content_b64 = btoa(unescape(encodeURIComponent(text)));
    const j = await POST('/quarantine/ingest',{path, content_b64});
    lastId = j.id || null;
    E('out').textContent = JSON.stringify(j,null,2);
  });
  E('btnScan').addEventListener('click', async ()=>{
    if(!lastId){ E('out').textContent='Snachala Ingest'; return; }
    const j = await POST('/quarantine/scan',{id:lastId});
    E('out').textContent = JSON.stringify(j,null,2);
  });
  E('btnRelease').addEventListener('click', async ()=>{
    if(!lastId){ E('out').textContent='Snachala Ingest'; return; }
    const j = await POST('/quarantine/release',{id:lastId, dest_path:E('qpath').value||'extensions/enabled/hello.txt', reason:'ui'});
    E('out').textContent = JSON.stringify(j,null,2);
  });
})();
 // c=a+b
