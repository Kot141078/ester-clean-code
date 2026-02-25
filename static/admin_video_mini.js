// static/admin_video_mini.zhs ​​- mini-remote: indexing the latest + self-check.
// Mosty:
// - Explicit: (XH ↔ Search) button for the elevator “dumps → vector index”.
// - Skrytyy #1: (Nablyudaemost ↔ Ekspluatatsiya) bystryy self-check iz brauzera.
// - Skrytyy #2: (Kibernetika ↔ Nagruzka) limit mozhno podpravit zdes zhe pri neobkhodimosti.
//
// Terrestrial paragraph: a small remote control at the warehouse door - he pulled the lever, and the boxes went upstairs.
//
// c=a+b
(function(){
  const E = id => document.getElementById(id);
  const out = E('out');
  const state = E('state');

  async function refreshState(){
    try{
      const r = await fetch('/ingest/video/index/state');
      const j = await r.json();
      state.textContent = JSON.stringify(j, null, 2);
    }catch(e){
      state.textContent = 'Oshibka: '+e;
    }
  }

  async function runIndex(){
    try{
      out.textContent = 'Rabotayu…';
      const r = await fetch('/ingest/video/index/recent', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({limit: 20, prefer_summary: true})
      });
      const j = await r.json();
      out.textContent = JSON.stringify(j, null, 2);
      await refreshState();
    }catch(e){
      out.textContent = 'Oshibka: '+e;
    }
  }

  async function runHealth(){
    try{
      const r = await fetch('/health/video/selfcheck');
      const j = await r.json();
      out.textContent = JSON.stringify(j, null, 2);
    }catch(e){
      out.textContent = 'Oshibka: '+e;
    }
  }

  E('run_index').addEventListener('click', runIndex);
  E('health').addEventListener('click', runHealth);
  refreshState();
})();
