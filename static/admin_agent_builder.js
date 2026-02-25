/* static/admin_agent_builder.zhs - mini-remote for internal Agent Builder.

Mosty:
- Yavnyy: (UX ↔ Mysli/Kaskad) knopki vyzyvayut /thinking/act i /thinking/cascade/*.
- Skrytyy #1: (UX ↔ Pravila) daem bystryy dostup k chteniyu/primeneniyu YAML dlya RuleHub (cherez suschestvuyuschie ruchki).
- Skrytyy #2: (UX ↔ Avtorizatsiya) pereispolzuem admin.js: JWT + apiFetch.

Zemnoy abzats:
Odna stranitsa: zadal tsel → poluchil opisanie → sgeneriroval plan → prevyu faylov → (po razresheniyu) primenil. Nikakikh novykh kontraktov, tolko udobnye knopki dlya togo, chto u Ester uzhe est.
c=a+b
*/
(function(){
  const E = id => document.getElementById(id);
  const log = E('log');
  const ab = { slot: 'unknown', write: false };

  function pjson(j){ return JSON.stringify(j, null, 2); }
  function println(msg){ log.textContent = (log.textContent ? log.textContent + "\n" : "") + msg; }
  async function fetchJSON(path, opts){ 
    const f = (window.apiFetch || (async (u,o)=>{ const r=await fetch(u, Object.assign({headers:{'Content-Type':'application/json'}},o||{})); try{return await r.json();}catch(e){return {ok:false,error:'non-json',status:r.status};}}));
    return f(path, opts);
  }

  async function envCheck(){
    // Uznaem A/B-slot + dostupnost rulehub
    const r1 = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'agent.builder.templates.list', args:{}})});
    const r2 = await fetchJSON('/rulehub/state');
    ab.slot = (r1 && r1.ab) || 'unknown';
    ab.write = false; // the client does not see ENV, displays hints
    E('abState').textContent = `AB-slot: ${ab.slot} (zapis razreshaetsya cherez ENV na servere)`;
    E('rulehubState').textContent = pjson(r2||{});
    println('✔ Okruzhenie asked.');
  }

  async function listTemplates(){
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'agent.builder.templates.list', args:{}})});
    E('out').textContent = pjson(r);
  }

  async function describeAgent(){
    const goal = E('goal').value.trim();
    const audience = E('audience').value.trim();
    const domain = E('domain').value.trim() || 'any';
    const name = E('name').value.trim();
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'agent.builder.describe', args:{goal,audience,domain,name}})});
    E('out').textContent = pjson(r);
    if(r && r.spec){ E('spec').value = pjson(r.spec); }
  }

  async function generatePlan(){
    const goal = E('goal').value.trim() || 'sobrat agenta';
    const note = 'from admin_agent_builder.js';
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'agent.builder.plan.generate', args:{goal, note}})});
    E('out').textContent = pjson(r);
    if(r && r.plan){ E('plan').value = pjson(r.plan); }
  }

  async function executePlan(){
    try{
      const plan = JSON.parse(E('plan').value);
      const r = await fetchJSON('/thinking/cascade/execute', {method:'POST', body: JSON.stringify({plan})});
      E('out').textContent = pjson(r);
    }catch(e){
      E('out').textContent = 'Snachala sformiruy plan.';
    }
  }

  async function scaffoldFiles(){
    let spec = {};
    try{ spec = JSON.parse(E('spec').value || '{}'); }catch(e){ E('out').textContent='Nekorrektnyy JSON v spec'; return; }
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'agent.builder.scaffold.files', args:{spec}})});
    E('out').textContent = pjson(r);
  }

  async function applyFiles(){
    let spec = {};
    try{ spec = JSON.parse(E('spec').value || '{}'); }catch(e){ E('out').textContent='Nekorrektnyy JSON v spec'; return; }
    const preview_only = !E('applyWrite').checked;
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'agent.builder.apply', args:{spec, preview_only}})});
    E('out').textContent = pjson(r);
  }

  // RuleHub helpers (ne menyaem kontraktov)
  async function loadRuleHubCfg(){
    const r = await fetch('/rulehub/config');
    try{ const j = await r.json(); E('rulehubCfg').value = j.yaml || ''; }catch(e){ E('rulehubCfg').value = 'YML reading error'; }
  }
  async function saveRuleHubCfg(){
    const yaml = E('rulehubCfg').value;
    const r = await fetchJSON('/rulehub/config', {method:'POST', body: JSON.stringify({yaml})});
    E('out').textContent = pjson(r);
  }

  window.addEventListener('DOMContentLoaded', ()=>{
    E('btnEnv').addEventListener('click', envCheck);
    E('btnList').addEventListener('click', listTemplates);
    E('btnDesc').addEventListener('click', describeAgent);
    E('btnPlan').addEventListener('click', generatePlan);
    E('btnExec').addEventListener('click', executePlan);
    E('btnFiles').addEventListener('click', scaffoldFiles);
    E('btnApply').addEventListener('click', applyFiles);
    E('btnRuleGet').addEventListener('click', loadRuleHubCfg);
    E('btnRuleSet').addEventListener('click', saveRuleHubCfg);
  });
})();
 // c=a+b
