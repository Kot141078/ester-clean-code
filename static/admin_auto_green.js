/* static/admin_auto_green.js — konsol avtonomnykh zelenykh tseley

Mosty:
- Yavnyy: (UX ↔ Mysli/Kaskad) — autonomy.green.* cherez /thinking/act i zapusk plana cherez /thinking/cascade/execute.
- Skrytyy #1: (UX ↔ Avtorizatsiya) — obschiy admin.js (JWT + apiFetch).
- Skrytyy #2: (UX ↔ Builder/Kit/Report) — plan ispolzuet uzhe suschestvuyuschie deystviya agent.builder.*, sustainability.kit.*, report.*.

Zemnoy abzats:
Odin ekran, gde Ester sama predlagaet tseli i sobiraet plan, a vy reshaete — zapuskat li ego. Kontrakty API prezhnie, fonovykh demonov net.
c=a+b
*/
(function(){
  const E = id => document.getElementById(id);
  const out = E('out'), log = E('log'), state = E('state');
  function pjson(j){ return JSON.stringify(j, null, 2); }
  function println(x){ log.textContent = (log.textContent?log.textContent+"\n":"") + x; }
  async function fetchJSON(path, opts){
    const f = (window.apiFetch || (async (u,o)=>{ const r=await fetch(u, Object.assign({headers:{'Content-Type':'application/json'}},o||{})); try{return await r.json();}catch(e){return {ok:false,error:'non-json',status:r.status};}}));
    return f(path, opts);
  }

  async function envCheck(){
    const ab  = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'agent.builder.templates.list', args:{}})});
    const auto = { var: 'ESTER_AUTONOMY_GREEN', active: false };
    try{ auto.active = !!parseInt((await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'autonomy.green.suggest_goals', args:{max_goals:1}})})).auto?1:0,10); }catch(e){}
    state.textContent = pjson({ab: ab ? ab.ab : 'unknown', autonomy_green: auto});
    println('✔ Okruzhenie provereno');
  }

  async function suggest(){
    const max_goals = parseInt(E('maxn').value||'1',10);
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'autonomy.green.suggest_goals', args:{max_goals}})});
    E('goals').value = pjson(r.goals || []);
    out.textContent = pjson(r);
  }

  async function plan(){
    const max_goals = parseInt(E('maxn').value||'1',10);
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'autonomy.green.plan', args:{max_goals}})});
    E('plan').value = pjson(r.plan || {});
    out.textContent = pjson({ok:true, have_plan: !!r.plan});
  }

  async function planBatch(){
    let goals=[]; try{ goals = JSON.parse(E('goals').value||'[]'); }catch(e){}
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'autonomy.green.batch.plan', args:{goals}})});
    E('plan').value = pjson(r.plan || {});
    out.textContent = pjson({ok:true, have_plan: !!r.plan});
  }

  async function execPlan(){
    try{
      const plan = JSON.parse(E('plan').value||'{}');
      const r = await fetchJSON('/thinking/cascade/execute', {method:'POST', body: JSON.stringify({plan})});
      out.textContent = pjson(r);
    }catch(e){
      out.textContent = 'Snachala sformiruyte plan';
    }
  }

  window.addEventListener('DOMContentLoaded', ()=>{
    E('btnEnv').addEventListener('click', envCheck);
    E('btnSuggest').addEventListener('click', suggest);
    E('btnPlan').addEventListener('click', plan);
    E('btnPlanBatch').addEventListener('click', planBatch);
    E('btnExec').addEventListener('click', execPlan);
  });
})();
 // c=a+b
