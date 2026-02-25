(function(){
  const E = id => document.getElementById(id);

  async function doSearch(){
    const q = E('q').value.trim();
    const k = parseInt(E('k').value||'5',10);
    if(!q){ E('out').textContent='Specify your request'; return; }
    const r = await fetch('/search/web',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q,k})});
    const j = await r.json();
    E('out').textContent = JSON.stringify(j,null,2);
  }

  async function doExpand(){
    const q = E('q').value.trim();
    const k = parseInt(E('k').value||'5',10);
    const autofetch = !!E('autofetch').checked;
    const max_fetch = parseInt(E('maxfetch').value||'3',10);
    if(!q){ E('out').textContent='Specify your request'; return; }
    const r = await fetch('/thinking/web_context/expand',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q,k,autofetch,max_fetch})});
    const j = await r.json();
    E('out').textContent = JSON.stringify(j,null,2);
  }

  E('btnSearch').addEventListener('click', doSearch);
  E('btnExpand').addEventListener('click', doExpand);
})();
