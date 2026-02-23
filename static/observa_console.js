(function(){
  const E = id => document.getElementById(id);
  E('btnHealth').addEventListener('click', async ()=>{
    const j = await (await fetch('/healthz')).json();
    E('out').textContent = JSON.stringify(j,null,2);
  });
  E('btnMetrics').addEventListener('click', async ()=>{
    const t = await (await fetch('/metrics')).text();
    E('out').textContent = t;
  });
})();
 // c=a+b
