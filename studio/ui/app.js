/* Highlight Studio UI. Talks to Python through window.pywebview.api; media and thumbnails
   come from the local media server (same origin, token-protected). */
(function () {
'use strict';
const $ = s => document.querySelector(s);
const API = () => window.pywebview.api;
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

/* ---------- icons ---------- */
const P = {
 video:'<rect x="2.5" y="5" width="11" height="10" rx="2"/><path d="M13.5 9l4-2.5v7l-4-2.5"/>',
 scissors:'<circle cx="5.5" cy="6" r="2.5"/><circle cx="5.5" cy="14" r="2.5"/><path d="M7.6 7.3L17 15M7.6 12.7L17 5"/>',
 stack:'<rect x="3" y="7" width="14" height="10" rx="2"/><path d="M5 4.5h10M7 2h6"/>',
 gear:'<circle cx="10" cy="10" r="2.5"/><path d="M10 2.5v2M10 15.5v2M2.5 10h2M15.5 10h2M4.7 4.7l1.4 1.4M13.9 13.9l1.4 1.4M4.7 15.3l1.4-1.4M13.9 6.1l1.4-1.4"/>',
 trash:'<path d="M3.5 5.5h13M8 5.5V3.8h4v1.7M5 5.5l.8 11h8.4l.8-11M8.5 8.5v5M11.5 8.5v5"/>',
 play:'<path d="M6.5 4.5v11l9-5.5z" fill="currentColor" stroke="none"/>',
 pause:'<path d="M7 4.5v11M13 4.5v11" stroke-width="2.4"/>',
 sparkle:'<path d="M10 2.5l1.6 4.6 4.6 1.6-4.6 1.6L10 15l-1.6-4.7-4.6-1.6 4.6-1.6z"/><path d="M15.5 13.5l.6 1.6 1.6.6-1.6.6-.6 1.6-.6-1.6-1.6-.6 1.6-.6z"/>',
 plus:'<path d="M10 4v12M4 10h12"/>',
 folder:'<path d="M2.5 6v9a1.5 1.5 0 001.5 1.5h12a1.5 1.5 0 001.5-1.5V8a1.5 1.5 0 00-1.5-1.5H10L8.3 4.5H4A1.5 1.5 0 002.5 6z"/>',
 check:'<path d="M4.5 10.5l3.5 3.5 7.5-8"/>',
 chevron:'<path d="M7.5 5l5 5-5 5"/>',
 grid:'<rect x="3" y="3" width="6" height="6" rx="1"/><rect x="11" y="3" width="6" height="6" rx="1"/><rect x="3" y="11" width="6" height="6" rx="1"/><rect x="11" y="11" width="6" height="6" rx="1"/>',
 list:'<path d="M7 5h10M7 10h10M7 15h10M3 5h.01M3 10h.01M3 15h.01"/>',
 search:'<circle cx="8.5" cy="8.5" r="5"/><path d="M12.5 12.5l4.5 4.5"/>',
 x:'<path d="M5 5l10 10M15 5L5 15"/>',
 grip:'<path d="M7.5 5h.01M12.5 5h.01M7.5 10h.01M12.5 10h.01M7.5 15h.01M12.5 15h.01"/>',
 music:'<path d="M7.5 15V4.5l9-2v10"/><circle cx="5.5" cy="15" r="2"/><circle cx="14.5" cy="12.5" r="2"/>',
 copy:'<rect x="7" y="7" width="10" height="10" rx="2"/><path d="M13 7V4.5A1.5 1.5 0 0011.5 3h-7A1.5 1.5 0 003 4.5v7A1.5 1.5 0 004.5 13H7"/>',
 activity:'<path d="M2.5 10h3l2-5 4 10 2-5h4"/>',
 queue:'<path d="M3 5h10M3 10h10M3 15h6M15 12v6M12 15h6"/>',
 retry:'<path d="M16 10a6 6 0 11-1.8-4.3"/><path d="M16 3.5v3h-3"/>',
 warn:'<path d="M10 3l7.5 13.5h-15z"/><path d="M10 8v3.5M10 14h.01"/>',
 loader:'<path d="M10 2.5a7.5 7.5 0 107.5 7.5"/>',
 eye:'<path d="M2 10s3-5.5 8-5.5 8 5.5 8 5.5-3 5.5-8 5.5S2 10 2 10z"/><circle cx="10" cy="10" r="2.3"/>',
 refresh:'<path d="M16.5 10a6.5 6.5 0 01-11.6 4M3.5 10a6.5 6.5 0 0111.6-4"/><path d="M15.5 2.5v3.5H12M4.5 17.5V14H8"/>',
 disk:'<rect x="2.5" y="5" width="15" height="10" rx="2"/><path d="M14 10h.01"/>',
 link:'<path d="M8.5 11.5a3.5 3.5 0 005 0l2.5-2.5a3.5 3.5 0 00-5-5l-1 1"/><path d="M11.5 8.5a3.5 3.5 0 00-5 0L4 11a3.5 3.5 0 005 5l1-1"/>',
};
const ic = (n, cls = '') => `<svg class="ic ${cls}" viewBox="0 0 20 20" aria-hidden="true">${P[n]}</svg>`;

/* ---------- state ---------- */
let K = '';
const D = {footage: [], sets: [], merged: [], tracks: [], jobs: [], watch: {waiting: [], ytal: false}, disk: null, claude: {}, roots: {}, loaded: {}};
const S = {page: 'footage', view: 'grid', q: '', status: 'all', sort: 'newest', minScore: 0,
  sel: {footage: new Set(), shorts: new Set(), music: new Set()}, queue: [], queueOpen: false, jobsOpen: false,
  detail: null, collapsed: new Set(), merge: {fmt: 'short', hq: true, style: 'punchy', music: 'any', name: ''},
  musicTab: 'library', ncsQ: '', ncsItems: null, ncsLoading: false, ncsError: '', genre: 'all', playing: null,
  lookup: null, lookupBusy: false, link: '', settings: {}};
let clipById = new Map(), clipByPath = new Map(), recById = new Map(), setOfClip = new Map();
const prevJobState = new Map();

const lsGet = (k, d) => { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (_) { return d; } };
const lsSet = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (_) {} };

/* ---------- formatting ---------- */
const dur = s => { s = Math.max(0, Math.round(s || 0)); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60;
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(x).padStart(2, '0')}` : `${m}:${String(x).padStart(2, '0')}`; };
// same units as File Explorer (1 GB = 1024³ bytes), so numbers match what Windows shows
const size = b => b >= 1073741824 ? `${(b / 1073741824).toFixed(1)} GB` : `${Math.max(1, Math.round(b / 1048576))} MB`;
const MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const when = ts => { if (!ts) return ''; const d = new Date(ts); if (isNaN(d)) return ts;
  return `${d.getDate()} ${MON[d.getMonth()]} ${d.getFullYear()}, ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`; };
const base = p => String(p || '').split(/[\\/]/).pop();
const plural = (n, a, b) => `${n} ${n === 1 ? a : (b || a + 's')}`;
const mediaUrl = p => `/media?k=${K}&p=${encodeURIComponent(p)}`;
const thumbUrl = (p, f = 0.1, w = 480) => `/thumb?k=${K}&p=${encodeURIComponent(p)}&f=${f}&w=${w}`;
const frameUrl = (p, i) => `/thumb?k=${K}&p=${encodeURIComponent(p)}&i=${i}&w=360`;
const GAMEC = {};
const gameColor = g => { if (!(g in GAMEC)) { const known = {'Valorant': 0, 'Arena Breakout Infinite': 1, 'Gray Zone Warfare': 2, 'Wardogs': 3, 'Desktop': 5};
  GAMEC[g] = `var(--g${known[g] ?? (Object.keys(GAMEC).length % 6)})`; } return GAMEC[g]; };

const STATUS = {done: 'Done', new: 'New', processing: 'Processing', queued: 'Queued', failed: 'Failed', too_small: 'Too small',
  recording: 'Recording', stale: 'Stuck', changed: 'Changed', original_deleted: 'Deleted'};

/* ---------- data ---------- */
function jobFor(path) {
  const lp = String(path).toLowerCase();
  return D.jobs.find(j => j.kind === 'highlight' && j.path.toLowerCase() === lp && (j.state === 'queued' || j.state === 'running'));
}
function effStatus(r) {
  const j = jobFor(r.path);
  if (j) return j.state === 'running' ? 'processing' : 'queued';
  return r.status;
}
const runnable = r => ['new', 'failed', 'stale'].includes(effStatus(r));
const selectable = r => !['recording', 'processing', 'queued'].includes(effStatus(r));

async function loadFootage() {
  D.footage = await API().footage(); D.loaded.footage = true;
  recById = new Map(D.footage.map(r => [r.id, r]));
  for (const id of [...S.sel.footage]) if (!recById.has(id)) S.sel.footage.delete(id);
}
async function loadShorts() {
  D.sets = await API().shorts(); D.loaded.shorts = true;
  clipById = new Map(); clipByPath = new Map(); setOfClip = new Map();
  for (const s of D.sets) for (const c of s.clips) { c.game = s.game; clipById.set(c.id, c); clipByPath.set(c.path.toLowerCase(), c); setOfClip.set(c.id, s); }
  for (const id of [...S.sel.shorts]) if (!clipById.has(id)) S.sel.shorts.delete(id);
  const before = S.queue.length;
  S.queue = S.queue.filter(p => clipByPath.has(p.toLowerCase()));
  if (S.queue.length !== before) lsSet('queue', S.queue);
}
async function loadMerged() { D.merged = await API().merged(); D.loaded.merged = true; }
async function loadMusic() { D.tracks = await API().music_list(); D.loaded.music = true; }
async function loadDisk() { D.disk = await API().disk(); renderTop(); }
const clipOfPath = p => clipByPath.get(String(p).toLowerCase());

/* ---------- shell ---------- */
function renderTop() {
  const d = D.disk;
  if (d && d.total) {
    const used = 1 - d.free / d.total;
    $('#disk').className = 'disk num' + (d.free < 20e9 ? ' low' : '');
    $('#disk').innerHTML = `${ic('disk')}<span>${esc(d.drive)} ${size(d.free)} free of ${size(d.total)}</span><span class="bar"><i style="width:${(used * 100).toFixed(0)}%"></i></span>`;
  }
  const active = D.jobs.filter(j => j.state === 'running' || j.state === 'queued').length;
  $('#jBtn').innerHTML = `${active ? ic('loader', 'spin') : ic('activity')}<span>Jobs</span><span class="count num ${active ? '' : 'zero'}">${active}</span>`;
  $('#jBtn').setAttribute('aria-pressed', S.jobsOpen);
  $('#qBtn').innerHTML = `${ic('queue')}<span>Merge queue</span><span class="count num ${S.queue.length ? '' : 'zero'}">${S.queue.length}</span>`;
  $('#qBtn').setAttribute('aria-pressed', S.queueOpen);
}
function renderNav() {
  const nClips = D.sets.reduce((a, s) => a + s.clips.length, 0);
  const items = [['footage', 'video', 'Footage', D.footage.length], ['shorts', 'scissors', 'Shorts', nClips],
    ['merged', 'stack', 'Merged', D.merged.length], ['music', 'music', 'Music', D.tracks.length]];
  $('#nav').innerHTML = items.map(([k, i, l, b]) => `<button data-action="nav" data-page="${k}" ${S.page === k ? 'aria-current="page"' : ''}>${ic(i)}<span>${l}</span><span class="badge num">${D.loaded[k] ? b : ''}</span></button>`).join('')
    + `<span class="grow"></span><button data-action="nav" data-page="settings" ${S.page === 'settings' ? 'aria-current="page"' : ''}>${ic('gear')}<span>Settings</span></button>`;
}
function render() {
  renderTop(); renderNav();
  const m = $('#main'), keep = m.scrollTop;
  const fn = {footage: pageFootage, shorts: pageShorts, merged: pageMerged, music: pageMusic, settings: pageSettings}[S.page];
  m.innerHTML = fn();
  m.scrollTop = keep;
  renderQueue(); renderFlyout();
}
const loadingPage = (title) => `<div class="page"><div class="pagehead"><h1>${title}</h1></div><div class="loading">${ic('loader', 'spin')}Reading your folders…</div></div>`;

/* ---------- Footage ---------- */
function filteredRecs() {
  const q = S.q.toLowerCase();
  const list = D.footage.filter(r => {
    const st = effStatus(r);
    const okS = S.status === 'all' || (S.status === 'new' ? runnable(r) : S.status === 'processing' ? (st === 'processing' || st === 'queued') : st === S.status);
    return okS && (!q || r.file.toLowerCase().includes(q));
  });
  const sorters = {newest: (a, b) => b.recorded.localeCompare(a.recorded), oldest: (a, b) => a.recorded.localeCompare(b.recorded),
    size: (a, b) => b.size - a.size, length: (a, b) => b.dur - a.dur};
  return list.sort(sorters[S.sort]);
}
function jobPct(j) { return j && j.state === 'running' ? Math.round(((j.step || 0) + 0.5) / (j.steps || []).length * 100) : 0; }
function pill(r) {
  const st = effStatus(r), j = jobFor(r.path);
  if (st === 'done') return `<span class="pill st-done">${ic('check')}${r.clips != null ? plural(r.clips, 'short') : 'Done'}</span>`;
  if (st === 'processing') return `<span class="pill st-processing">${ic('loader', 'spin')}${j ? esc(j.steps[j.step] || 'Processing') : 'Processing'}</span>`;
  if (st === 'recording') return `<span class="pill st-recording"><span class="rec-dot"></span>Recording</span>`;
  return `<span class="pill st-${st}">${STATUS[st] || esc(st)}</span>`;
}
function thumbBox(path, durS, f, extra = '', portrait = false) {
  return `<div class="thumb ${portrait ? 'portrait' : ''}" data-scrub="${durS || 0}" data-p="${esc(path)}">
    <img loading="lazy" src="${thumbUrl(path, f)}" data-src="${thumbUrl(path, f)}" alt="" draggable="false">
    <span class="scrub"></span><span class="scrubtime num"></span>${extra}</div>`;
}
function recCard(r) {
  const sel = S.sel.footage.has(r.id), dis = !selectable(r), j = jobFor(r.path), st = effStatus(r);
  const extra = `${dis ? '' : `<button class="chk" data-action="check" data-id="${r.id}" data-kind="footage" role="checkbox" aria-checked="${sel}" aria-label="Select">${ic('check')}</button>`}
    ${pill(r)}<span class="dur num">${dur(r.dur)}</span>${st === 'processing' ? `<span class="progress"><i style="width:${jobPct(j)}%"></i></span>` : ''}`;
  return `<div class="card ${sel ? 'selected' : ''} ${dis ? 'disabled' : ''}" data-action="card" data-id="${r.id}" data-kind="footage" title="${esc(r.file)}">
    ${thumbBox(r.path, r.dur, 0.1, extra)}
    <div class="cname">${esc(when(r.recorded))}</div>
    <div class="cmeta num"><span>${size(r.size)}</span>${r.res ? `<span>${esc(r.res)}</span>` : ''}${st === 'failed' && r.reason ? `<span class="bad" title="${esc(r.reason)}">${esc(r.reason.slice(0, 60))}</span>` : ''}</div></div>`;
}
function recRow(r) {
  const sel = S.sel.footage.has(r.id), dis = !selectable(r), st = effStatus(r);
  const label = st === 'done' && r.clips != null ? plural(r.clips, 'short') : (STATUS[st] || st);
  return `<tr class="${sel ? 'selected' : ''}" data-action="card" data-id="${r.id}" data-kind="footage">
    <td>${dis ? '' : `<button class="boxchk" data-action="check" data-id="${r.id}" data-kind="footage" role="checkbox" aria-checked="${sel}" aria-label="Select">${ic('check')}</button>`}</td>
    <td class="name" title="${esc(r.file)}">${esc(r.file)}</td><td class="r num">${dur(r.dur)}</td><td class="r num">${size(r.size)}</td><td>${esc(r.res)}</td>
    <td class="num">${esc(when(r.recorded))}</td><td><span class="tpill st-${st}">${esc(label)}</span></td></tr>`;
}
function pageFootage() {
  if (!D.loaded.footage) return loadingPage('Footage');
  const list = filteredRecs(), games = [...new Set(list.map(r => r.game))].sort();
  const total = D.footage.reduce((a, r) => a + r.size, 0), nNew = D.footage.filter(r => r.status === 'new').length;
  let h = `<div class="page"><div class="pagehead"><h1>Footage</h1><span class="sub num">${plural(D.footage.length, 'recording')}, ${size(total)} in ${esc(D.roots.recordings)}. ${nNew} not processed yet.</span></div>
  <div class="toolbar">
   <label class="search">${ic('search')}<input id="q" type="text" placeholder="Search recordings" value="${esc(S.q)}" aria-label="Search recordings"></label>
   <select class="select" id="statusSel" aria-label="Status">${[['all', 'All statuses'], ['new', 'Not processed'], ['done', 'Done'], ['processing', 'Processing'], ['too_small', 'Too small']].map(([v, l]) => `<option value="${v}" ${S.status === v ? 'selected' : ''}>${l}</option>`).join('')}</select>
   <select class="select" id="sortSel" aria-label="Sort">${[['newest', 'Newest first'], ['oldest', 'Oldest first'], ['size', 'Largest first'], ['length', 'Longest first']].map(([v, l]) => `<option value="${v}" ${S.sort === v ? 'selected' : ''}>${l}</option>`).join('')}</select>
   <button class="btn ghost" data-action="refresh" title="Scan the folders again">${ic('refresh')}Refresh</button>
   <span class="grow"></span>
   <div class="seg" role="group" aria-label="View"><button data-action="view" data-view="grid" aria-pressed="${S.view === 'grid'}">${ic('grid')}Thumbnails</button><button data-action="view" data-view="table" aria-pressed="${S.view === 'table'}">${ic('list')}Details</button></div>
  </div>`;
  if (!D.footage.length) h += `<div class="empty"><b>No recordings yet</b>Recordings saved to ${esc(D.roots.recordings)} show up here.</div>`;
  else if (!list.length) h += `<div class="empty"><b>No recordings match</b>Clear the search or pick another status.</div>`;
  for (const g of games) {
    const rs = list.filter(r => r.game === g), col = S.collapsed.has('f:' + g);
    h += `<section class="group ${col ? 'collapsed' : ''}"><div class="ghead">
      <button class="toggle" data-action="collapse" data-g="f:${esc(g)}" aria-expanded="${!col}">${ic('chevron')}<span class="gdot" style="background:${gameColor(g)}"></span>${esc(g)}</button>
      <span class="gmeta num">${plural(rs.length, 'recording')}, ${size(rs.reduce((a, r) => a + r.size, 0))}</span><span class="grow"></span>
      <button class="linkbtn" data-action="sel-group" data-g="${esc(g)}" data-mode="new">Select not processed</button>
      <button class="linkbtn" data-action="sel-group" data-g="${esc(g)}" data-mode="all">Select all</button></div><div class="gbody">`;
    h += S.view === 'grid' ? `<div class="grid">${rs.map(recCard).join('')}</div>`
      : `<div class="tablewrap wide"><table><thead><tr><th style="width:36px"></th><th>Name</th><th class="r">Length</th><th class="r">Size</th><th>Resolution</th><th>Recorded</th><th>Status</th></tr></thead><tbody>${rs.map(recRow).join('')}</tbody></table></div>`;
    h += `</div></section>`;
  }
  const sel = [...S.sel.footage].map(id => recById.get(id)).filter(Boolean), run = sel.filter(runnable).length;
  h += `</div><div class="cmdbar ${sel.length ? '' : 'hide'}" role="toolbar" aria-label="Selection">
   <span class="info num"><strong>${sel.length} selected</strong>, ${size(sel.reduce((a, r) => a + r.size, 0))}</span>
   <button class="btn primary" data-action="make" ${run ? '' : 'disabled'} title="${sel.length - run ? `${sel.length - run} already processed or too small, skipped` : ''}">${ic('sparkle')}Make highlights${run ? ` (${run})` : ''}</button>
   <button class="btn danger" data-action="del-footage">${ic('trash')}Delete${sel.length > 1 ? ` (${sel.length})` : ''}</button>
   <button class="btn ghost" data-action="clear" data-kind="footage">Clear</button></div>`;
  return h;
}

/* ---------- Shorts ---------- */
function pageShorts() {
  if (!D.loaded.shorts) return loadingPage('Shorts');
  const q = S.q.toLowerCase();
  const match = c => (c.score == null ? S.minScore === 0 : c.score >= S.minScore) && (!q || c.title.toLowerCase().includes(q) || c.file.toLowerCase().includes(q));
  const sets = D.sets.map(s => ({...s, vis: s.clips.filter(match)})).filter(s => s.vis.length);
  const games = [...new Set(sets.map(s => s.game))].sort();
  const nClips = D.sets.reduce((a, s) => a + s.clips.length, 0);
  let h = `<div class="page"><div class="pagehead"><h1>Shorts</h1><span class="sub num">${plural(nClips, 'short')} from ${plural(D.sets.length, 'recording')} in ${esc(D.roots.highlights)}</span></div>
  <div class="toolbar"><label class="search">${ic('search')}<input id="q" type="text" placeholder="Search shorts" value="${esc(S.q)}" aria-label="Search shorts"></label>
   <select class="select" id="minScore" aria-label="Minimum score">${[0, 60, 70, 80].map(v => `<option value="${v}" ${S.minScore == v ? 'selected' : ''}>${v ? `Score ${v}+` : 'Any score'}</option>`).join('')}</select>
   <button class="btn ghost" data-action="refresh">${ic('refresh')}Refresh</button></div>`;
  if (!nClips) h += `<div class="empty"><b>No shorts yet</b>Pick recordings on the Footage page and choose Make highlights.</div>`;
  else if (!sets.length) h += `<div class="empty"><b>No shorts match</b>Clear the search or lower the minimum score.</div>`;
  for (const g of games) {
    const col = S.collapsed.has('s:' + g);
    h += `<section class="group ${col ? 'collapsed' : ''}"><div class="ghead"><button class="toggle" data-action="collapse" data-g="s:${esc(g)}" aria-expanded="${!col}">${ic('chevron')}<span class="gdot" style="background:${gameColor(g)}"></span>${esc(g)}</button></div><div class="gbody">`;
    const gs = sets.filter(s => s.game === g).sort((a, b) => b.label.localeCompare(a.label));
    for (const s of gs) {
      const older = !s.current && D.sets.some(o => o.current && o.path.toLowerCase().startsWith(s.path.toLowerCase() + '\\'));
      h += `<div class="sub-ghead">${ic('folder')}<strong>${esc(s.label)}</strong>${older ? '<span class="oldtag">Earlier run</span>' : ''}<span class="num">${plural(s.vis.length, 'short')}</span><span class="grow"></span>
        <button class="linkbtn" data-action="reveal" data-p="${esc(s.path)}">Show in folder</button><button class="linkbtn" data-action="sel-set" data-id="${s.id}">Select all</button></div>
        <div class="grid small">${s.vis.map(clipCard).join('')}</div>`;
    }
    h += `</div></section>`;
  }
  const n = S.sel.shorts.size, len = [...S.sel.shorts].reduce((a, id) => a + (clipById.get(id)?.len || 0), 0);
  h += `</div><div class="cmdbar ${n ? '' : 'hide'}" role="toolbar" aria-label="Selection"><span class="info num"><strong>${n} selected</strong>, ${dur(len)}</span>
   <button class="btn primary" data-action="add-queue">${ic('plus')}Add to merge queue</button>
   <button class="btn danger" data-action="del-shorts">${ic('trash')}Delete${n > 1 ? ` (${n})` : ''}</button>
   <button class="btn ghost" data-action="clear" data-kind="shorts">Clear</button></div>`;
  return h;
}
function clipCard(c) {
  const sel = S.sel.shorts.has(c.id), q = S.queue.some(p => p.toLowerCase() === c.path.toLowerCase());
  const extra = `<button class="chk" data-action="check" data-id="${c.id}" data-kind="shorts" role="checkbox" aria-checked="${sel}" aria-label="Select">${ic('check')}</button>
    ${c.score != null ? `<span class="score num ${c.score >= 85 ? 'top' : ''}" title="Score">${c.score}</span>` : ''}<span class="dur num">${dur(c.len)}</span>`;
  return `<div class="card ${sel ? 'selected' : ''}" data-action="open-clip" data-id="${c.id}" data-kind="shorts" title="${esc(c.file)}">
    ${thumbBox(c.path, c.len, 0.4, extra)}
    <div class="cname">${esc(c.title)}</div>
    <div class="cmeta">${c.n != null ? `<span class="num">#${String(c.n).padStart(2, '0')}</span>` : ''}${q ? '<span class="inqueue">In merge queue</span>' : ''}${c.used ? `<span class="used">${ic('stack')}Used in ${plural(c.used, 'merge')}</span>` : ''}</div></div>`;
}

/* ---------- Merge queue ---------- */
const QCOL = ['var(--accent)', 'var(--g1)', 'var(--g2)', 'var(--g3)', 'var(--g0)'];
function trackLabel(t) { return `${t.artist ? t.artist + ' - ' : ''}${t.title || t.file}`; }
function renderQueue() {
  const el = $('#queue'); el.hidden = !S.queueOpen; if (!S.queueOpen) return;
  const items = S.queue.map(clipOfPath).filter(Boolean), total = items.reduce((a, c) => a + c.len, 0);
  const limit = S.merge.fmt === 'short' ? 180 : null, scale = limit ? Math.max(limit, total) : Math.max(total, 1);
  let acc = 0;
  const usable = D.tracks.filter(t => t.credit_state !== 'missing');
  el.innerHTML = `<div class="qhead"><h2>Merge queue</h2><span class="grow"></span>${items.length ? '<button class="linkbtn" data-action="q-clear">Clear</button>' : ''}<button class="iconbtn" data-action="toggle-queue" aria-label="Hide merge queue">${ic('x')}</button></div>
  ${items.length ? `<ol class="qlist" id="qlist">${items.map(c => `<li class="qitem" draggable="true" data-qp="${esc(c.path)}">
    <span class="grip" title="Drag to reorder">${ic('grip')}</span><span class="mini"><img src="${thumbUrl(c.path, 0.4)}" alt="" draggable="false"></span>
    <span class="t"><b title="${esc(c.title)}">${esc(c.title)}</b><span class="num">${dur(c.len)}${c.score != null ? `, score ${c.score}` : ''}, ${esc(c.game)}</span></span>
    <button class="iconbtn" data-action="q-remove" data-p="${esc(c.path)}" aria-label="Remove">${ic('x')}</button></li>`).join('')}</ol>`
   : `<div class="qempty">Select shorts and choose <b>Add to merge queue</b>. Drag them into the order you want.</div><div style="flex:1"></div>`}
  ${items.length ? `<div class="timeline" title="Raw length of each short">${items.map((c, i) => { const op = limit && acc >= limit ? .35 : 1; acc += c.len;
      return `<i style="width:${c.len / scale * 100}%;background:${QCOL[i % QCOL.length]};opacity:${op}" title="${esc(c.title)} ${dur(c.len)}"></i>`; }).join('')}${limit ? `<span class="limit" style="left:${limit / scale * 100}%"></span>` : ''}</div>
   <div class="tl-label num ${limit && total > limit ? 'over' : ''}"><span>${dur(total)} before trimming</span><span>${limit ? (total > limit ? `${dur(total - limit)} over 3:00, trimming may fix it` : '3:00 Short limit') : 'No length limit'}</span></div>` : ''}
  <div class="qopts">
   <div class="field"><label for="outName">Name</label><input type="text" id="outName" value="${esc(S.merge.name)}" placeholder="Merged video name"></div>
   <div class="field"><label>Format</label><div class="seg" role="group"><button data-action="fmt" data-v="short" aria-pressed="${S.merge.fmt === 'short'}">Short 9:16</button><button data-action="fmt" data-v="long" aria-pressed="${S.merge.fmt === 'long'}">Long 16:9</button></div></div>
   <div class="field"><label for="musicSel">Music</label><select class="select" id="musicSel"><option value="any" ${S.merge.music === 'any' ? 'selected' : ''}>Shuffle tracks that have a credit${usable.length ? '' : ' (none yet)'}</option>${D.tracks.map(t => `<option value="${esc(t.path)}" ${t.credit_state === 'missing' ? 'disabled' : ''} ${S.merge.music === t.path ? 'selected' : ''}>${esc(trackLabel(t))}${t.credit_state === 'missing' ? ' (add a credit first)' : ''}</option>`).join('')}</select></div>
   <div class="field"><label for="styleSel">Style</label><select class="select" id="styleSel"><option value="punchy" ${S.merge.style === 'punchy' ? 'selected' : ''}>Punchy: zoom and flash on kills</option><option value="clean" ${S.merge.style === 'clean' ? 'selected' : ''}>Clean: plain crossfades</option></select></div>
   <div class="field"><label>1440p</label><span style="display:flex;align-items:center;gap:8px"><button class="switch" data-action="hq" role="switch" aria-checked="${S.merge.hq}" aria-label="1440p output"></button><span class="note">${S.merge.hq ? 'Higher quality on YouTube' : '1080p'}</span></span></div>
  </div>
  <div class="qactions"><button class="btn" data-action="preview" ${items.length < 2 ? 'disabled' : ''}>${ic('eye')}Preview cuts</button><button class="btn primary" data-action="merge" ${items.length < 2 ? 'disabled' : ''} title="${items.length < 2 ? 'Add at least 2 shorts' : ''}">${ic('stack')}Merge</button></div>`;
  bindDrag();
}
function saveQueue() { lsSet('queue', S.queue); }
function saveMergeOpts() { API().settings_set({merge: {fmt: S.merge.fmt, hq: S.merge.hq, style: S.merge.style, music: S.merge.music}}); }
function bindDrag() {
  const list = $('#qlist'); if (!list) return; let drag = null;
  list.querySelectorAll('.qitem').forEach(li => {
    li.addEventListener('dragstart', e => { drag = li.dataset.qp; li.classList.add('dragging'); e.dataTransfer.effectAllowed = 'move'; try { e.dataTransfer.setData('text/plain', drag); } catch (_) {} });
    li.addEventListener('dragend', () => { li.classList.remove('dragging'); list.querySelectorAll('.over').forEach(x => x.classList.remove('over')); });
    li.addEventListener('dragover', e => { e.preventDefault(); list.querySelectorAll('.over').forEach(x => x.classList.remove('over')); li.classList.add('over'); });
    li.addEventListener('drop', e => { e.preventDefault(); const to = li.dataset.qp; if (!drag || drag === to) return;
      const q = S.queue.filter(x => x !== drag); q.splice(q.indexOf(to), 0, drag); S.queue = q; saveQueue(); render(); });
  });
}
function mergeOpts(musicOverride) {
  return {clips: S.queue, name: S.merge.name || defaultName(), fmt: S.merge.fmt, hq: S.merge.hq, style: S.merge.style, music: musicOverride || S.merge.music};
}
function defaultName() {
  const games = [...new Set(S.queue.map(clipOfPath).filter(Boolean).map(c => c.game))];
  const d = new Date();
  return `${games.length === 1 ? games[0] : 'Highlights'} ${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}.${String(d.getMinutes()).padStart(2, '0')}`;
}

/* ---------- Merged ---------- */
function trackOfPath(p) { return p ? D.tracks.find(t => t.path.toLowerCase() === String(p).toLowerCase()) : null; }
function pageMerged() {
  if (!D.loaded.merged) return loadingPage('Merged');
  let h = `<div class="page"><div class="pagehead"><h1>Merged</h1><span class="sub num">${plural(D.merged.length, 'video')} in ${esc(D.roots.merged)}, ${size(D.merged.reduce((a, m) => a + m.size, 0))}</span></div>
   <div class="toolbar"><button class="btn ghost" data-action="open-folder" data-k="merged">${ic('folder')}Open folder</button><button class="btn ghost" data-action="refresh">${ic('refresh')}Refresh</button></div>`;
  if (!D.merged.length) h += `<div class="empty"><b>Nothing merged yet</b>Build a merge queue on the Shorts page, then choose Merge.</div>`;
  h += `<div class="mgrid">${D.merged.map(m => {
    const t = trackOfPath(m.music);
    return `<article class="mcard ${m.fmt}">
    <div class="thumb ${m.fmt === 'short' ? 'portrait' : ''}" data-action="play-merged" data-id="${m.id}"><img loading="lazy" src="${thumbUrl(m.path, 0.3, m.fmt === 'short' ? 360 : 640)}" alt=""><span class="dur num">${dur(m.len)}</span></div>
    <div class="info"><h3 title="${esc(m.name)}">${esc(m.name)}</h3>
     <dl class="facts num"><dt>Format</dt><dd>${m.fmt === 'short' ? 'Short, 9:16' : 'Long, 16:9'}, ${m.w}×${m.h}</dd><dt>Music</dt><dd title="${esc(m.music || '')}">${t ? esc(trackLabel(t)) : m.music ? esc(base(m.music)) : 'None'}</dd><dt>Made</dt><dd>${esc(when(m.ts))}</dd><dt>Size</dt><dd>${size(m.size)}</dd></dl>
     ${m.clips.length ? `<div class="chips">${m.clips.map(p => { const c = clipOfPath(p); return `<span class="chip" title="${esc(p)}">${esc(c ? c.title : base(p).replace(/\.mp4$/i, '') + (c ? '' : ''))}</span>`; }).join('')}</div>` : ''}
     <div class="mactions"><button class="btn sm" data-action="play-merged" data-id="${m.id}">${ic('play')}Play</button><button class="btn sm" data-action="desc" data-id="${m.id}">${ic('copy')}YouTube description</button>
      <button class="btn sm ghost" data-action="reveal" data-p="${esc(m.path)}">${ic('folder')}Show in folder</button>
      ${m.clips.length ? `<button class="btn sm ghost" data-action="remerge" data-id="${m.id}">${ic('retry')}Merge again</button>` : ''}
      <button class="btn sm ghost danger" data-action="del-merged" data-id="${m.id}">${ic('trash')}Delete</button></div></div></article>`; }).join('')}</div></div>`;
  return h;
}

/* ---------- Music ---------- */
function creditCell(t) {
  if (t.credit_state === 'ready') return `<span class="tpill st-done">${ic('check')}Credit ready</span>`;
  if (t.credit_state === 'none') return `<span class="tpill st-new">No credit needed</span>`;
  return `<button class="tpill st-processing btnlike" data-action="credit" data-id="${t.id}">${ic('warn')}Add credit</button>`;
}
function usedCount(t) { return D.merged.filter(m => m.music && m.music.toLowerCase() === t.path.toLowerCase()).length; }
function inLibrary(n) {
  const norm = s => String(s || '').toLowerCase().replace(/[^a-z0-9]/g, '');
  return D.tracks.some(t => (t.source_url && t.source_url.endsWith('/' + n.slug)) || (norm(t.title) === norm(n.title) && norm(t.artist) === norm(n.artist)));
}
function pageMusic() {
  if (!D.loaded.music) return loadingPage('Music');
  const missing = D.tracks.filter(t => t.credit_state === 'missing').length;
  const tabs = [['library', 'Library'], ['ncs', 'Find on NCS'], ['other', 'Other sources']];
  const watching = D.watch.waiting.length || D.watch.ytal;
  let h = `<div class="page"><div class="pagehead"><h1>Music</h1><span class="sub num">${plural(D.tracks.length, 'track')} in ${esc(D.roots.music)}${missing ? `, ${missing} without a credit line` : ''}</span></div>
   <div class="toolbar"><div class="seg" role="tablist">${tabs.map(([k, l]) => `<button role="tab" data-action="music-tab" data-v="${k}" aria-pressed="${S.musicTab === k}">${l}</button>`).join('')}</div><span class="grow"></span>
   <span class="watch">${watching ? `<span class="live-dot"></span>Watching Downloads for ${D.watch.waiting.length ? plural(D.watch.waiting.length, 'NCS track') : 'Audio Library downloads'}` : (S.settings.watch_downloads ? 'Get track adds the download here automatically' : 'Adding from Downloads is off (Settings)')}</span></div>`;
  if (S.musicTab === 'library') {
    if (!D.tracks.length) h += `<div class="empty"><b>No music yet</b>Find tracks on NCS, or import files you already have.<br><br><button class="btn primary" data-action="music-tab" data-v="ncs">Find on NCS</button></div>`;
    else h += `<div class="tablewrap wide"><table><thead><tr><th style="width:36px"></th><th style="width:44px"></th><th>Track</th><th>Source</th><th class="r">Length</th><th>Credit</th><th class="r">Used in</th><th></th></tr></thead><tbody>
      ${D.tracks.map(t => { const sel = S.sel.music.has(t.id), u = usedCount(t);
        return `<tr class="${sel ? 'selected' : ''}"><td><button class="boxchk" data-action="track-check" data-id="${t.id}" role="checkbox" aria-checked="${sel}" aria-label="Select">${ic('check')}</button></td>
        <td><button class="playbtn ${S.playing === t.path ? 'on' : ''}" data-action="play-local" data-id="${t.id}" aria-label="Play">${S.playing === t.path ? ic('pause') : ic('play')}</button></td>
        <td class="tt" style="max-width:340px"><b title="${esc(t.file)}">${esc(t.title || t.file)}</b><span>${esc(t.artist || 'Unknown artist')}</span></td><td>${esc(t.source)}</td><td class="r num">${dur(t.len)}</td><td>${creditCell(t)}</td>
        <td class="r num">${u ? plural(u, 'merge') : 'Not used'}</td><td><button class="btn sm ghost" data-action="credit" data-id="${t.id}">Edit</button></td></tr>`; }).join('')}</tbody></table></div>
      <p class="note" style="margin-top:10px">Tracks without a credit line can't be picked for a merge, so a video never goes up without its music credit.</p>`;
    h += `</div><div class="cmdbar ${S.sel.music.size ? '' : 'hide'}" role="toolbar"><span class="info"><strong>${S.sel.music.size} selected</strong></span><button class="btn danger" data-action="del-tracks">${ic('trash')}Delete${S.sel.music.size > 1 ? ` (${S.sel.music.size})` : ''}</button><button class="btn ghost" data-action="clear" data-kind="music">Clear</button></div>`;
    return h;
  }
  if (S.musicTab === 'ncs') {
    const items = S.ncsItems || [];
    const genres = ['all', ...new Set(items.map(n => n.genre).filter(Boolean))];
    const list = items.filter(n => S.genre === 'all' || n.genre === S.genre);
    h += `<div class="banner">${ic('music')}<p>Search NCS and preview tracks here. <b>Get track</b> opens the track's page on ncs.io in your browser. Click Download there, and Studio moves the file into your library with the credit line filled in.</p></div>
     <div class="toolbar"><label class="search">${ic('search')}<input id="ncsQ" type="text" placeholder="Search NCS, then press Enter" value="${esc(S.ncsQ)}" aria-label="Search NCS"></label>
      <button class="btn" data-action="ncs-search">Search</button>
      <select class="select" id="genreSel" aria-label="Genre">${genres.map(g => `<option value="${esc(g)}" ${S.genre === g ? 'selected' : ''}>${g === 'all' ? 'All genres' : esc(g)}</option>`).join('')}</select></div>`;
    if (S.ncsLoading) h += `<div class="loading">${ic('loader', 'spin')}Searching ncs.io…</div>`;
    else if (S.ncsError) h += `<div class="empty"><b>Search didn't work</b>${esc(S.ncsError)}</div>`;
    else if (!list.length) h += `<div class="empty"><b>No tracks match</b>Try another name or genre.</div>`;
    else h += `<div class="ncs-grid">${list.map(n => { const have = inLibrary(n), wait = D.watch.waiting.includes(n.slug), playing = S.playing === 'ncs:' + n.slug;
      return `<div class="tcard"><div class="cover">${n.cover ? `<img loading="lazy" src="${esc(n.cover)}" alt="">` : ''}<button class="playbtn ${playing ? 'on' : ''}" data-action="play-ncs" data-slug="${esc(n.slug)}" aria-label="Preview ${esc(n.title)}">${playing ? ic('pause') : ic('play')}</button></div>
       <div class="tt"><b title="${esc(n.title)}">${esc(n.title)}</b><span title="${esc(n.artist)}">${esc(n.artist)}</span></div><div class="chips">${n.genre ? `<span class="chip">${esc(n.genre)}</span>` : ''}${n.mood ? `<span class="chip">${esc(n.mood)}</span>` : ''}${n.len ? `<span class="chip num">${esc(n.len)}</span>` : ''}</div>
       ${have ? `<div class="inlib">${ic('check')}In your library</div>` : wait ? `<button class="btn" disabled>${ic('loader', 'spin')}Waiting for the download</button>` : `<button class="btn" data-action="get-ncs" data-slug="${esc(n.slug)}">Get track</button>`}</div>`; }).join('')}</div>`;
    return h + `</div>`;
  }
  const L = S.lookup;
  h += `<div class="srcgrid">
   <div class="srccard"><h3>${ic('play')}YouTube Audio Library</h3><p>YouTube's own free music. Tracks downloaded from it don't get Content ID claims. Some ask for a credit line, which the library shows next to the track.</p>
    <div><button class="btn" data-action="open-ytal">Open Audio Library</button></div><p class="note">Opens YouTube Studio in your browser. For the next 30 minutes, music you download is added here. Then fill in its credit, or mark it as not needing one.</p></div>
   <div class="srccard"><h3>${ic('link')}Check a link</h3><p>Paste a video from a music channel, such as a repost channel, to see who the original artist is and where to get the track legally.</p>
    <div class="row"><input type="text" id="linkIn" placeholder="https://youtube.com/watch?v=…" value="${esc(S.link)}" aria-label="Video link"><button class="btn" data-action="lookup" ${S.lookupBusy ? 'disabled' : ''}>${S.lookupBusy ? ic('loader', 'spin') : ''}Check</button></div>
    ${L ? (L.ok ? `<div class="lookup"><span><b>${esc(L.title)}</b><br><span class="note">Channel: ${esc(L.channel || 'unknown')}</span></span>
      ${L.found ? `<span>The description credits <b>${esc(L.found.artist)} - ${esc(L.found.track)}</b>${L.found.label ? ` [${esc(L.found.label)}]` : ''}.</span>` : '<span>No original artist is named in the description.</span>'}
      ${L.is_ncs ? `<span>This is an NCS track. Get it from NCS so you have the real file and its credit.</span><div><button class="btn sm primary" data-action="goto-ncs" data-q="${esc(L.found ? L.found.track : (L.ncs_slug || ''))}">Find it on NCS</button></div>`
        : `<span>This doesn't look like an NCS track. Only use it if the original artist's own license allows it, and keep their credit text.</span>`}</div>`
      : `<div class="lookup"><span class="badline">${ic('warn')}${esc(L.error)}</span></div>`) : ''}
    <p class="note">Studio doesn't pull audio out of YouTube videos. YouTube's terms don't allow it, and a repost's copy doesn't come with a license you can point to.</p></div>
   <div class="srccard"><h3>${ic('folder')}Import files</h3><p>Already have the file? Add MP3, M4A, WAV or FLAC files. They're copied into the library, then you fill in the credit line.</p>
    <div><button class="btn" data-action="import">Choose files</button></div></div>
  </div>`;
  return h + `</div>`;
}

