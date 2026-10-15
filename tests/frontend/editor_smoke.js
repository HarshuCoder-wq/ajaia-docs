// Headless smoke test: real Quill 2 + our editor.js in jsdom, against the running Flask server.
const { JSDOM } = require('jsdom');
const fs = require('fs');
const BASE = process.env.BASE_URL || 'http://127.0.0.1:5000';
const APP = require('path').resolve(__dirname, '../../app');

async function login(email) {
  const r = await fetch(BASE + '/login', { method: 'POST', redirect: 'manual',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: `email=${email}&password=demo1234` });
  return r.headers.get('set-cookie').split(';')[0];
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function openEditor(cookie, id) {
  const html = await (await fetch(`${BASE}/documents/${id}`, { headers: { cookie } })).text();
  const dom = new JSDOM(html, { url: `${BASE}/documents/${id}`, runScripts: 'outside-only', pretendToBeVisual: true });
  const w = dom.window;
  w.fetch = (url, opts = {}) => fetch(new URL(url, BASE), { ...opts, headers: { ...(opts.headers || {}), cookie } });
  w.HTMLDialogElement && (w.HTMLDialogElement.prototype.showModal = function () { this.open = true; });
  w.document.getSelection = w.document.getSelection || (() => null);
  w.eval(fs.readFileSync(require.resolve('quill/dist/quill.js'), 'utf8'));
  const m = html.match(/window\.DOC = (.*?);<\/script>/s);
  w.eval('window.DOC = ' + m[1]);
  w.eval(fs.readFileSync(APP + '/static/editor.js', 'utf8'));
  return w;
}

(async () => {
  const alice = await login('alice@ajaia.test');
  const bob = await login('bob@ajaia.test');
  const api = (c, p, o = {}) => fetch(BASE + p, { ...o, headers: { cookie: c, 'Content-Type': 'application/json' } });

  // Seed a doc with plain imported-style HTML (<ul>, h1) to check conversion on load.
  const id = (await api(alice, '/documents', { method: 'POST', redirect: 'manual' })).headers.get('location').split('/').pop();
  await api(alice, `/api/documents/${id}`, { method: 'PATCH', body: JSON.stringify({ version: 1, content: '<h1>Plan</h1><ul><li>one</li><li>two</li></ul>' }) });
  await api(alice, `/api/documents/${id}/shares`, { method: 'POST', body: JSON.stringify({ email: 'bob@ajaia.test', role: 'editor' }) });

  const w = await openEditor(alice, id);
  const root = w.document.querySelector('.ql-editor');
  console.log('loaded HTML :', root.innerHTML);
  console.log('toolbar     :', !!w.document.querySelector('.ql-toolbar'));

  // Simulate a user edit via Quill API (source user) → autosave.
  const q = w.Quill.find(w.document.getElementById('editor'));
  q.insertText(q.getLength() - 1, 'typed by alice', { bold: true }, 'user');
  console.log('status now  :', w.document.getElementById('status').textContent);
  await sleep(1500);
  console.log('status after:', w.document.getElementById('status').textContent);
  let saved = await (await api(alice, `/api/documents/${id}`)).json();
  console.log('server v' + saved.version + ' :', saved.content);

  // Rename via title input blur.
  const t = w.document.getElementById('title');
  t.value = 'Renamed via UI'; t.dispatchEvent(new w.Event('blur'));
  await sleep(500);
  saved = await (await api(alice, `/api/documents/${id}`)).json();
  console.log('title       :', saved.title, 'v' + saved.version);

  // Conflict: bob saves behind alice's back, then alice edits.
  await api(bob, `/api/documents/${id}`, { method: 'PATCH', body: JSON.stringify({ version: saved.version, content: '<p>bob version</p>' }) });
  q.insertText(0, 'X', 'user');
  await sleep(1500);
  console.log('conflict UI :', !w.document.getElementById('conflict').hidden, '|', w.document.getElementById('status').textContent);
  w.document.getElementById('conflict-reload').click();
  console.log('after reload:', root.innerHTML);

  // Viewer: read-only, no toolbar.
  await api(alice, `/api/documents/${id}/shares`, { method: 'POST', body: JSON.stringify({ email: 'carol@ajaia.test', role: 'viewer' }) });
  const carol = await login('carol@ajaia.test');
  const wc = await openEditor(carol, id);
  console.log('viewer      : toolbar', !!wc.document.querySelector('.ql-toolbar'), 'editable', wc.document.querySelector('.ql-editor').getAttribute('contenteditable'), 'share btn', !!wc.document.getElementById('share-btn'));

  // Share dialog renders list.
  w.document.getElementById('share-btn').click();
  await sleep(500);
  console.log('share list  :', [...w.document.querySelectorAll('#share-list li')].map(li => li.querySelector('strong').textContent + ':' + li.querySelector('select').value).join(', '));
  process.exit(0);
})().catch(e => { console.error('FAIL', e); process.exit(1); });
