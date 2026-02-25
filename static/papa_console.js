(function(){
  const E = id => document.getElementById(id);
  async function POST(url, body){
    const r = await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});
    let j; try{ j = await r.json(); }catch(e){ j = {ok:false,error:'bad json'} }
    return j;
  }
  // Politiki
  E('btnSet').addEventListener('click', async ()=>{
    const priority = parseFloat(E('prio').value||'1');
    const money_bias = parseFloat(E('mb').value||'0.8');
    const task_bias = parseFloat(E('tb').value||'0.9');
    const j = await POST('/policy/papa/set',{priority,money_bias,task_bias});
    E('outPol').textContent = JSON.stringify(j,null,2);
  });
  E('btnArm').addEventListener('click', async ()=>{
    const j = await POST('/policy/papa/pill',{arm:true,ttl_sec:300});
    E('outPol').textContent = JSON.stringify(j,null,2);
  });
  E('btnDisarm').addEventListener('click', async ()=>{
    const j = await POST('/policy/papa/pill',{arm:false});
    E('outPol').textContent = JSON.stringify(j,null,2);
  });
  // Podderzhka
  let lastSha = null;
  E('btnPlan').addEventListener('click', async ()=>{
    const amount_eur = parseFloat(E('amt').value||'0');
    const purpose = E('purpose').value.trim()||'podderzhka';
    const j = await POST('/agency/papa/support/plan',{amount_eur,purpose});
    lastSha = j?.draft?.sha || null;
    E('outTx').textContent = JSON.stringify(j,null,2);
  });
  E('btnExec').addEventListener('click', async ()=>{
    if(!lastSha){ E('outTx').textContent = 'No draft - first “Make a draft”'; return; }
    const j = await POST('/agency/papa/support/execute',{sha:lastSha});
    E('outTx').textContent = JSON.stringify(j,null,2);
  });
})();
// c=a+b