/* ---------- Settings ---------- */
function pageSettings() {
  const st = S.settings, c = D.claude;
  const row = (t, s, ctl) => `<div class="srow"><div><b>${t}</b><span>${s}</span></div><div class="ctl">${ctl}</div></div>`;
  return `<div class="page"><div class="pagehead"><h1>Settings</h1></div><div class="settings">
   <div class="shead">Claude</div>
   ${row('Account', `Highlight runs use the account you're signed in to in the Claude Code CLI (${esc(c.path || 'claude')}). No API key is used.`,
     c.found ? (c.signed_in ? `<span class="okline">${ic('check')}Signed in</span>` : `<span class="badline">${ic('warn')}Run claude in a terminal to sign in</span>`) : `<span class="badline">${ic('warn')}Claude Code not found</span>`)}
   ${row('Model for Valorant', 'Valorant runs are mostly scripted, so a lighter model is enough. Other games use your default model.',
     `<select class="select" id="setModel"><option value="sonnet" ${st.valorant_model === 'sonnet' ? 'selected' : ''}>Sonnet</option><option value="default" ${st.valorant_model === 'default' ? 'selected' : ''}>Same as other games</option></select>`)}
   ${row('Highlight runs at the same time', 'Each recording gets its own agent. Running two at once is faster but heavier on the PC.',
     `<select class="select" id="setJobs">${[1, 2].map(n => `<option ${+st.jobs_at_once === n ? 'selected' : ''}>${n}</option>`).join('')}</select>`)}
   <div class="shead">Folders</div>
   ${row('Recordings', esc(D.roots.recordings) + '. Set by the pipeline.', `<button class="btn sm" data-action="open-folder" data-k="recordings">Open</button>`)}
   ${row('Shorts', esc(D.roots.highlights) + '. Set by the pipeline.', `<button class="btn sm" data-action="open-folder" data-k="highlights">Open</button>`)}
   ${row('Merged videos', esc(st.merged_root), `<button class="btn sm" data-action="open-folder" data-k="merged">Open</button><button class="btn sm" data-action="pick-folder" data-k="merged_root">Change</button>`)}
   ${row('Music library', esc(st.music_root), `<button class="btn sm" data-action="open-folder" data-k="music">Open</button><button class="btn sm" data-action="pick-folder" data-k="music_root">Change</button>`)}
   ${row('Add music from Downloads', 'After you choose Get track or Open Audio Library, music that lands in your Downloads folder is moved into the library. Other downloads are left alone.',
     `<button class="switch" data-action="set-watch" role="switch" aria-checked="${!!st.watch_downloads}" aria-label="Add music from Downloads"></button>`)}
   <div class="shead">Appearance</div>
   ${row('Theme', 'System follows your Windows setting.', `<div class="seg" role="group">${['system', 'light', 'dark'].map(t => `<button data-action="theme" data-v="${t}" aria-pressed="${(st.theme || 'system') === t}">${t[0].toUpperCase() + t.slice(1)}</button>`).join('')}</div>`)}
   <div class="shead">Troubleshooting</div>
   ${row('Job logs', 'Full output of every highlight run and merge.', `<button class="btn sm" data-action="open-folder" data-k="logs">Open logs</button>`)}
  </div></div>`;
}

/* ---------- flyouts ---------- */
function renderFlyout() {
  const host = $('#flyout');
  if (S.jobsOpen) {
    const act = D.jobs.filter(j => j.state === 'queued' || j.state === 'running'), done = D.jobs.filter(j => !(j.state === 'queued' || j.state === 'running'));
    const body = `${act.length ? `<div class="sectionlabel">Running</div>${act.map(jobCard).join('')}` : `<div class="qempty">Nothing running. Select recordings on Footage and choose Make highlights.</div>`}
     ${done.length ? `<div class="sectionlabel"><span>Finished</span><button class="linkbtn" data-action="clear-jobs">Clear</button></div>${done.map(jobCard).join('')}` : ''}`;
    // Only rebuild what changed: the elapsed clocks tick in place, so spinners, scroll and
    // the slide-in animation aren't restarted every second.
    const sig = body.replace(/data-el="[^"]*">[^<]*</g, '');
    const fly = host.querySelector('.flyout.jobs');
    if (!fly) {
      host.innerHTML = `<div class="flyout jobs" role="dialog" aria-label="Jobs"><div class="flyhead"><h2>Jobs</h2><button class="iconbtn" data-action="toggle-jobs" aria-label="Close">${ic('x')}</button></div><div class="flybody">${body}</div></div>`;
    } else if (fly.dataset.sig !== sig) {
      const fb = fly.querySelector('.flybody'), keep = fb.scrollTop;
      const reports = [...fb.querySelectorAll('.report')].map(r => r.scrollTop);
      fb.innerHTML = body; fb.scrollTop = keep;
      fb.querySelectorAll('.report').forEach((r, i) => { r.scrollTop = reports[i] || 0; });
    } else {
      for (const j of D.jobs) fly.querySelectorAll(`[data-el="${j.id}"]`).forEach(e => { e.textContent = dur(j.elapsed); });
    }
    host.querySelector('.flyout.jobs').dataset.sig = sig;
    return;
  }
  const c = S.detail && clipById.get(S.detail);
  if (!c) { S.detail = null; host.innerHTML = ''; return; }
  const s = setOfClip.get(c.id), q = S.queue.some(p => p.toLowerCase() === c.path.toLowerCase());
  const yt = (label, val, k) => val ? `<div class="yt-row"><div><small>${label}</small><p>${esc(val)}</p></div><button class="iconbtn" data-action="copy" data-k="${k}" aria-label="Copy ${label}">${ic('copy')}</button></div>` : '';
  const parts = c.parts && typeof c.parts === 'object' ? c.parts : null;
  const html = `<div class="flyout" role="dialog" aria-label="${esc(c.title)}"><div class="flyhead"><h2 title="${esc(c.title)}">${esc(c.title)}</h2><button class="iconbtn" data-action="close-detail" aria-label="Close">${ic('x')}</button></div>
   <div class="flybody"><div class="detail-player"><video controls preload="metadata" src="${mediaUrl(c.path)}"></video></div>
   <div class="cmeta num" style="padding:0">${c.score != null ? `<span>Score ${c.score}</span>` : ''}<span>${dur(c.len)}</span>${c.n != null ? `<span>#${String(c.n).padStart(2, '0')}</span>` : ''}<span>${esc(c.game)}</span>${c.used ? `<span>Used in ${plural(c.used, 'merge')}</span>` : ''}</div>
   ${parts ? `<div class="meters">${[['hook', 'Hook'], ['action', 'Action'], ['payoff', 'Payoff']].map(([k, l]) => `<div class="meter">${l} <span class="num">${parts[k] ?? '-'}/10</span><div><i style="width:${(parts[k] || 0) * 10}%"></i></div></div>`).join('')}</div>` : ''}
   ${c.title || c.desc || c.tags ? `<div class="sectionlabel">For YouTube</div><div class="yt">${yt('Title', c.title, 'title')}${yt('Description', c.desc, 'desc')}${yt('Hashtags', c.tags, 'tags')}${yt('Hook idea', c.hook, 'hook')}</div>` : ''}
   ${c.story ? `<div class="sectionlabel">What happens</div><p style="margin:0;font-size:13px;color:var(--fg2)">${esc(c.story)}</p>` : ''}
   <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn ${q ? '' : 'primary'}" data-action="${q ? 'q-remove' : 'add-one'}" data-p="${esc(c.path)}">${q ? ic('x') + 'Remove from queue' : ic('plus') + 'Add to merge queue'}</button>
    <button class="btn ghost" data-action="reveal" data-p="${esc(c.path)}">${ic('folder')}Show in folder</button><button class="btn ghost danger" data-action="del-one" data-id="${c.id}">${ic('trash')}Delete</button></div>
   <p class="note" style="margin:0">${esc(s ? s.label : '')}</p></div></div>`;
  // unchanged panel: leave it alone so a playing video keeps playing
  const cur = host.querySelector('.flyout');
  if (cur && cur.dataset.sig === html) return;
  host.innerHTML = html;
  host.querySelector('.flyout').dataset.sig = html;
}
function jobCard(j) {
  const steps = j.steps || [], si = Math.min(steps.length - 1, j.step || 0);
  const name = j.kind === 'merge' ? `Merge: ${esc(j.title)}` : esc(j.title);
  const sub = j.kind === 'merge' ? `${plural((j.clips || []).length, 'short')}${j.music ? ', ' + esc(base(j.music)) : ''}` : `Model: ${esc(j.model_used || j.model)}`;
  const el = dur(j.elapsed);
  if (j.state === 'queued') return `<div class="job"><div class="top">${ic('activity')}<div class="grow"><b>${name}</b><span>${sub}. Waiting for the current job.</span></div><button class="btn sm ghost" data-action="cancel" data-id="${j.id}">Cancel</button></div></div>`;
  if (j.state === 'running') return `<div class="job"><div class="top">${ic('loader', 'spin')}<div class="grow"><b>${name}</b><span>${sub}, <span class="num" data-el="${j.id}">${el}</span> so far</span></div><button class="btn sm ghost" data-action="cancel" data-id="${j.id}">Cancel</button></div>
    <div class="steps">${steps.map((s, i) => `<i class="${i < si ? 'done' : i === si ? 'now' : ''}"></i>`).join('')}</div>
    <div class="stepname"><span title="${esc(j.activity)}">Step ${si + 1} of ${steps.length}: ${esc(steps[si])}. ${esc(j.activity || '')}</span></div></div>`;
  const u = j.usage;
  const usage = u ? `${u.tokens ? `${Math.round(u.tokens / 1000)}k tokens` : ''}${u.turns ? `, ${u.turns} turns` : ''}` : '';
  if (j.state === 'done') {
    const acts = j.kind === 'merge' ? `<button class="btn sm" data-action="nav" data-page="merged">Open Merged</button>${j.out ? `<button class="btn sm ghost" data-action="reveal" data-p="${esc(j.out)}">Show in folder</button>` : ''}`
      : `<button class="btn sm" data-action="nav" data-page="shorts">View shorts</button>`;
    return `<div class="job"><div class="top"><span class="ok">${ic('check')}</span><div class="grow"><b>${name}</b><span>${j.kind === 'merge' ? 'Saved' : `${j.clips != null ? plural(j.clips, 'short') : 'Done'}`}, took ${el}${usage ? ', ' + usage : ''}</span></div></div>
      ${j.report ? `<div class="report">${esc(j.report)}</div>` : ''}<div class="jobacts">${acts}</div></div>`;
  }
  const retry = j.kind === 'highlight' && j.state === 'failed' ? `<button class="btn sm" data-action="retry" data-p="${esc(j.path)}">${ic('retry')}Retry</button>` : '';
  return `<div class="job"><div class="top"><span class="bad">${ic('warn')}</span><div class="grow"><b>${name}</b><span>${j.state === 'cancelled' ? 'Cancelled' : 'Failed'} after ${el}${usage ? ', ' + usage : ''}</span></div></div>
    ${j.error && j.state !== 'cancelled' ? `<div class="report bad">${esc(j.error)}</div>` : ''}<div class="jobacts">${retry}<button class="btn sm ghost" data-action="open-folder" data-k="logs">Open logs</button></div></div>`;
}

/* ---------- dialogs and toasts ---------- */
const dlg = $('#dlg');
function openDialog(html, cls = '') { dlg.className = cls; dlg.innerHTML = html; if (!dlg.open) dlg.showModal(); }
function closeDialog() { dlg.querySelectorAll('video,audio').forEach(v => { try { v.pause(); } catch (_) {} }); if (dlg.open) dlg.close(); dlg.innerHTML = ''; }
dlg.addEventListener('close', () => { dlg.querySelectorAll('video').forEach(v => { try { v.pause(); v.removeAttribute('src'); v.load(); } catch (_) {} }); });
let toastT;
function toast(msg, sub, action) {
  clearTimeout(toastT);
  $('#toastHost').innerHTML = `<div class="toast" role="status"><div>${esc(msg)}${sub ? `<small>${esc(sub)}</small>` : ''}</div>${action ? `<button class="btn" data-action="${action[1]}" data-page="${action[2] || ''}">${esc(action[0])}</button>` : ''}<button class="btn" data-action="toast-x" aria-label="Dismiss">${ic('x')}</button></div>`;
  toastT = setTimeout(() => { $('#toastHost').innerHTML = ''; }, 7000);
}
function deleteDialog(kind, items) {
  let title, body, rows, warn = '';
  if (kind === 'footage') {
    const unp = items.filter(r => r.status !== 'done');
    title = `Delete ${plural(items.length, 'recording')}?`;
    body = `They go to the Recycle Bin. ${size(items.reduce((a, r) => a + r.size, 0))} is freed when you empty it.`;
    rows = items.map(r => `<div><span title="${esc(r.file)}">${esc(r.file)}</span><span class="num">${r.status !== 'done' ? '<span class="tag">No highlights yet</span> ' : ''}${size(r.size)}</span></div>`).join('');
    if (unp.length) warn = `<div class="warnbox">${ic('warn')}<span>${unp.length === 1 ? '1 of these has' : `${unp.length} of these have`} no highlights yet. After the Recycle Bin is emptied, nothing will be left from ${unp.length === 1 ? 'it' : 'them'}.</span></div>`;
  } else if (kind === 'shorts') {
    title = `Delete ${plural(items.length, 'short')}?`; body = 'Each video and its YouTube text file go to the Recycle Bin.';
    rows = items.map(c => `<div><span>${esc(c.title)}</span><span class="num">${dur(c.len)}</span></div>`).join('');
    const q = items.filter(c => S.queue.some(p => p.toLowerCase() === c.path.toLowerCase())).length;
    if (q) warn = `<div class="warnbox">${ic('warn')}<span>${q === 1 ? '1 is' : `${q} are`} in the merge queue and will be removed from it.</span></div>`;
  } else if (kind === 'merged') {
    title = `Delete "${items[0].name}"?`; body = 'The merged video goes to the Recycle Bin. The shorts it was made from stay.';
    rows = items.map(m => `<div><span>${esc(m.name)}.mp4</span><span class="num">${size(m.size)}</span></div>`).join('');
  } else {
    title = `Delete ${plural(items.length, 'track')}?`; body = 'The files go to the Recycle Bin. Videos you already merged keep their music.';
    rows = items.map(t => `<div><span>${esc(t.file)}</span><span class="num">${dur(t.len)}</span></div>`).join('');
  }
  S.pendingDelete = {kind, paths: items.map(x => x.path)};
  openDialog(`<div class="dlg-body"><h2>${esc(title)}</h2><p>${body}</p><div class="dlg-list">${rows}</div>${warn}</div>
   <div class="dlg-foot"><button class="btn danger-solid" data-action="confirm-del">Move to Recycle Bin</button><button class="btn" data-action="dlg-close" autofocus>Cancel</button></div>`);
}
async function doDelete() {
  const {kind, paths} = S.pendingDelete || {}; if (!kind) return;
  closeDialog();
  const res = await API().trash(kind, paths);
  const ok = res.filter(r => r.ok), bad = res.filter(r => !r.ok);
  const freed = ok.reduce((a, r) => a + (r.size || 0), 0);
  const noun = {footage: 'recording', shorts: 'short', merged: 'merged video', music: 'track'}[kind];
  if (kind === 'shorts') { const gone = new Set(ok.map(r => r.path.toLowerCase())); S.queue = S.queue.filter(p => !gone.has(p.toLowerCase())); saveQueue(); S.sel.shorts.clear(); if (S.detail && !clipById.get(S.detail)) S.detail = null; S.detail = null; }
  if (kind === 'footage') S.sel.footage.clear();
  if (kind === 'music') S.sel.music.clear();
  toast(ok.length ? `Moved ${plural(ok.length, noun)} to the Recycle Bin` : `Nothing was deleted`,
    bad.length ? `${bad.length} skipped: ${bad.map(b => `${base(b.path)} (${b.reason})`).join(', ').slice(0, 200)}` : (freed ? `${size(freed)} is freed when you empty the Recycle Bin.` : ''));
  await Promise.all([kind === 'footage' ? loadFootage() : null, kind === 'shorts' ? loadShorts() : null, kind === 'merged' ? Promise.all([loadMerged(), loadShorts()]) : null,
    kind === 'music' ? loadMusic() : null, loadDisk()].filter(Boolean));
  render();
}
function playerDialog(name, path, portrait) {
  openDialog(`<div class="player ${portrait ? 'portrait' : ''}"><video controls autoplay src="${mediaUrl(path)}"></video>
   <div class="pbar"><b title="${esc(name)}">${esc(name)}</b><button class="btn sm ghost" data-action="reveal" data-p="${esc(path)}">${ic('folder')}Show in folder</button><button class="iconbtn" data-action="dlg-close" aria-label="Close">${ic('x')}</button></div></div>`, 'player' + (portrait ? ' portrait' : ''));
}
async function previewDialog() {
  openDialog(`<div class="dlg-body"><h2>Preview cuts</h2><div class="loading">${ic('loader', 'spin')}Finding the action in each short and syncing to the music. This can take a minute…</div></div>
   <div class="dlg-foot"><button class="btn" data-action="dlg-close">Close</button></div>`);
  const r = await API().preview(mergeOpts());
  if (!dlg.open) return;
  if (!r.ok) { openDialog(`<div class="dlg-body"><h2>Preview didn't work</h2><div class="report bad">${esc(r.error)}</div></div><div class="dlg-foot"><button class="btn" data-action="dlg-close">Close</button></div>`); return; }
  S.previewMusic = r.music;
  const t = trackOfPath(r.music);
  const rows = r.clips.map((c, i) => { const cl = clipOfPath(c.file); return `<tr><td class="num">${i + 1}</td><td style="max-width:220px;overflow:hidden;text-overflow:ellipsis">${esc(cl ? cl.title : base(c.file))}</td><td class="num">${dur(c.in)} to ${dur(c.out)}</td><td class="r num">${(c.out - c.in).toFixed(1)}s</td><td class="num">${dur(c.starts_at)}</td><td>${esc(c.transition_in || 'fade in')}</td></tr>`; }).join('');
  const dropped = S.queue.length - r.clips.length;
  openDialog(`<div class="dlg-body"><h2>Preview cuts</h2><p>What the merge keeps from each short, cut to the beat. Nothing is encoded yet.</p>
   <div class="tablewrap"><table><thead><tr><th>#</th><th>Short</th><th>Keeps</th><th class="r">Length</th><th>Starts at</th><th>Transition</th></tr></thead><tbody>${rows}</tbody></table></div>
   <p class="num">Final length about <b>${dur(r.length)}</b>${r.music ? `, music: <b>${esc(t ? trackLabel(t) : base(r.music))}</b>${r.bpm ? ` (${r.bpm} BPM)` : ''}` : ''}.</p>
   ${dropped > 0 ? `<div class="warnbox">${ic('warn')}<span>${plural(dropped, 'short')} with the lowest score ${dropped === 1 ? 'was' : 'were'} dropped to fit the 3:00 Short limit.</span></div>` : ''}</div>
   <div class="dlg-foot"><button class="btn primary" data-action="merge-preview">Merge like this</button><button class="btn" data-action="dlg-close">Close</button></div>`);
}
async function doMerge(music) {
  closeDialog();
  const r = await API().merge(mergeOpts(music));
  if (!r.ok) { toast("Can't merge yet", r.error); return; }
  toast('Merge started', 'It runs in the background. Watch it under Jobs.');
  S.queue = []; saveQueue(); S.merge.name = ''; S.jobsOpen = true; S.detail = null;
  await pollJobs(); render();
}
function creditDialog(t) {
  S.creditFile = t.file;
  openDialog(`<div class="dlg-body"><h2>Credit for "${esc(t.title || t.file)}"</h2><p>This text goes into the YouTube description of every merge that uses this track.</p>
   <div class="form"><div class="two"><label>Title<input type="text" id="cTitle" value="${esc(t.title)}"></label><label>Artist<input type="text" id="cArtist" value="${esc(t.artist)}"></label></div>
    <label>Source<select id="cSource">${['NCS', 'YouTube Audio Library', 'Imported file', 'Other'].map(s => `<option ${t.source === s ? 'selected' : ''}>${s}</option>`).join('')}</select></label>
    <label>Credit line<textarea id="cText" placeholder="For NCS, copy the credit block from the track's ncs.io page. For the YouTube Audio Library, copy the attribution text if the track has one.">${esc(t.credit || '')}</textarea></label>
    <label class="checkline"><input type="checkbox" id="cNone" ${t.no_credit ? 'checked' : ''}> This track doesn't need a credit (its source says so)</label></div></div>
   <div class="dlg-foot"><button class="btn primary" data-action="credit-save">Save</button><button class="btn" data-action="dlg-close">Cancel</button></div>`);
}
function descDialog(m) {
  const cs = m.clips.map(clipOfPath).filter(Boolean), t = trackOfPath(m.music);
  const tags = [...new Set(cs.flatMap(c => String(c.tags || '').split(/\s+/)).filter(x => x.startsWith('#')))].slice(0, 8).join(' ');
  let credit = '', warn = '';
  if (t && t.credit_state === 'ready') credit = t.credit;
  else if (m.music && !t) warn = `The music (${base(m.music)}) isn't in your library any more, so its credit isn't known. Add it yourself before posting.`;
  else if (t && t.credit_state === 'missing') warn = `"${trackLabel(t)}" has no credit line. Add one on the Music page first.`;
  const lines = cs.length > 1 ? cs.map(c => '• ' + c.title).join('\n') : (cs[0] ? cs[0].desc || '' : '');
  const txt = [m.name, lines, credit, tags].filter(Boolean).join('\n\n');
  openDialog(`<div class="dlg-body"><h2>YouTube description</h2><p>Built from the shorts' text and the music credit. Edit it before copying if you like.</p>
   ${warn ? `<div class="warnbox">${ic('warn')}<span>${esc(warn)}</span></div>` : ''}
   <div class="form"><textarea id="descTxt" style="min-height:240px">${esc(txt)}</textarea></div></div>
   <div class="dlg-foot"><button class="btn primary" data-action="copy-desc">${ic('copy')}Copy</button><button class="btn" data-action="dlg-close">Close</button></div>`);
}
async function copyText(text, el) {
  try { await navigator.clipboard.writeText(text); toast('Copied'); }
  catch (_) {
    const ta = el || Object.assign(document.createElement('textarea'), {value: text});
    if (!el) document.body.appendChild(ta);
    ta.select(); const ok = document.execCommand('copy'); if (!el) ta.remove();
    toast(ok ? 'Copied' : 'Press Ctrl+C to copy the selected text');
  }
}

