(function(){
  function getJwt(){ return localStorage.getItem('ester.jwt') || ''; }
  function setJwt(v){ if(v){ localStorage.setItem('ester.jwt', v); } else { localStorage.removeItem('ester.jwt'); } }

  async function apiFetch(path, opts){
    opts = opts || {};
    opts.headers = opts.headers || { 'Content-Type': 'application/json' };
    const jwt = getJwt();
    if(jwt){ opts.headers['Authorization'] = 'Bearer ' + jwt; }
    const res = await fetch(path, opts);
    let data = null;
    try { data = await res.json(); } catch(e){ data = { ok:false, error:'non-json', status: res.status }; }
    if(!res.ok){
      return Object.assign({ ok:false, status: res.status }, data);
    }
    return data;
  }

  window.apiFetch = apiFetch;

  // JWT box bindings
  window.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('jwtInput');
    const saveBtn = document.getElementById('saveJwtBtn');
    const clearBtn = document.getElementById('clearJwtBtn');
    if(input){ input.value = getJwt(); }
    if(saveBtn){ saveBtn.onclick = () => setJwt(document.getElementById('jwtInput').value.trim()); }
    if(clearBtn){ clearBtn.onclick = () => { setJwt(''); if(input) input.value=''; }; }
  });
})();
