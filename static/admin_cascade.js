(function(){
  const E = id => document.getElementById(id);
  async function post(url, body){
    const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body||{})});
    return r.json();
  }
  E('btnPlan').addEventListener('click', async ()=>{
    const goal = E('goal').value.trim();
    if(!goal){ E('out').textContent='Specify a goal'; return; }
    const j = await post('/thinking/cascade/plan', {goal});
    E('out').textContent = JSON.stringify(j, null, 2);
  });
  E('btnExec').addEventListener('click', async ()=>{
    try{
      const plan = JSON.parse(E('out').textContent);
      const j = await post('/thinking/cascade/execute', {plan});
      E('out').textContent = JSON.stringify(j, null, 2);
    }catch(e){
      E('out').textContent = 'First get a plan (Plan button).';
    }
  });
})();
// c=a+b