/* ---------- jobs polling ---------- */
async function pollJobs() {
  let r; try { r = await API().jobs(); } catch (_) { return; }
  D.jobs = r.jobs; D.watch = r.watch;
  let reloadF = false, reloadS = false, reloadM = false;
  for (const j of D.jobs) {
    const prev = prevJobState.get(j.id);
    if (prev && prev !== j.state) {
      if (j.state === 'running' && j.kind === 'highlight') reloadF = true;
      if (j.state === 'done') {
        if (j.kind === 'highlight') { reloadF = reloadS = true; toast(`${j.title}: ${j.clips != null ? plural(j.clips, 'short') : 'done'}`, 'Highlights are ready.', ['View shorts', 'nav', 'shorts']); }
        else { reloadM = reloadS = true; toast(`Merged "${j.title}"`, `Saved to ${D.roots.merged}`, ['Open Merged', 'nav', 'merged']); }
      } else if (j.state === 'failed') { reloadF = true; toast(`${j.kind === 'merge' ? 'Merge' : 'Highlight run'} failed: ${j.title}`, String(j.error || '').slice(0, 160), ['Show jobs', 'show-jobs']); }
      else if (j.state === 'cancelled') reloadF = true;
    }
    prevJobState.set(j.id, j.state);
  }
  if (r.music_added && r.music_added.length) {
    await loadMusic();
    const a = r.music_added[0];
    toast(`Added "${a.title}" to your music`, a.credit_state === 'ready' ? 'Credit line filled in from ncs.io.' : 'Add its credit line before using it in a merge.', ['Open library', 'music-lib']);
    if (S.page === 'music' || S.queueOpen) render();
  }
  await Promise.all([reloadF && loadFootage(), reloadS && loadShorts(), reloadM && loadMerged()].filter(Boolean));
  if (reloadF || reloadS || reloadM) { loadDisk(); render(); return; }
  softUpdate();
}
/* update the parts that change every second without rebuilding the page (keeps hover and scroll) */
function softUpdate() {
  renderTop();
  if (S.jobsOpen) renderFlyout();
  if (S.page === 'footage') {
    for (const r of D.footage) {
      const j = jobFor(r.path); if (!j || j.state !== 'running') continue;
      const card = document.querySelector(`.card[data-id="${r.id}"]`); if (!card) continue;
      const bar = card.querySelector('.progress i'); if (bar) bar.style.width = jobPct(j) + '%'; else return render();
      const p = card.querySelector('.pill'), np = pill(r);
      if (p && p.dataset.html !== np) { p.outerHTML = np; const q = card.querySelector('.pill'); if (q) q.dataset.html = np; }
    }
  }
}

