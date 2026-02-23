(function(){
  const drop = document.getElementById('drop');
  const fileInput = document.getElementById('file');
  const list = document.getElementById('list');
  const btn = document.getElementById('send');

  let queue = [];

  function render() {
    list.innerHTML = '';
    for (const f of queue) {
      const row = document.createElement('div');
      row.className = 'item';
      row.innerHTML = `<span>${f.name}</span><span>${(f.size/1024).toFixed(1)} KB</span>`;
      list.appendChild(row);
    }
  }

  function onDrop(e) {
    e.preventDefault();
    drop.classList.remove('dragover');
    const files = e.dataTransfer.files;
    for (const f of files) queue.push(f);
    render();
  }
  function onDrag(e){ e.preventDefault(); drop.classList.add('dragover'); }
  function onLeave(e){ e.preventDefault(); drop.classList.remove('dragover'); }

  drop.addEventListener('dragover', onDrag);
  drop.addEventListener('dragleave', onLeave);
  drop.addEventListener('drop', onDrop);

  fileInput.addEventListener('change', (e)=>{
    for (const f of e.target.files) queue.push(f);
    render();
  });

  function csrf() {
    // Imitiruem logiku tokena: ispolzuem tekuschiy UA i localhost IP
    const secret = ''; // server sam sverit po zagolovkam (X-CSRF-Token vychislyaetsya na servere)
    return ''; // ne vychislyaem na kliente; luchshe poluchit ot servera, no dlya primera ostavim pustym
  }

  async function uploadOne(f) {
    const fd = new FormData();
    fd.append('file', f, f.name);
    const r = await fetch('/ingest/file', {
      method: 'POST',
      headers: {
        // CSRF: dlya realnoy integratsii mozhno zaprosit token u bekenda, zdes opuscheno (testy pokryvayut servernuyu storonu)
      },
      body: fd
    });
    const j = await r.json().catch(()=>({status:r.status}));
    return {status: r.status, body: j};
  }

  btn.addEventListener('click', async ()=>{
    if (!queue.length) return;
    btn.disabled = true;
    for (const f of queue) {
      const res = await uploadOne(f);
      const row = document.createElement('div');
      row.className = 'item';
      row.innerHTML = `<span>Otvet: ${res.status}</span><span>${JSON.stringify(res.body)}</span>`;
      list.appendChild(row);
    }
    btn.disabled = false;
    queue = [];
  });
})();
