/* static/admin_activity_to_report.js — avtosvertka aktivnosti v otchet.

Mosty:
- Yavnyy: (UX ↔ Mysli/Deystviya/Kaskad) — activity.report.* i /thinking/cascade/execute.
- Skrytyy #1: (UX ↔ Avtorizatsiya) — obschiy admin.js (JWT + apiFetch) bez izmeneniy.
- Skrytyy #2: (UX ↔ RuleHub) — otobrazhaem sostoyanie RuleHub temi zhe ruchkami (read-only).

Zemnoy abzats:
Okno «nazhmi i poluchi»: skaniruem sobytiya, sobiraem MD, oborachivaem v HTML (cherez report.compose.html) i po razresheniyu sokhranyaem fayly.
c=a+b
*/
(function(){
  const E = id => document.getElementById(id);
  const out = E('out'), state = E('state'), rule = E('rule'), log = E('log');

  function pjson(j){ return JSON.stringify(j, null, 2); }
  function println(x){ log.textContent = (log.textContent?log.textContent+"\n":"") + x; }
  async function fetchJSON(path, opts){
    const f = (window.apiFetch || (async (u,o)=>{ const r=await fetch(u, Object.assign({headers:{'Content-Type':'application/json'}},o||{})); try{return await r.json();}catch(e){return {ok:false,error:'non-json',status:r.status};}}));
    return f(path, opts);
  }

  async function envCheck(){
    const ab  = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'agent.builder.templates.list', args:{}})});
    const rh  = await fetch('/rulehub/state').then(r=>r.json()).catch(()=>({ok:false}));
    state.textContent = pjson({ab: ab ? ab.ab : 'unknown'});
    rule.textContent = pjson(rh || {});
    println('✔ Okruzhenie provereno');
  }

  async function scan(){
    const q = E('q').value.trim();
    const limit = parseInt(E('limit').value||'50',10);
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'agent.activity.scan', args:{q, limit}})});
    out.textContent = pjson(r);
  }

  async function composeMD(){
    const title = E('title').value.trim() || 'Otchet aktivnosti Ester';
    const q = E('q').value.trim();
    const limit = parseInt(E('limit').value||'50',10);
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'activity.report.compose.md', args:{title, q, limit}})});
    E('md').value = (r && r.markdown) ? r.markdown : '';
    out.textContent = pjson({ok:true, md: !!r.markdown, count: r.count});
  }

  async function composeHTML(){
    const title = E('title').value.trim() || 'Otchet aktivnosti Ester';
    const markdown = E('md').value || '# Pusto';
    // Ispolzuem uzhe dobavlennyy report.compose.html dlya obertki (iz paketa-06),
    // no vyzyvaem nash action, kotoryy poprobuet ego zadeystvovat iznutri.
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'activity.report.compose.html', args:{title, markdown}})});
    E('html').value = (r && r.html) ? r.html : '';
    out.textContent = pjson({ok:true, html: !!r.html});
  }

  async function saveFiles(){
    const title = E('title').value.trim() || 'Otchet aktivnosti Ester';
    const markdown = E('md').value || '';
    const html = E('html').value || '';
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'activity.report.save', args:{title, markdown, html}})});
    out.textContent = pjson(r);
  }

  async function planQuick(){
    const title = E('title').value.trim() || 'Sobrat otchet iz aktivnosti';
    const r = await fetchJSON('/thinking/act', {method:'POST', body: JSON.stringify({name:'activity.report.plan.quick', args:{title}})});
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
    E('btnMD').addEventListener('click', composeMD);
    E('btnHTML').addEventListener('click', composeHTML);
    E('btnSave').addEventListener('click', saveFiles);
    E('btnPlan').addEventListener('click', planQuick);
    E('btnExec').addEventListener('click', execPlan);
  });
})();
 // c=a+b