/* ---------- events ---------- */
function setTheme(t) { if (t === 'system') document.documentElement.removeAttribute('data-theme'); else document.documentElement.setAttribute('data-theme', t); }
async function playAudio(key, url) {
  const a = $('#audio');
  if (S.playing === key) { a.pause(); S.playing = null; render(); return; }
  a.src = url; S.playing = key;
  try { await a.play(); } catch (_) { S.playing = null; toast("Couldn't play that track"); }
  render();
}
$('#audio').addEventListener('ended', () => { S.playing = null; render(); });

document.addEventListener('click', async e => {
  const t = e.target.closest('[data-action]'); if (!t) return;
  const a = t.dataset.action, id = t.dataset.id, kind = t.dataset.kind;
  switch (a) {
    case 'nav': S.page = t.dataset.page; S.q = ''; S.detail = null; S.jobsOpen = false; $('#toastHost').innerHTML = ''; closeDialog();
      if (S.page === 'shorts' && !S.queueOpen && S.queue.length) S.queueOpen = true;
      if (S.page === 'music' && S.musicTab === 'ncs' && !S.ncsItems) ncsSearch();
      API().settings_set({last_page: S.page}); render(); $('#main').scrollTop = 0; break;
    case 'toggle-queue': S.queueOpen = !S.queueOpen; render(); break;
    case 'toggle-jobs': S.jobsOpen = !S.jobsOpen; S.detail = null; render(); break;
    case 'show-jobs': S.jobsOpen = true; S.detail = null; $('#toastHost').innerHTML = ''; render(); break;
    case 'clear-jobs': await API().clear_jobs(); await pollJobs(); render(); break;
    case 'view': S.view = t.dataset.view; lsSet('view', S.view); render(); break;
    case 'refresh': t.disabled = true; await Promise.all([loadFootage(), loadShorts(), loadMerged(), loadMusic(), loadDisk()]); render(); toast('Folders scanned again'); break;
    case 'collapse': { const g = t.dataset.g; S.collapsed.has(g) ? S.collapsed.delete(g) : S.collapsed.add(g); lsSet('collapsed', [...S.collapsed]); render(); break; }
    case 'check': { e.stopPropagation(); const s = S.sel[kind]; s.has(id) ? s.delete(id) : s.add(id); render(); break; }
    case 'card': { const r = recById.get(id); if (!r) break;
      if (!selectable(r)) { toast(effStatus(r) === 'recording' ? 'This file is still being recorded' : 'This recording is being processed', 'Wait for it to finish before selecting it.'); break; }
      const s = S.sel.footage; s.has(id) ? s.delete(id) : s.add(id); render(); break; }
    case 'open-clip': S.detail = id; S.jobsOpen = false; render(); break;
    case 'close-detail': S.detail = null; render(); break;
    case 'sel-group': { const rs = D.footage.filter(r => r.game === t.dataset.g && selectable(r) && (t.dataset.mode === 'all' || runnable(r)));
      const all = rs.length && rs.every(r => S.sel.footage.has(r.id)); rs.forEach(r => all ? S.sel.footage.delete(r.id) : S.sel.footage.add(r.id)); render(); break; }
    case 'sel-set': { const s = D.sets.find(x => x.id === id); if (!s) break; const all = s.clips.every(c => S.sel.shorts.has(c.id)); s.clips.forEach(c => all ? S.sel.shorts.delete(c.id) : S.sel.shorts.add(c.id)); render(); break; }
    case 'clear': S.sel[kind].clear(); render(); break;
    case 'make': { const rs = [...S.sel.footage].map(i => recById.get(i)).filter(r => r && runnable(r));
      const n = await API().make_highlights(rs.map(r => r.path)); S.sel.footage.clear();
      toast(n ? `Started ${plural(n, 'highlight job')}` : 'Nothing new to start', n ? 'Each recording gets its own agent, one at a time.' : '');
      S.jobsOpen = !!n; await pollJobs(); render(); break; }
    case 'retry': { const n = await API().make_highlights([t.dataset.p]); toast(n ? 'Retrying' : "Couldn't retry", n ? 'The recording is reset and runs again.' : 'It may already be queued.'); await pollJobs(); render(); break; }
    case 'cancel': await API().cancel_job(id); toast('Stopping the job', 'A stopped highlight run is marked failed. Use Retry to run it again.'); await pollJobs(); render(); break;
    case 'del-footage': deleteDialog('footage', [...S.sel.footage].map(i => recById.get(i)).filter(Boolean)); break;
    case 'del-shorts': deleteDialog('shorts', [...S.sel.shorts].map(i => clipById.get(i)).filter(Boolean)); break;
    case 'del-one': deleteDialog('shorts', [clipById.get(id)].filter(Boolean)); break;
    case 'del-merged': deleteDialog('merged', [D.merged.find(m => m.id === id)].filter(Boolean)); break;
    case 'del-tracks': deleteDialog('music', [...S.sel.music].map(i => D.tracks.find(x => x.id === i)).filter(Boolean)); break;
    case 'confirm-del': await doDelete(); break;
    case 'dlg-close': closeDialog(); break;
    case 'add-queue': { const add = [...S.sel.shorts].map(i => clipById.get(i)).filter(c => c && !S.queue.some(p => p.toLowerCase() === c.path.toLowerCase()));
      S.queue.push(...add.map(c => c.path)); S.sel.shorts.clear(); S.queueOpen = true; saveQueue(); render(); toast(`Added ${add.length} to the merge queue`, 'Drag them in the queue to change the order.'); break; }
    case 'add-one': if (!S.queue.some(p => p.toLowerCase() === t.dataset.p.toLowerCase())) S.queue.push(t.dataset.p); S.queueOpen = true; saveQueue(); render(); break;
    case 'q-remove': S.queue = S.queue.filter(p => p.toLowerCase() !== t.dataset.p.toLowerCase()); saveQueue(); render(); break;
    case 'q-clear': S.queue = []; saveQueue(); render(); break;
    case 'fmt': S.merge.fmt = t.dataset.v; saveMergeOpts(); render(); break;
    case 'hq': S.merge.hq = !S.merge.hq; saveMergeOpts(); render(); break;
    case 'preview': previewDialog(); break;
    case 'merge': doMerge(); break;
    case 'merge-preview': doMerge(S.previewMusic); break;
    case 'remerge': { const m = D.merged.find(x => x.id === id); const ok = m.clips.filter(p => clipOfPath(p));
      S.queue = ok; S.merge.fmt = m.fmt; S.merge.name = m.name + ' v2'; saveQueue(); S.page = 'shorts'; S.queueOpen = true; render();
      toast(`Loaded ${plural(ok.length, 'short')} from "${m.name}" into the queue`, ok.length < m.clips.length ? `${m.clips.length - ok.length} no longer exist.` : 'Change the order or settings, then merge.'); break; }
    case 'play-merged': { const m = D.merged.find(x => x.id === id); if (m) playerDialog(m.name, m.path, m.fmt === 'short'); break; }
    case 'reveal': API().reveal(t.dataset.p); break;
    case 'open-folder': API().open_folder(t.dataset.k); break;
    case 'pick-folder': { const r = await API().pick_folder(t.dataset.k); if (r) { const init = await API().init(); D.roots = init.roots; S.settings = init.settings; await Promise.all([loadMerged(), loadMusic()]); render(); } break; }
    case 'copy': { const c = clipById.get(S.detail); if (c) copyText({title: c.title, desc: c.desc, tags: c.tags, hook: c.hook}[t.dataset.k] || ''); break; }
    case 'desc': { const m = D.merged.find(x => x.id === id); if (m) descDialog(m); break; }
    case 'copy-desc': copyText($('#descTxt').value, $('#descTxt')); break;
    case 'theme': S.settings.theme = t.dataset.v; setTheme(t.dataset.v); API().settings_set({theme: t.dataset.v}); render(); break;
    case 'set-watch': S.settings.watch_downloads = !S.settings.watch_downloads; API().settings_set({watch_downloads: S.settings.watch_downloads}); render(); break;
    case 'music-tab': S.musicTab = t.dataset.v; if (S.musicTab === 'ncs' && !S.ncsItems) ncsSearch(); render(); break;
    case 'music-lib': S.page = 'music'; S.musicTab = 'library'; $('#toastHost').innerHTML = ''; render(); break;
    case 'track-check': { const s = S.sel.music; s.has(id) ? s.delete(id) : s.add(id); render(); break; }
    case 'play-local': { const tr = D.tracks.find(x => x.id === id); if (tr) playAudio(tr.path, mediaUrl(tr.path)); break; }
    case 'play-ncs': { const slug = t.dataset.slug, key = 'ncs:' + slug;
      if (S.playing === key) { playAudio(key); break; }
      t.disabled = true; const info = await API().ncs_track(slug); t.disabled = false;
      if (info.ok && info.preview) playAudio(key, info.preview); else toast('No preview for this track', info.error || ''); break; }
    case 'ncs-search': S.ncsQ = ($('#ncsQ') || {}).value || ''; ncsSearch(); break;
    case 'get-ncs': { const n = (S.ncsItems || []).find(x => x.slug === t.dataset.slug); if (!n) break;
      if (!S.settings.watch_downloads) toast('Adding from Downloads is off', 'Turn it on in Settings, or import the file yourself after downloading.');
      await API().ncs_get(n); toast(`Opened "${n.title}" on ncs.io`, 'Click Download on that page. Studio adds the file when it lands in Downloads.'); await pollJobs(); render(); break; }
    case 'goto-ncs': S.musicTab = 'ncs'; S.ncsQ = t.dataset.q || ''; ncsSearch(); break;
    case 'lookup': { S.link = ($('#linkIn') || {}).value || ''; if (!S.link.trim()) { toast('Paste a video link first'); break; }
      S.lookupBusy = true; render(); S.lookup = await API().check_link(S.link); S.lookupBusy = false; render(); break; }
    case 'open-ytal': await API().open_ytal(); toast("Opened YouTube Studio's Audio Library", 'Music you download there in the next 30 minutes is added here.'); await pollJobs(); render(); break;
    case 'import': { const added = await API().music_import(); if (!added || !added.length) break; await loadMusic(); S.musicTab = 'library'; render();
      toast(`Imported ${plural(added.length, 'track')}`); const first = added.find(x => x.credit_state === 'missing'); if (first) { const tr = D.tracks.find(x => x.file === first.file); if (tr) creditDialog(tr); } break; }
    case 'credit': { const tr = D.tracks.find(x => x.id === id); if (tr) creditDialog(tr); break; }
    case 'credit-save': { const none = $('#cNone').checked, text = $('#cText').value.trim();
      await API().music_save(S.creditFile, $('#cTitle').value.trim(), $('#cArtist').value.trim(), $('#cSource').value, text, none);
      closeDialog(); await loadMusic(); render(); toast(!none && !text ? 'Saved without a credit line' : 'Credit saved', !none && !text ? "This track can't be used in merges until it has one." : ''); break; }
    case 'toast-x': $('#toastHost').innerHTML = ''; break;
  }
});
async function ncsSearch() {
  S.ncsLoading = true; S.ncsError = ''; render();
  const r = await API().ncs_search(S.ncsQ);
  S.ncsLoading = false; if (r.ok) { S.ncsItems = r.items; S.genre = 'all'; } else { S.ncsError = r.error; S.ncsItems = S.ncsItems || []; }
  render();
}
document.addEventListener('dblclick', e => {
  const c = e.target.closest('.card'); if (!c || e.target.closest('.chk')) return;
  if (c.dataset.kind === 'footage') { const r = recById.get(c.dataset.id); if (r) playerDialog(r.file, r.path, false); }
  if (c.dataset.kind === 'shorts') { const x = clipById.get(c.dataset.id); if (x) playerDialog(x.title, x.path, false); }
});
document.addEventListener('input', e => {
  if (e.target.id === 'q') { S.q = e.target.value; const pos = e.target.selectionStart; render(); const q = $('#q'); if (q) { q.focus(); q.setSelectionRange(pos, pos); } }
  if (e.target.id === 'outName') S.merge.name = e.target.value;
  if (e.target.id === 'linkIn') S.link = e.target.value;
  if (e.target.id === 'ncsQ') S.ncsQ = e.target.value;
});
document.addEventListener('keydown', e => {
  if (e.target.id === 'ncsQ' && e.key === 'Enter') { ncsSearch(); return; }
  if (e.target.id === 'linkIn' && e.key === 'Enter') { document.querySelector('[data-action="lookup"]')?.click(); return; }
  if (e.target.matches('input,select,textarea') || dlg.open) return;
  if (e.key === 'Escape') { if (S.detail || S.jobsOpen) { S.detail = null; S.jobsOpen = false; render(); } }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a' && (S.page === 'footage' || S.page === 'shorts')) {
    e.preventDefault();
    if (S.page === 'footage') filteredRecs().filter(selectable).forEach(r => S.sel.footage.add(r.id)); else D.sets.forEach(s => s.clips.forEach(c => S.sel.shorts.add(c.id)));
    render();
  }
  if (e.key === 'Delete') {
    if (S.page === 'footage' && S.sel.footage.size) document.querySelector('[data-action="del-footage"]')?.click();
    if (S.page === 'shorts' && S.sel.shorts.size) document.querySelector('[data-action="del-shorts"]')?.click();
  }
});
document.addEventListener('change', e => {
  const id = e.target.id;
  if (id === 'statusSel') { S.status = e.target.value; render(); }
  if (id === 'sortSel') { S.sort = e.target.value; lsSet('sort', S.sort); render(); }
  if (id === 'minScore') { S.minScore = +e.target.value; render(); }
  if (id === 'styleSel') { S.merge.style = e.target.value; saveMergeOpts(); }
  if (id === 'musicSel') { S.merge.music = e.target.value; saveMergeOpts(); }
  if (id === 'genreSel') { S.genre = e.target.value; render(); }
  if (id === 'setModel') { S.settings.valorant_model = e.target.value; API().settings_set({valorant_model: e.target.value}); }
  if (id === 'setJobs') { S.settings.jobs_at_once = +e.target.value; API().settings_set({jobs_at_once: +e.target.value}); }
});
/* hover scrub: 8 frames across the video, generated on first hover and cached */
let scrubEl = null;
document.addEventListener('mousemove', e => {
  const th = e.target.closest('.thumb[data-scrub]');
  if (scrubEl && scrubEl !== th) { const img = scrubEl.querySelector('img'); if (img) img.src = img.dataset.src; scrubEl = null; }
  if (!th) return;
  const p = th.dataset.p, img = th.querySelector('img'); if (!img || !p) return;
  if (scrubEl !== th) { scrubEl = th; for (let i = 0; i < 8; i++) { const im = new Image(); im.src = frameUrl(p, i); } }
  const b = th.getBoundingClientRect(), f = Math.max(0, Math.min(0.999, (e.clientX - b.left) / b.width));
  const idx = Math.floor(f * 8), want = frameUrl(p, idx);
  if (img.getAttribute('src') !== want) img.src = want;
  const sc = th.querySelector('.scrub'); if (sc) sc.style.left = (f * 100) + '%';
  const st = th.querySelector('.scrubtime'); if (st) st.textContent = dur(+th.dataset.scrub * (idx + 0.5) / 8);
});

