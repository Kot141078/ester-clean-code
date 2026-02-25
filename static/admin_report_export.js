/* static/admin_report_export.js — konsol eksporta otchetov (MD/HTML)

Mosty:
- Yavnyy: (UX ↔ Mysli/Deystviya) — report.compose.*, report.save.files cherez /thinking/act.
- Skrytyy #1: (UX ↔ Kaskad) — formiruem i otpravlyaem mini-plan v /thinking/cascade/execute (kak v admin_cascade.js).
- Skrytyy #2: (UX ↔ Avtorizatsiya/RuleHub) — obschiy JWT i chtenie sostoyaniya RuleHub, bez izmeneniya kontraktov.

Zemnoy abzats:
Polzovatel sobiraet otchet iz brifa/cheklista/metrik, smotrit prevyu i po razresheniyu sokhranyaet fayly. Vse rabotaet «iz korobki», API prezhnie.
c=a+b
*/
(function(){
  const E = id => document.getElementById(id);
  const out = E('out');
  const log = E('log'); const state = E('state'); const rulehub = E('rulehub');

  function pjson(j){ return JSON.stringify(j, null, 2); }
  function println(x){ log.textContent = (log.textContent?log.textContent+"\n":"") + x; }
  async function fetchJSON(path, opts){
    const f = (window.apiFetch || (async (u,o)=>{ const r=await fetch(u, Object.assign({headers:{'Content-Type':'application/json'}},o||{})); try{return await r.json();}catch(e){return {ok:false,error:'non-json',status:r.status};}}));
    return f(path, opts);
  }

  async function envCheck(){
    const ab = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'agent.builder.templates.list', args:{}})});
    const rs = await fetch('/rulehub/state').then(r=>r.json()).catch(()=>({ok:false}));
    state.textContent = pjson({ab: ab ? ab.ab : 'unknown'});
    rulehub.textContent = pjson(rs || {});
    println('✔ Okruzhenie provereno');
  }

  async function kitList(){
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'sustainability.kit.list', args:{}})});
    const sel = E('checklistId'); sel.innerHTML = '';
    (r.checklists||[]).forEach(it=>{ const o=document.createElement('option'); o.value=it.id; o.textContent=it.id; sel.appendChild(o); });
    out.textContent = pjson(r);
  }
  async function kitGet(){
    const id = E('checklistId').value.trim(); if(!id){ out.textContent='Vyberite cheklist'; return; }
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'sustainability.kit.get_checklist', args:{id}})});
    E('checklistMd').value = (r && r.markdown) ? r.markdown : '';
    out.textContent = pjson({ok:true, got:id});
  }
  async function briefGet(){
    const goal = E('goal').value.trim() || 'snizit CO₂e';
    const sector = 'SMB';
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'sustainability.kit.compose_brief', args:{goal, sector}})});
    E('brief').value = pjson(r.brief || {});
    const m = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'sustainability.kit.metrics.list', args:{}})});
    E('metrics').value = pjson(m.data || {});
    out.textContent = pjson({ok:true, brief: !!r.brief, metrics: !!m.data});
  }

  async function buildMD(){
    let brief={}, metrics={};
    try{ brief = JSON.parse(E('brief').value||'{}'); }catch(e){}
    try{ metrics = JSON.parse(E('metrics').value||'{}'); }catch(e){}
    const title = E('title').value.trim() || 'Otchet';
    const goal  = E('goal').value.trim();
    const checklist_md = E('checklistMd').value || '';
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'report.compose.md', args:{title, goal, brief, checklist_md, metrics}})});
    E('md').value = (r && r.markdown) ? r.markdown : '';
    out.textContent = pjson(r);
  }

  async function buildHTML(){
    const title = E('title').value.trim() || 'Otchet';
    const markdown = E('md').value || '# (pusto)';
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'report.compose.html', args:{title, markdown}})});
    E('html').value = (r && r.html) ? r.html : '';
    out.textContent = pjson({ok:true, html: !!r.html});
  }

  async function saveFiles(){
    const title = E('title').value.trim() || 'Otchet';
    const markdown = E('md').value || '';
    const html = E('html').value || '';
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'report.save.files', args:{title, markdown, html}})});
    out.textContent = pjson(r);
  }

  async function planQ(){
    const goal = 'Prepare a report (mini-plan)';
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'report.plan.quick', args:{goal}})});
    E('plan').value = pjson(r.plan || {});
  }
  async function execPlan(){
    try{
      const plan = JSON.parse(E('plan').value||'{}');
      const r = await fetchJSON('/thinking/cascade/execute', {method:'POST', body: JSON.stringify({plan})});
      out.textContent = pjson(r);
    }catch(e){ out.textContent='Snachala sformiruyte plan'; }
  }

  window.addEventListener('DOMContentLoaded', ()=>{
    E('btnEnv').addEventListener('click', envCheck);
    E('btnList').addEventListener('click', kitList);
    E('btnGet').addEventListener('click', kitGet);
    E('btnBrief').addEventListener('click', briefGet);
    E('btnMD').addEventListener('click', buildMD);
    E('btnHTML').addEventListener('click', buildHTML);
    E('btnSave').addEventListener('click', saveFiles);
    E('btnPlan').addEventListener('click', planQ);
    E('btnExec').addEventListener('click', execPlan);
  });
})();
 // c=a+b
