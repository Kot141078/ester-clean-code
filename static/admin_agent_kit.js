/* static/admin_agent_kit.js — konsol kita ustoychivogo razvitiya (Sustainability Kit)

Mosty:
- Yavnyy: (UX ↔ Mysli/Kaskad) — dergaem /thinking/act dlya sustainability.kit.* i /thinking/cascade/execute.
- Skrytyy #1: (UX ↔ Avtorizatsiya) — ispolzuem obschiy admin.js (JWT + apiFetch).
- Skrytyy #2: (UX ↔ RuleHub) — pokazyvaem sostoyanie RuleHub cherez suschestvuyuschie ruchki (read-only v etoy vkladke).

Zemnoy abzats:
Odin ekran dlya zelenykh zadach: cheklist → metriki → brif → mini-plan → vypolnenie cherez kaskad. Vse poverkh uzhe suschestvuyuschikh API, bez novykh kontraktov.
c=a+b
*/
(function(){
  const E = id => document.getElementById(id);
  const out = E('out');
  const state = E('state');
  const rulehub = E('rulehub');
  const log = E('log');

  function pjson(v){ return JSON.stringify(v, null, 2); }
  function println(msg){ log.textContent = (log.textContent ? log.textContent+"\n" : "") + msg; }
  async function fetchJSON(path, opts){
    const f = (window.apiFetch || (async (u,o)=>{ const r=await fetch(u, Object.assign({headers:{'Content-Type':'application/json'}}, o||{})); try{return await r.json();}catch(e){return {ok:false,error:'non-json',status:r.status};}}));
    return f(path, opts);
  }

  async function envCheck(){
    try{
      const ab = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'agent.builder.templates.list', args:{}})});
      const rs = await fetch('/rulehub/state').then(r=>r.json()).catch(()=>({ok:false}));
      state.textContent = pjson({ ab: ab ? ab.ab : 'unknown' });
      rulehub.textContent = pjson(rs || {});
      println('✔ Okruzhenie provereno');
    }catch(e){
      println('✖ Oshibka envCheck: '+e);
    }
  }

  async function kitList(){
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'sustainability.kit.list', args:{}})});
    out.textContent = pjson(r);
    const sel = E('checklistId');
    sel.innerHTML = '';
    (r.checklists||[]).forEach(it=>{
      const opt = document.createElement('option');
      opt.value = it.id; opt.textContent = it.id;
      sel.appendChild(opt);
    });
  }

  async function kitGet(){
    const id = E('checklistId').value.trim();
    if(!id){ out.textContent='Ukazhite cheklist'; return; }
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'sustainability.kit.get_checklist', args:{id}})});
    out.textContent = pjson(r);
  }

  async function kitMetrics(){
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'sustainability.kit.metrics.list', args:{}})});
    out.textContent = pjson(r);
  }

  async function composeBrief(){
    const goal = E('goal').value.trim() || 'snizit CO₂e';
    const sector = E('sector').value.trim() || 'SMB';
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'sustainability.kit.compose_brief', args:{goal, sector}})});
    out.textContent = pjson(r);
    if(r && r.brief){ E('brief').value = pjson(r.brief); }
  }

  function buildMiniPlan(){
    // Mini-plan kaskada iz UI s ispolzovaniem brief + vybrannogo cheklista
    let brief = {}; try{ brief = JSON.parse(E('brief').value||'{}'); }catch(e){}
    const checklist = E('checklistId').value.trim();
    const plan = {
      ok: true,
      goal: `Zelenaya zadacha: ${E('goal').value||''} (${E('sector').value||''})`,
      steps: [
        { kind:"reflect.enqueue", endpoint:"/thinking/reflection/enqueue", body:{ item:{ text: E('goal').value||'Eco', meta:{importance:0.6} } } },
        { kind:"mem.passport.append", endpoint:"/thinking/act", body:{ name:"mem.passport.append", args:{ note:`KIT: plan sformirovan (${checklist})`, meta:{ from:"admin_agent_kit", brief }, source:"thinking://sustainability.kit" } } },
        { kind:"self.map", endpoint:"/thinking/act", body:{ name:"self.map", args:{} } }
      ],
      ab: "A"
    };
    E('plan').value = pjson(plan);
    out.textContent = pjson({ok:true, hint:"gotovo k /thinking/cascade/execute", plan});
  }

  async function execPlan(){
    try{
      const plan = JSON.parse(E('plan').value||'{}');
      const r = await fetchJSON('/thinking/cascade/execute', {method:'POST', body: JSON.stringify({plan})});
      out.textContent = pjson(r);
    }catch(e){
      out.textContent = 'Snachala soberite plan';
    }
  }

  window.addEventListener('DOMContentLoaded', ()=>{
    E('btnEnv').addEventListener('click', envCheck);
    E('btnList').addEventListener('click', kitList);
    E('btnGet').addEventListener('click', kitGet);
    E('btnMetrics').addEventListener('click', kitMetrics);
    E('btnBrief').addEventListener('click', composeBrief);
    E('btnBuild').addEventListener('click', buildMiniPlan);
    E('btnExec').addEventListener('click', execPlan);
  });
})();
 // c=a+b
