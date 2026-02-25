(function(){
  const E = id => document.getElementById(id);
  const out = E('out');
  const btn = E('run');

  async function run(){
    btn.disabled = true;
    out.textContent = 'Rabotayu…';
    const url = E('url').value.trim();
    const path = E('path').value.trim();
    const body = {
      meta: E('meta').checked,
      transcript: E('transcript').checked,
      summary: E('summary').checked,
      prefer_audio: E('prefer_audio').checked,
      chunk_ms: parseInt(E('chunk_ms').value||'300000',10)
    };
    let endpoint = '';
    if(url){
      endpoint = '/ingest/video/url';
      body.url = url;
    } else if(path){
      endpoint = '/ingest/video/file';
      body.path = path;
    } else {
      out.textContent = 'You must specify a URL or path.';
      btn.disabled = false;
      return;
    }
    try{
      const r = await fetch(endpoint, {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify(body)
      });
      const j = await r.json();
      out.textContent = JSON.stringify(j, null, 2);
    }catch(e){
      out.textContent = 'Oshibka: '+e;
    }finally{
      btn.disabled = false;
    }
  }

  btn.addEventListener('click', run);
})();