/* ---------- boot ---------- */
async function boot() {
  const init = await API().init();
  K = init.token; D.disk = init.disk; D.claude = init.claude; D.roots = init.roots; S.settings = init.settings;
  setTheme(S.settings.theme || 'system');
  S.page = ['footage', 'shorts', 'merged', 'music', 'settings'].includes(S.settings.last_page) ? S.settings.last_page : 'footage';
  Object.assign(S.merge, S.settings.merge || {});
  S.queue = lsGet('queue', []); S.view = lsGet('view', 'grid'); S.sort = lsGet('sort', 'newest'); S.collapsed = new Set(lsGet('collapsed', []));
  const open = /open=([a-z]+)(?::([a-z]+))?/.exec(location.hash || '');
  if (open) { S.page = open[1]; if (open[2] === 'queue') S.queueOpen = true; else if (open[2] === 'jobs') S.jobsOpen = true; else if (open[2]) S.musicTab = open[2]; }
  S.queueOpen = S.queueOpen || (S.page === 'shorts' && S.queue.length > 0);
  render();
  await pollJobs();
  await Promise.all([loadFootage().then(render), loadShorts().then(render), loadMerged(), loadMusic()]);
  render();
  if (S.page === 'music' && S.musicTab === 'ncs') ncsSearch();
  setInterval(pollJobs, 1000);
  setInterval(loadDisk, 30000);
  setInterval(async () => {  // pick up new or finished recordings without a manual refresh
    if (S.page !== 'footage' || dlg.open || document.querySelector('.card:hover')) return;
    const before = JSON.stringify(D.footage.map(r => [r.id, r.status, r.size]));
    await loadFootage();
    if (JSON.stringify(D.footage.map(r => [r.id, r.status, r.size])) !== before) render();
  }, 20000);
}
if (window.pywebview && window.pywebview.api) boot(); else window.addEventListener('pywebviewready', boot);
})();
