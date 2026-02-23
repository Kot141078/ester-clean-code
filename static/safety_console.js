(function(){
  const E = id => document.getElementById(id);
  async function POST(url, body){
    const r = await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});
    let j; try{ j = await r.json(); }catch(e){ j = {ok:false,error:'bad json'} }
    return j;
  }
  E('btnSet').addEventListener('click', async ()=>{
    const enabled = parseInt(E('enabled').value||'1',10) ? 1 : 0;
    const risk_tolerance = parseFloat(E('tol').value||'0.25');
    const j = await POST('/policy/caution/set',{enabled, risk_tolerance});
    E('out').textContent = JSON.stringify(j,null,2);
  });
  E('btnArm').addEventListener('click', async ()=>{
    const j = await POST('/policy/caution/pill',{arm:true, ttl_sec:300});
    E('out').textContent = JSON.stringify(j,null,2);
  });
  E('btnDisarm').addEventListener('click', async ()=>{
    const j = await POST('/policy/caution/pill',{arm:false});
    E('out').textContent = JSON.stringify(j,null,2);
  });
})();
// c=a+b
