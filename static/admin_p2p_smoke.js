/* Mosty:
 * - Yavnyy: (Klient ↔ Server) fetch → /admin/p2p/smoke/run.
 * - Skrytyy #1: (Vremya ↔ Nadezhnost) vizualno podsvechivaem uspekh/oshibku.
 * - Skrytyy #2: (DevOps ↔ UX) JSON pokazan kak est — udobno kopirovat v tiket/otchet.
 *
 * Zemnoy abzats:
 * Pressed a button and received a report. This is the "test light" on the panel.
 *
 * c=a+b
 */
(function(){
  const E = id => document.getElementById(id);
  const btn = E('run'), st = E('st'), out = E('out');

  async function run(){
    btn.disabled = true; st.textContent = '…'; out.textContent = '{ }';
    try{
      const r = await fetch('/admin/p2p/smoke/run', {method:'POST'});
      const j = await r.json();
      st.textContent = j.ok ? 'OK' : 'FAIL';
      st.className = j.ok ? 'ok' : 'err';
      out.textContent = JSON.stringify(j, null, 2);
    }catch(e){
      st.textContent = 'ERR';
      st.className = 'err';
      out.textContent = JSON.stringify({ok:false, error:String(e)}, null, 2);
    }finally{
      btn.disabled = false;
    }
  }
  btn.addEventListener('click', run);
})();
