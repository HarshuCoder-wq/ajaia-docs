(() => {
  const doc = window.DOC;
  const canEdit = doc.role === 'owner' || doc.role === 'editor';
  const statusEl = document.getElementById('status');
  const titleEl = document.getElementById('title');
  const conflictEl = document.getElementById('conflict');

  const quill = new Quill('#editor', {
    theme: 'snow',
    readOnly: !canEdit,
    placeholder: canEdit ? 'Start writing…' : '',
    modules: {
      toolbar: canEdit ? [
        [{ header: [1, 2, 3, false] }],
        ['bold', 'italic', 'underline', 'strike'],
        [{ list: 'ordered' }, { list: 'bullet' }, { indent: '-1' }, { indent: '+1' }],
        [{ align: [] }],
        ['blockquote', 'link'],
        ['clean'],
      ] : false,
    },
  });

  function loadContent(html) {
    // Going through the clipboard converter means imported HTML (plain <ul>, etc.)
    // is normalised into Quill's model the same way a paste would be.
    quill.setContents(quill.clipboard.convert({ html: html || '' }), 'silent');
  }
  loadContent(doc.content);

  // ------------------------------------------------------------ saving
  // One save in flight at a time; edits made meanwhile are merged into the next save.
  let version = doc.version;
  let pending = {};
  let inFlight = false;
  let timer = null;
  let blocked = false; // true while a conflict is unresolved

  function setStatus(text, cls = '') {
    statusEl.textContent = text;
    statusEl.className = 'save-status small ' + (cls || 'muted');
  }

  function queue(fields, delay = 800) {
    if (!canEdit) return;
    Object.assign(pending, fields);
    setStatus('Unsaved changes…');
    clearTimeout(timer);
    timer = setTimeout(flush, delay);
  }

  async function flush(force = false) {
    clearTimeout(timer);
    if (inFlight || blocked && !force || !Object.keys(pending).length) return;
    const body = { ...pending, version };
    pending = {};
    inFlight = true;
    setStatus('Saving…');
    try {
      const res = await fetch(`/api/documents/${doc.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        version = data.version;
        document.title = `${data.title} · Ajaia Docs`;
        setStatus('All changes saved');
      } else if (res.status === 409) {
        // Put our edits back and let the user choose.
        pending = { ...body, ...pending };
        delete pending.version;
        blocked = true;
        conflictEl.hidden = false;
        conflictEl._latest = data.current;
        setStatus('Not saved — conflict', 'error-text');
      } else if (res.status === 401) {
        pending = { ...body, ...pending };
        delete pending.version;
        setStatus('Session expired — sign in again to save', 'error-text');
      } else {
        setStatus(data.error || 'Save failed', 'error-text');
        if ('title' in body) titleEl.value = titleEl.dataset.last || titleEl.value;
      }
    } catch (e) {
      // Network blip: keep the edits and retry.
      pending = { ...body, ...pending };
      delete pending.version;
      setStatus('Offline — retrying…', 'error-text');
      timer = setTimeout(flush, 3000);
    } finally {
      inFlight = false;
      if (Object.keys(pending).length && !blocked) flush();
    }
  }

  quill.on('text-change', (_d, _o, source) => {
    if (source === 'user') queue({ content: quill.root.innerHTML });
  });

  titleEl.dataset.last = titleEl.value;
  function commitTitle() {
    const t = titleEl.value.trim();
    if (!t) { titleEl.value = titleEl.dataset.last; return; }
    if (t === titleEl.dataset.last) return;
    titleEl.dataset.last = t;
    const st = document.getElementById('share-title');
    if (st) st.textContent = t;
    queue({ title: t }, 0);
  }
  if (canEdit) {
    titleEl.addEventListener('blur', commitTitle);
    titleEl.addEventListener('keydown', e => {
      if (e.key === 'Enter') { e.preventDefault(); titleEl.blur(); }
      if (e.key === 'Escape') { titleEl.value = titleEl.dataset.last; titleEl.blur(); }
    });
  }

  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); flush(); }
  });
  window.addEventListener('beforeunload', e => {
    if (Object.keys(pending).length || inFlight) { e.preventDefault(); e.returnValue = ''; }
  });

  document.getElementById('conflict-reload')?.addEventListener('click', () => {
    const latest = conflictEl._latest;
    version = latest.version;
    loadContent(latest.content);
    titleEl.value = titleEl.dataset.last = latest.title;
    pending = {}; blocked = false; conflictEl.hidden = true;
    setStatus('Loaded latest version');
  });
  document.getElementById('conflict-overwrite')?.addEventListener('click', () => {
    version = conflictEl._latest.version;
    pending = { title: titleEl.value.trim() || titleEl.dataset.last, content: quill.root.innerHTML };
    blocked = false; conflictEl.hidden = true;
    flush(true);
  });

  // ------------------------------------------------------------ sharing (owner only)
  const dialog = document.getElementById('share-dialog');
  if (!dialog) return;
  const list = document.getElementById('share-list');
  const errEl = document.getElementById('share-error');

  const api = async (url, opts = {}) => {
    const res = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...opts });
    const data = res.status === 204 ? {} : await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
    return data;
  };
  const showError = msg => { errEl.textContent = msg || ''; errEl.hidden = !msg; };

  function renderShares(shares) {
    list.innerHTML = '';
    if (!shares.length) {
      list.innerHTML = '<li class="muted small">Only you have access.</li>';
      return;
    }
    for (const s of shares) {
      const li = document.createElement('li');
      li.innerHTML = `
        <span class="avatar sm"></span>
        <span class="share-who"><strong></strong><span class="muted small"></span></span>
        <select aria-label="Role"><option value="editor">Editor</option><option value="viewer">Viewer</option></select>
        <button class="btn btn-ghost btn-sm" aria-label="Remove access">Remove</button>`;
      li.querySelector('.avatar').textContent = s.name[0];
      li.querySelector('strong').textContent = s.name;
      li.querySelector('.muted').textContent = s.email;
      const sel = li.querySelector('select');
      sel.value = s.role;
      sel.addEventListener('change', async () => {
        try { await api(`/api/documents/${doc.id}/shares`, { method: 'POST', body: JSON.stringify({ email: s.email, role: sel.value }) }); showError(''); }
        catch (e) { showError(e.message); sel.value = s.role; }
      });
      li.querySelector('button').addEventListener('click', async () => {
        try { await api(`/api/documents/${doc.id}/shares/${s.id}`, { method: 'DELETE' }); refresh(); }
        catch (e) { showError(e.message); }
      });
      list.appendChild(li);
    }
  }
  async function refresh() {
    try { renderShares((await api(`/api/documents/${doc.id}/shares`)).shares); }
    catch (e) { showError(e.message); }
  }

  document.getElementById('share-btn').addEventListener('click', () => { showError(''); refresh(); dialog.showModal(); });
  document.getElementById('share-form').addEventListener('submit', async e => {
    e.preventDefault();
    const emailEl = document.getElementById('share-email');
    try {
      await api(`/api/documents/${doc.id}/shares`, {
        method: 'POST',
        body: JSON.stringify({ email: emailEl.value, role: document.getElementById('share-role').value }),
      });
      emailEl.value = ''; showError(''); refresh();
    } catch (err) { showError(err.message); }
  });
})();
