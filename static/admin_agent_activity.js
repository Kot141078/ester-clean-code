/* static/admin_agent_activity.js — konsol prosmotra aktivnosti Builder/KIT/Report.

Mosty:
- Yavnyy: (UX ↔ Mysli/Kaskad/Pravila) — /thinking/act dlya skanov/statistiki, /thinking/cascade/execute dlya daydzhesta, /rulehub/last dlya sobytiy.
- Skrytyy #1: (UX ↔ Avtorizatsiya) — obschiy admin.js (JWT + apiFetch) bez izmeneniya kontraktov.
- Skrytyy #2: (UX ↔ Memory) — vizualiziruem zametki, izvlechennye iz memory JSON, v odnom okne.

Zemnoy abzats:
Panel «chto proiskhodilo»: za paru klikov uvidet svezhie deystviya Ester, sobrat statistiku i zapustit daydzhest. Nikakikh novykh API — tolko udobnaya vitrina.
c=a+b
*/
(function(){
  const E = id => document.getElementById(id);
  const out = E('out');
  const rule = E('rule');
  const log  = E('log');
  function pjson(j){ return JSON.stringify(j, null, 2); }
  function println(x){ log.textContent = (log.textContent?log.textContent+"\n":"") + x; }

  async function fetchJSON(path, opts){
    const f = (window.apiFetch || (async (u,o)=>{ const r=await fetch(u, Object.assign({headers:{'Content-Type':'application/json'}},o||{})); try{return await r.json();}catch(e){return {ok:false,error:'non-json',status:r.status};}}));
    return f(path, opts);
  }

  async function envCheck(){
    const ab  = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'agent.builder.templates.list', args:{}})});
    const rhl = await fetch('/rulehub/last?limit=50').then(r=>r.json()).catch(()=>({ok:false}));
    E('state').textContent = pjson({ab: ab ? ab.ab : 'unknown'});
    rule.textContent = pjson(rhl||{});
    println('✔ Okruzhenie provereno');
  }

  async function scan(){
    const q = E('q').value.trim();
    const limit = parseInt(E('limit').value||'50',10);
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'agent.activity.scan', args:{q, limit}})});
    out.textContent = pjson(r);
  }

  async function stats(){
    const q = E('q').value.trim();
    const limit = parseInt(E('limit').value||'200',10);
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'agent.activity.stats', args:{q, limit}})});
    out.textContent = pjson(r);
  }

  async function digestPlan(){
    const title = E('title').value.trim() || 'Esther\'s activity digest';
    const q = E('q').value.trim();
    const limit = parseInt(E('limit').value||'40',10);
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'agent.activity.digest.plan', args:{title, q, limit}})});
    E('plan').value = pjson(r.plan || {});
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
    E('btnScan').addEventListener('click', scan);
    E('btnStats').addEventListener('click', stats);
    E('btnDigest').addEventListener('click', digestPlan);
    E('btnExec').addEventListener('click', execPlan);
  });
})();
 // c=a+b
