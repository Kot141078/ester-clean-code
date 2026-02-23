/* static/admin_oneclick_green.js — One-Click Green Agent UI

Mosty:
- Yavnyy: (UX ↔ Mysli/Kaskad) — oneclick.green.* i /thinking/cascade/execute.
- Skrytyy #1: (UX ↔ Avtorizatsiya) — obschiy admin.js (JWT + apiFetch).
- Skrytyy #2: (UX ↔ Pravila) — RuleHub-status pokazyvaetsya read-only na ekrane.

Zemnoy abzats:
Odna knopka: tsel → bundle (spec, plan, fayly, otchet). Po umolchaniyu — prevyu, zapis vklyuchaetsya yavno. Sovmestimo s tekuschimi API.
c=a+b
*/
(function(){
  const E = id => document.getElementById(id);
  const out = E('out'), log = E('log'), state = E('state'), rule = E('rule');
  function pjson(j){ return JSON.stringify(j, null, 2); }
  function println(m){ log.textContent = (log.textContent?log.textContent+"\n":"")+m; }
  async function fetchJSON(path, opts){
    const f = (window.apiFetch || (async (u,o)=>{ const r=await fetch(u, Object.assign({headers:{'Content-Type':'application/json'}},o||{})); try{return await r.json();}catch(e){return {ok:false,error:'non-json',status:r.status};}}));
    return f(path, opts);
  }

  let bundle = null;

  async function envCheck(){
    const ab = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'agent.builder.templates.list', args:{}})});
    const rh = await fetch('/rulehub/state').then(r=>r.json()).catch(()=>({ok:false}));
    state.textContent = pjson({ab: ab ? ab.ab : 'unknown'});
    rule.textContent = pjson(rh || {});
    println('✔ Okruzhenie provereno');
  }

  async function oneClick(){
    const goal = E('goal').value.trim();
    const audience = E('audience').value.trim();
    const domain = E('domain').value.trim() || 'sustainability';
    const name = E('name').value.trim();

    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'oneclick.green.bundle', args:{goal, audience, domain, name}})});
    bundle = r.bundle || null;
    E('bundle').value = pjson(bundle||{});
    out.textContent = pjson({ok: r.ok, ab: r.ab, have_bundle: !!bundle});
  }

  async function execPlan(){
    if(!bundle || !bundle.plan){ out.textContent='Sperva soberite bundle'; return; }
    const r = await fetchJSON('/thinking/cascade/execute', {method:'POST', body: JSON.stringify({plan: bundle.plan})});
    out.textContent = pjson(r);
  }

  async function applyFiles(){
    if(!bundle){ out.textContent='Net bundle'; return; }
    const allow = E('write').checked;
    if(!allow){ out.textContent='Vklyuchite chekboks «Razreshit zapis»'; return; }
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'oneclick.green.apply', args:{bundle}})});
    out.textContent = pjson(r);
  }

  function downloadJSON(){
    if(!bundle){ out.textContent='Net bundle'; return; }
    const blob = new Blob([JSON.stringify(bundle, null, 2)], {type:'application/json'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'oneclick_bundle.json';
    a.click();
    URL.revokeObjectURL(a.href);
  }

  window.addEventListener('DOMContentLoaded', ()=>{
    E('btnEnv').addEventListener('click', envCheck);
    E('btnOne').addEventListener('click', oneClick);
    E('btnPlan').addEventListener('click', execPlan);
    E('btnApply').addEventListener('click', applyFiles);
    E('btnDL').addEventListener('click', downloadJSON);
  });
})();
 // c=a+b
