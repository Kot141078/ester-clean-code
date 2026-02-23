(function(){
  const E = id => document.getElementById(id);
  async function POST(url, body){
    const r = await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});
    let j; try{ j = await r.json(); }catch(e){ j = {ok:false,error:'bad json'} }
    return j;
  }

  // SOS
  E('btnPlan').addEventListener('click', async ()=>{
    const situation = E('sit').value.trim();
    const location_hint = E('loc').value.trim();
    const j = await POST('/aid/sos',{situation, location_hint});
    E('outSos').textContent = JSON.stringify(j,null,2);
  });
  E('btnSim').addEventListener('click', async ()=>{
    const situation = E('sit').value.trim();
    const j = await POST('/aid/simulate',{situation, level:'high'});
    E('outSos').textContent = JSON.stringify(j,null,2);
  });
  E('btnTrig').addEventListener('click', async ()=>{
    try{
      const plan = JSON.parse(E('outSos').textContent);
      const j = await POST('/aid/trigger', plan);
      E('outSos').textContent = JSON.stringify(j,null,2);
    }catch(e){
      E('outSos').textContent = 'Snachala sformiruy plan SOS';
    }
  });

  // Kontakty
  E('btnAdd').addEventListener('click', async ()=>{
    const d = {kind:E('k').value.trim(), name:E('nm').value.trim(), channel:E('ch').value.trim(),
               value:E('val').value.trim(), priority: parseInt(E('pr').value||'5',10)};
    const j = await POST('/aid/contacts/add', d);
    const r = await fetch('/aid/contacts'); const s = await r.json();
    E('outContacts').textContent = JSON.stringify({add:j, list:s}, null, 2);
  });

  // Finansy
  E('btnFinStart').addEventListener('click', async ()=>{
    const j = await POST('/aid/fin/discovery/start',{scope:E('scope').value.trim()||'basic'});
    E('outFin').textContent = JSON.stringify(j,null,2);
  });
  E('btnFinStatus').addEventListener('click', async ()=>{
    const r = await fetch('/aid/fin/discovery/status'); const j = await r.json();
    E('outFin').textContent = JSON.stringify(j,null,2);
  });
})();
// c=a+b
