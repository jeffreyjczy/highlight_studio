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
 expand:'<path d="M3 7.5V3h4.5M17 7.5V3h-4.5M3 12.5V17h4.5M17 12.5V17h-4.5"/>',
 book:'<path d="M3.5 4.5c2-1 4.5-1 6.5.5 2-1.5 4.5-1.5 6.5-.5v11c-2-1-4.5-1-6.5.5-2-1.5-4.5-1.5-6.5-.5z"/><path d="M10 5v11"/>',
};
const ic = (n, cls = '') => `<svg class="ic ${cls}" viewBox="0 0 20 20" aria-hidden="true">${P[n]}</svg>`;

/* ---------- state ---------- */
let K = '';
const DEMO = /demo/.test(location.hash);  // dev only: --open page:demo fills queue and jobs with long sample labels
const DEMO_JOBS = [
  {id: 'demo1', kind: 'highlight', state: 'running', path: 'demo', title: 'Valorant 2026.08.01 - 16.15.54.03', model: 'sonnet', step: 3,
   steps: ['Claim', 'Probe', 'Analyze', 'Plan clips', 'Render', 'Check', 'Finish'], elapsed: 372,
   activity: 'python valorant_plan.py "E:\\Recordings\\Valorant\\Valorant 2026.08.01 - 16.15.54.03.mp4" "C:\\Work\\highlight-work\\Valorant_2026.08.01-16.15.54.03\\kills.json" --match "1=Breeze/Viper" --match "2=Sunset/Reyna"'},
  {id: 'demo2', kind: 'merge', state: 'running', path: 'demo', title: 'A very long merged video name for the weekend Valorant and Arena Breakout montage', clips: [1, 2, 3, 4],
   music: 'E:\\Music\\Highlights\\tonytonychopper999 - FEEL THE RUSH [NCS Release].mp3', step: 1, steps: ['Read clips', 'Beat-sync', 'Plan cuts', 'Encode', 'Finish'], elapsed: 41,
   activity: 'music: tonytonychopper999 - FEEL THE RUSH [NCS Release].mp3  140.0 BPM, starts at 3.42s'},
  {id: 'demo3', kind: 'highlight', state: 'failed', path: 'demo', title: 'Arena Breakout Infinite 2026.07.05 - 14.50.12.33', model: 'default', step: 2, steps: ['Claim'], elapsed: 95,
   error: 'ffmpeg exited with code 1: E:\\Recordings\\Arena Breakout Infinite\\Arena Breakout Infinite 2026.07.05 - 14.50.12.33.mp4: Invalid data found when processing input'},
];
const D = {footage: [], sets: [], merged: [], tracks: [], jobs: [], watch: {waiting: [], ytal: false}, disk: null, claude: {}, roots: {}, loaded: {}};
const S = {page: 'footage', view: 'grid', q: '', status: 'all', sort: 'newest', minScore: 0,
  sel: {footage: new Set(), shorts: new Set(), music: new Set()}, queue: [], queueOpen: false, jobsOpen: false,
  detail: null, collapsed: new Set(), merge: {fmt: 'short', hq: true, style: 'punchy', music: 'any', mix: 'music', mvol: 50, name: ''},
  musicTab: 'library', ncsQ: '', ncsItems: null, ncsLoading: false, ncsError: '', genre: 'all', playing: null,
  lookup: null, lookupBusy: false, link: '', settings: {}, musicVol: 0.5, playingInfo: null};
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

/* ---------- video player with an in-app full screen ----------
   The browser's own full screen only fills the app's web area and leaves the window's
   title bar (and its close button) showing, with no way out except Esc. This mode makes
   the window itself full screen and shows an "Exit full screen" X at the top left. */
function videoBox(path, title, autoplay = false) {
  return `<div class="vwrap"><video controls ${autoplay ? 'autoplay' : ''} preload="metadata" controlslist="nofullscreen nodownload noremoteplayback" disablepictureinpicture src="${mediaUrl(path)}"></video>
    <button class="vfs" data-action="fs-enter" title="Full screen (or double-click the video)" aria-label="Full screen">${ic('expand')}</button>
    <div class="vtop"><span class="vtitle">${esc(title)}</span><button class="vclose" data-action="fs-exit" aria-label="Exit full screen"><span>Exit full screen</span>${ic('x')}</button></div></div>`;
}
let theaterEl = null, idleT = null;
function enterTheater(wrap) {
  if (!wrap || theaterEl) return;
  theaterEl = wrap; wrap.classList.add('theater'); API().set_fullscreen(true); wakeTheater();
}
function exitTheater() {
  if (theaterEl) { theaterEl.classList.remove('theater', 'idle'); theaterEl = null; }
  clearTimeout(idleT); API().set_fullscreen(false);
}
function wakeTheater() {
  if (!theaterEl) return;
  theaterEl.classList.remove('idle'); clearTimeout(idleT);
  idleT = setTimeout(() => theaterEl && theaterEl.classList.add('idle'), 2500);
}
document.addEventListener('dblclick', e => {
  const v = e.target.closest('.vwrap video'); if (!v) return;
  e.preventDefault(); e.stopPropagation();
  theaterEl ? exitTheater() : enterTheater(v.closest('.vwrap'));
}, true);
document.addEventListener('fullscreenchange', () => {  // fallback if the browser's full screen still gets triggered
  const fe = document.fullscreenElement;
  if (fe && fe.tagName === 'VIDEO') { document.exitFullscreen().catch(() => {}); enterTheater(fe.closest('.vwrap')); }
});
document.addEventListener('mousemove', () => { if (theaterEl) wakeTheater(); }, true);
// every video starts at 50% volume (media events don't bubble, so listen in the capture phase)
document.addEventListener('loadstart', e => {
  const v = e.target;
  if (v.tagName === 'VIDEO' && !v.dataset.vol) { v.volume = 0.5; v.dataset.vol = '1'; }
}, true);

/* ---------- shell ---------- */
// only touch the DOM when the markup really changed (renderTop runs every second)
function setHTML(el, html) { if (el && el._html !== html) { el.innerHTML = html; el._html = html; } }
function setAttr(el, k, v) { if (el && el.getAttribute(k) !== String(v)) el.setAttribute(k, v); }
function renderTop() {
  const d = D.disk;
  if (d && d.total) {
    const used = 1 - d.free / d.total;
    const cls = 'disk num' + (d.free < 20e9 ? ' low' : ''); if ($('#disk').className !== cls) $('#disk').className = cls;
    setHTML($('#disk'), `${ic('disk')}<span>${esc(d.drive)} ${size(d.free)} free of ${size(d.total)}</span><span class="bar"><i style="width:${(used * 100).toFixed(0)}%"></i></span>`);
  }
  const active = D.jobs.filter(j => j.state === 'running' || j.state === 'queued').length;
  setHTML($('#jBtn'), `${active ? ic('loader', 'spin') : ic('activity')}<span>Jobs</span><span class="count num ${active ? '' : 'zero'}">${active}</span>`);
  setAttr($('#jBtn'), 'aria-pressed', S.jobsOpen);
  setHTML($('#qBtn'), `${ic('queue')}<span>Merge queue</span><span class="count num ${S.queue.length ? '' : 'zero'}">${S.queue.length}</span>`);
  setAttr($('#qBtn'), 'aria-pressed', S.queueOpen);
  renderRec();
}
/* recording (AMD Adrenalin, via its record hotkey). The timer shows minutes only and is
   refreshed every 15 s from started_at: no backend calls, one text node. */
function recElapsed() {
  const m = Math.max(0, Math.floor((Date.now() / 1000 - D.rec.started_at) / 60));
  return m < 1 ? '<1m' : m < 60 ? `${m}m` : `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, '0')}m`;
}
function renderRec() {
  const r = D.rec, box = $('#recBox'); if (!box) return;
  if (!r) return setHTML(box, '');
  const hk = esc(r.hotkey || 'Ctrl+Shift+E');
  if (r.phase === 'starting' || r.phase === 'stopping')
    return setHTML(box, `<button class="tb-btn recbtn" disabled>${ic('loader', 'spin')}<span>${r.phase === 'starting' ? 'Starting…' : 'Stopping…'}</span></button>`);
  if (r.recording) {
    const tip = `Recording ${esc(r.game)} since ${new Date(r.started_at * 1000).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}, ${size(r.size)} so far`;
    return setHTML(box, `<span class="recpill" title="${tip}"><span class="rec-dot"></span><b>REC</b><span class="recgame">${esc(r.game)}</span><span class="num" data-recel>${recElapsed()}</span></span><button class="tb-btn recstop" data-action="rec-toggle" title="Stop recording (${hk})">Stop</button>`);
  }
  setHTML(box, `<button class="tb-btn recbtn" data-action="rec-toggle" title="Start AMD Adrenalin recording (${hk})"><span class="rec-dot idle"></span><span>Record</span></button>`);
}
function tickRec() { if (D.rec && D.rec.recording) { const t = recElapsed(); document.querySelectorAll('[data-recel]').forEach(el => { if (el.textContent !== t) el.textContent = t; }); } }
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
  renderQueue(); renderFlyout(); renderNow();
  if (theaterEl && !theaterEl.isConnected) exitTheater();
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
  // the live recording first, then files the recorder still holds, then the chosen sort
  const rank = r => isLive(r) ? 0 : r.status === 'recording' ? 1 : 2;
  return list.sort((x, y) => rank(x) - rank(y) || sorters[S.sort](x, y));
}
function isLive(r) { return !!(D.rec && D.rec.recording && D.rec.path.toLowerCase() === r.path.toLowerCase()); }

function jobPct(j) { return j && j.state === 'running' ? Math.round(((j.step || 0) + 0.5) / (j.steps || []).length * 100) : 0; }
function pill(r) {
  const st = effStatus(r), j = jobFor(r.path);
  if (isLive(r))  // live, even while still "too small"
    return `<span class="pill st-recording"><span class="rec-dot"></span>Recording <span class="num" data-recel>${recElapsed()}</span></span>`;
  if (st === 'done') return `<span class="pill st-done">${ic('check')}${r.clips != null ? plural(r.clips, 'short') : 'Done'}</span>`;
  if (st === 'processing') return `<span class="pill st-processing">${ic('loader', 'spin')}${j ? esc(j.steps[j.step] || 'Processing') : 'Processing'}</span>`;
  if (st === 'recording')
    return `<span class="pill st-recording" title="The recorder still has this file open. It can be processed once it's released (closing AMD Software releases it).">Finishing</span>`;
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
  return `<div class="card ${sel ? 'selected' : ''} ${dis ? 'disabled' : ''} ${S.detailRec === r.id ? 'open' : ''}" data-action="card" data-id="${r.id}" data-kind="footage" title="${esc(r.file)}">
    ${thumbBox(r.path, r.dur, 0.1, extra)}
    <div class="cname">${esc(when(r.recorded))}</div>
    <div class="cmeta num"><span data-rsize="${r.id}">${size(r.size)}</span>${r.res ? `<span>${esc(r.res)}</span>` : ''}${st === 'failed' && r.reason ? `<span class="bad" title="${esc(r.reason)}">${esc(r.reason.slice(0, 60))}</span>` : ''}</div></div>`;
}
function recRow(r) {
  const sel = S.sel.footage.has(r.id), dis = !selectable(r), st = effStatus(r);
  const label = st === 'done' && r.clips != null ? plural(r.clips, 'short') : (STATUS[st] || st);
  return `<tr class="${sel ? 'selected' : ''}" data-action="card" data-id="${r.id}" data-kind="footage">
    <td>${dis ? '' : `<button class="boxchk" data-action="check" data-id="${r.id}" data-kind="footage" role="checkbox" aria-checked="${sel}" aria-label="Select">${ic('check')}</button>`}</td>
    <td class="name" title="${esc(r.file)}">${esc(r.file)}</td><td class="r num">${dur(r.dur)}</td><td class="r num" data-rsize="${r.id}">${size(r.size)}</td><td>${esc(r.res)}</td>
    <td class="num">${esc(when(r.recorded))}</td><td><span class="tpill st-${st}">${esc(label)}</span></td></tr>`;
}
function pageFootage() {
  if (!D.loaded.footage) return loadingPage('Footage');
  const list = filteredRecs(), liveGame = (list.find(isLive) || list.find(r => r.status === 'recording') || {}).game;
  // the game being recorded comes first
  const games = [...new Set(list.map(r => r.game))].sort((x, y) => (y === liveGame) - (x === liveGame) || x.localeCompare(y));
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
    const gs = sets.filter(s => s.game === g).sort((a, b) => b.label.localeCompare(a.label));
    const allClosed = gs.every(s => S.collapsed.has('r:' + s.id));
    h += `<section class="group ${col ? 'collapsed' : ''}"><div class="ghead"><button class="toggle" data-action="collapse" data-g="s:${esc(g)}" aria-expanded="${!col}">${ic('chevron')}<span class="gdot" style="background:${gameColor(g)}"></span>${esc(g)}</button>
      <span class="gmeta num">${plural(gs.length, 'recording')}, ${plural(gs.reduce((a, s) => a + s.vis.length, 0), 'short')}</span><span class="grow"></span>
      ${gs.length > 1 ? `<button class="linkbtn" data-action="collapse-sets" data-g="${esc(g)}" data-mode="${allClosed ? 'expand' : 'collapse'}">${allClosed ? 'Expand all' : 'Collapse all'}</button>` : ''}</div><div class="gbody">`;
    for (const s of gs) {
      const older = !s.current && D.sets.some(o => o.current && o.path.toLowerCase().startsWith(s.path.toLowerCase() + '\\'));
      const closed = S.collapsed.has('r:' + s.id);
      const scores = s.vis.map(c => c.score).filter(x => x != null), best = scores.length ? Math.max(...scores) : null;
      const nSel = s.vis.filter(c => S.sel.shorts.has(c.id)).length;
      h += `<div class="setgroup ${closed ? 'collapsed' : ''}"><div class="sub-ghead" data-set-id="${s.id}">
        <button class="subtoggle" data-action="collapse" data-g="r:${s.id}" aria-expanded="${!closed}">${ic('chevron')}${ic('folder')}<strong>${esc(s.label)}</strong></button>
        ${older ? '<span class="oldtag">Earlier run</span>' : ''}<span class="num">${plural(s.vis.length, 'short')}${best != null ? `, best ${best}` : ''}${nSel ? `, <span class="inqueue">${nSel} selected</span>` : ''}</span><span class="grow"></span>
        <button class="linkbtn" data-action="reveal" data-p="${esc(s.path)}">Show in folder</button><button class="linkbtn" data-action="sel-set" data-id="${s.id}">Select all</button></div>
        <div class="grid small">${closed ? '' : s.vis.map(clipCard).join('')}</div></div>`;
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
  return `<div class="card ${sel ? 'selected' : ''} ${S.detail === c.id ? 'open' : ''}" data-action="open-clip" data-id="${c.id}" data-kind="shorts" title="${esc(c.file)}">
    ${thumbBox(c.path, c.len, 0.4, extra)}
    <div class="cname">${esc(c.title)}</div>
    <div class="cmeta">${c.n != null ? `<span class="num">#${String(c.n).padStart(2, '0')}</span>` : ''}${q ? '<span class="inqueue">In merge queue</span>' : ''}${c.used ? `<span class="used">${ic('stack')}Used in ${plural(c.used, 'merge')}</span>` : ''}</div></div>`;
}

/* ---------- Merge queue ---------- */
const QCOL = ['var(--accent)', 'var(--g1)', 'var(--g2)', 'var(--g3)', 'var(--g0)'];
function trackLabel(t) { return `${t.artist ? t.artist + ' - ' : ''}${t.title || t.file}`; }
function renderQueue() {
  const el = $('#queue'); el.hidden = !S.queueOpen; if (!S.queueOpen) return;
  el.style.width = (S.queueW || 340) + 'px';
  const items = S.queue.map(clipOfPath).filter(Boolean), total = items.reduce((a, c) => a + c.len, 0);
  const limit = S.merge.fmt === 'short' ? 180 : null, scale = limit ? Math.max(limit, total) : Math.max(total, 1);
  let acc = 0;
  const usable = D.tracks.filter(t => t.credit_state !== 'missing');
  el.innerHTML = `${RESIZER}<div class="qhead"><h2>Merge queue</h2><span class="grow"></span>${items.length ? '<button class="linkbtn" data-action="q-clear">Clear</button>' : ''}<button class="iconbtn" data-action="toggle-queue" aria-label="Hide merge queue">${ic('x')}</button></div>
  ${items.length ? `<ol class="qlist" id="qlist">${items.map((c, i) => `<li class="qitem" draggable="true" data-qp="${esc(c.path)}" style="--qc:${QCOL[i % QCOL.length]}">
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
   <div class="field"><label for="mixSel">Sound</label><select class="select" id="mixSel">${[['music', 'Steady: music plays under the game'], ['balanced', 'Game first: music also dips on shots'], ['musiconly', 'Music only: no game sound']].map(([v, l]) => `<option value="${v}" ${S.merge.mix === v ? 'selected' : ''}>${l}</option>`).join('')}</select></div>
   ${S.merge.mix === 'musiconly' ? '' : `<div class="field"><label for="mvol">Music volume</label><span class="np-vol mvol" title="Compared with the gameplay, measured per video. 100% = as loud as the game, 50% = half as loud."><input type="range" id="mvol" min="10" max="150" step="5" value="${S.merge.mvol ?? 50}" aria-label="Music volume compared with the game"><span class="num" id="mvolTxt">${S.merge.mvol ?? 50}%</span><span class="note">of game</span></span></div>`}
   <div class="field"><label>1440p</label><span style="display:flex;align-items:center;gap:8px"><button class="switch" data-action="hq" role="switch" aria-checked="${S.merge.hq}" aria-label="1440p output"></button><span class="note">${S.merge.hq ? 'Higher quality on YouTube' : '1080p'}</span></span></div>
  </div>
  <div class="qactions"><button class="btn" data-action="preview" ${items.length < 2 ? 'disabled' : ''}>${ic('eye')}Preview cuts</button><button class="btn primary" data-action="merge" ${items.length < 2 ? 'disabled' : ''} title="${items.length < 2 ? 'Add at least 2 shorts' : ''}">${ic('stack')}Merge</button></div>`;
  bindDrag();
}
function saveQueue() { if (!DEMO) lsSet('queue', S.queue); }
/* resize a side panel (merge queue or details) by dragging its left edge; double-click to reset */
const QMIN = 280, QDEF = 340, DDEF = 420, qMax = () => Math.max(QMIN, Math.min(900, window.innerWidth - 460));
const RESIZER = '<div class="qresize" title="Drag to resize. Double-click to reset." role="separator" aria-orientation="vertical" aria-label="Resize panel"></div>';
const panelKey = el => el.id === 'detail' ? ['detailW', DDEF] : ['queueW', QDEF];
document.addEventListener('pointerdown', e => {
  const h = e.target.closest('.qresize'); if (!h || e.button !== 0) return;
  e.preventDefault();
  const q = h.parentElement, [key] = panelKey(q), startX = e.clientX, startW = q.getBoundingClientRect().width;
  h.classList.add('dragging'); document.body.classList.add('resizing');
  const move = ev => { S[key] = Math.round(Math.max(QMIN, Math.min(qMax(), startW + (startX - ev.clientX)))); q.style.width = S[key] + 'px'; };
  const up = () => { window.removeEventListener('pointermove', move); h.classList.remove('dragging'); document.body.classList.remove('resizing'); lsSet(key, S[key]); };
  window.addEventListener('pointermove', move);
  window.addEventListener('pointerup', up, {once: true});
});
document.addEventListener('dblclick', e => {
  const h = e.target.closest('.qresize'); if (!h) return;
  const q = h.parentElement, [key, def] = panelKey(q);
  S[key] = def; lsSet(key, def); q.style.width = def + 'px';
});
window.addEventListener('resize', () => {
  for (const [id, key] of [['queue', 'queueW'], ['detail', 'detailW']]) {
    if (S[key] && S[key] > qMax()) { S[key] = qMax(); const q = document.getElementById(id); if (q) q.style.width = S[key] + 'px'; }
  }
});
function saveMergeOpts() { API().settings_set({merge: {fmt: S.merge.fmt, hq: S.merge.hq, style: S.merge.style, music: S.merge.music, mix: S.merge.mix, mvol: S.merge.mvol ?? 50}}); }
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
  return {clips: S.queue, name: S.merge.name || defaultName(), fmt: S.merge.fmt, hq: S.merge.hq, style: S.merge.style, mix: S.merge.mix || 'music', mvol: S.merge.mvol ?? 50, music: musicOverride || S.merge.music};
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
     ${m.clips.length ? `<div class="clipspop"><button class="chip clipsbtn" aria-haspopup="true">${ic('scissors')}Made from ${plural(m.clips.length, 'short')}</button>
       <div class="pop" role="tooltip"><div class="pop-in"><ol>${m.clips.map(p => { const c = clipOfPath(p);
         return `<li title="${esc(p)}"><span>${esc(c ? c.title : base(p).replace(/\.mp4$/i, ''))}</span>${c ? `<small>${esc(c.game)}${c.score != null ? `, score ${c.score}` : ''}</small>` : '<small>Deleted short</small>'}</li>`; }).join('')}</ol></div></div></div>` : ''}
     ${(m.youtube || []).length ? (() => { const y = m.youtube[m.youtube.length - 1];
       return `<div><button class="tpill st-done btnlike" data-action="open-url" data-url="${esc(y.studio)}" title="Open in YouTube Studio">${ic('check')}On YouTube, ${esc(y.privacy_requested === 'scheduled' ? 'scheduled' : y.privacy)}${m.youtube.length > 1 ? ` (${m.youtube.length} uploads)` : ''}</button></div>`; })() : ''}
     <div class="mactions"><button class="btn sm primary" data-action="upload-yt" data-id="${m.id}">${ic('play')}Upload to YouTube</button><button class="btn sm" data-action="play-merged" data-id="${m.id}">${ic('play')}Play</button><button class="btn sm" data-action="desc" data-id="${m.id}">${ic('copy')}YouTube description</button>
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
      const facts = [n.genre, n.mood].filter(Boolean).map(esc).join(' · ');
      return `<div class="tcard"><div class="cover">${n.cover ? `<img loading="lazy" src="${esc(n.cover)}" alt="">` : ''}
         ${facts || n.len ? `<div class="cover-info">${facts ? `<span>${facts}</span>` : ''}${n.len ? `<span class="num">${esc(n.len)}</span>` : ''}</div>` : ''}
         <button class="playbtn ${playing ? 'on' : ''}" data-action="play-ncs" data-slug="${esc(n.slug)}" aria-label="Preview ${esc(n.title)}">${playing ? ic('pause') : ic('play')}</button></div>
       <div class="tt" title="${esc([n.title, n.artist, facts.replace(/&middot;|·/g, '·'), n.len].filter(Boolean).join('\n'))}"><b>${esc(n.title)}</b><span>${esc(n.artist)}</span></div>
       ${have ? `<div class="inlib">${ic('check')}In your library</div>`
         : wait ? `<div class="waitrow"><span>${ic('loader', 'spin')}Waiting for the download</span><button class="linkbtn" data-action="ncs-cancel" data-slug="${esc(n.slug)}">Stop waiting</button></div>`
         : `<button class="btn" data-action="get-ncs" data-slug="${esc(n.slug)}">Get track</button>`}</div>`; }).join('')}</div>`;
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
   ${row('Game playbooks', 'The rules the highlight maker follows for each game, in plain view. To change one, ask Claude in the terminal.',
     `<button class="btn sm" data-action="playbooks">${ic('book')}View playbooks</button>`)}
   <div class="shead">Recording</div>
   ${(() => { const ri = D.recInfo || {};
     return row('AMD Adrenalin', ri.adrenalin === false ? "AMD Software isn't running, so the Record button can't start a recording." : `The Record button in the top bar presses Adrenalin's record hotkey.${ri.output ? ` Adrenalin saves to ${esc(ri.output)}.` : ''}`,
       ri.adrenalin === false ? `<span class="badline">${ic('warn')}Not running</span>` : ri.output_ok === false ? `<span class="badline">${ic('warn')}Saves outside ${esc(ri.recordings)}</span>` : `<span class="okline">${ic('check')}Ready</span>`)
     + row('Record hotkey', 'Must match Adrenalin → Settings → Hotkeys → Record video. Click the box and press the keys.',
       `<input type="text" class="hkin" id="recKey" readonly value="${esc(st.rec_hotkey || 'Ctrl+Shift+E')}" aria-label="Record hotkey">`); })()}
   <div class="shead">YouTube</div>
   ${(() => { const y = D.yt || {};
     if (!y.client) return row('YouTube uploads', 'Not set up yet. A one-time setup of about 15 minutes lets the app upload merged videos to your channel when you press Upload.', `<button class="btn sm primary" data-action="yt-setup">Set up</button>`);
     if (!y.signed_in) return row('YouTube uploads', y.error ? esc(y.error) : 'Client file added. Sign in with the Google account that owns your channel.', `<button class="btn sm" data-action="yt-setup">Setup steps</button><button class="btn sm primary" data-action="yt-signin">Sign in</button>`);
     return row('YouTube uploads', `Signed in as <b>${esc(y.channel.title)}</b>. Uploads default to Private. Google may ask you to sign in again about once a week; the app opens it for you.`, `<span class="okline">${ic('check')}Connected</span><button class="btn sm" data-action="yt-setup">Setup steps</button><button class="btn sm ghost" data-action="yt-signout">Sign out</button>`);
   })()}
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
function renderFlyout() { renderJobs(); renderDetail(); }
/* Jobs: a popup over the page */
function renderJobs() {
  const host = $('#flyout');
  if (!S.jobsOpen) { host.innerHTML = ''; return; }
  {
    const act = D.jobs.filter(j => j.state === 'queued' || j.state === 'running'), done = D.jobs.filter(j => !(j.state === 'queued' || j.state === 'running'));
    const body = `${act.length ? `<div class="sectionlabel">Running</div>${act.map(jobCard).join('')}` : `<div class="qempty">Nothing running. Select recordings on Footage and choose Make highlights.</div>`}
     ${done.length ? `<div class="sectionlabel"><span>Finished</span><button class="linkbtn" data-action="clear-jobs">Clear</button></div>${done.map(jobCard).join('')}` : ''}`;
    // Only rebuild what changed: the elapsed clocks tick in place, so spinners, scroll and
    // the slide-in animation aren't restarted every second.
    const sig = body.replace(/data-el="[^"]*">[^<]*</g, '').replace(/data-upbar="[^"]*" style="[^"]*"/g, '').replace(/data-upact="[^"]*">[^<]*</g, '');
    const fly = host.querySelector('.flyout.jobs');
    if (!fly) {
      host.innerHTML = `<div class="flyout jobs" role="dialog" aria-label="Jobs"><div class="flyhead"><h2>Jobs</h2><button class="iconbtn" data-action="toggle-jobs" aria-label="Close">${ic('x')}</button></div><div class="flybody">${body}</div></div>`;
    } else if (fly.dataset.sig !== sig) {
      const fb = fly.querySelector('.flybody'), keep = fb.scrollTop;
      const reports = [...fb.querySelectorAll('.report')].map(r => r.scrollTop);
      fb.innerHTML = body; fb.scrollTop = keep;
      fb.querySelectorAll('.report').forEach((r, i) => { r.scrollTop = reports[i] || 0; });
    } else {
      for (const j of D.jobs) {
        fly.querySelectorAll(`[data-el="${j.id}"]`).forEach(e => { e.textContent = dur(j.elapsed); });
        if (j.kind === 'upload') {
          fly.querySelectorAll(`[data-upbar="${j.id}"]`).forEach(e => { e.style.width = Math.round((j.progress || 0) * 100) + '%'; });
          fly.querySelectorAll(`[data-upact="${j.id}"]`).forEach(e => { e.textContent = j.activity || 'Uploading'; });
        }
      }
    }
    host.querySelector('.flyout.jobs').dataset.sig = sig;
  }
}
/* Details (a recording or a short): a docked side panel next to the page, like the merge queue */
function renderDetail() {
  const host = $('#detail');
  host.style.width = (S.detailW || DDEF) + 'px';
  if (S.detailRec) {
    const r = recById.get(S.detailRec);
    if (r) { host.hidden = false; return recPanel(host, r); }
    S.detailRec = null;
  }
  const c = S.detail && clipById.get(S.detail);
  if (!c) { S.detail = null; host.hidden = true; host.innerHTML = ''; return; }
  host.hidden = false;
  const s = setOfClip.get(c.id), q = S.queue.some(p => p.toLowerCase() === c.path.toLowerCase());
  const yt = (label, val, k) => val ? `<div class="yt-row"><div><small>${label}</small><p>${esc(val)}</p></div><button class="iconbtn" data-action="copy" data-k="${k}" aria-label="Copy ${label}">${ic('copy')}</button></div>` : '';
  const parts = c.parts && typeof c.parts === 'object' ? c.parts : null;
  const html = `<div class="flyout" role="dialog" aria-label="${esc(c.title)}"><div class="flyhead"><h2 title="${esc(c.title)}">${esc(c.title)}</h2><button class="iconbtn" data-action="close-detail" aria-label="Close">${ic('x')}</button></div>
   <div class="flybody">${videoBox(c.path, c.title)}
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
  host.innerHTML = RESIZER + html;
  host.querySelector('.flyout').dataset.sig = html;
}
function recPanel(host, r) {
  const st = effStatus(r), j = jobFor(r.path);
  const set = r.clips_dir ? D.sets.find(s => s.path.toLowerCase() === String(r.clips_dir).toLowerCase()) : null;
  const label = st === 'done' && r.clips != null ? plural(r.clips, 'short') : (STATUS[st] || st);
  const audio = r.audio === 2 ? '2 tracks (game and mic)' : r.audio === 1 ? '1 track' : r.audio ? `${r.audio} tracks` : 'None';
  const row = (k, v) => v ? `<dt>${k}</dt><dd title="${esc(String(v).replace(/<[^>]+>/g, ''))}">${v}</dd>` : '';
  const act = [];
  if (st === 'done' && set) act.push(`<button class="btn primary" data-action="view-set" data-id="${set.id}">${ic('scissors')}View ${plural(set.clips.length, 'short')}</button>`);
  if (runnable(r)) act.push(`<button class="btn primary" data-action="make-one" data-p="${esc(r.path)}">${ic(st === 'new' ? 'sparkle' : 'retry')}${st === 'new' ? 'Make highlights' : 'Run again'}</button>`);
  act.push(`<button class="btn ghost" data-action="reveal" data-p="${esc(r.path)}">${ic('folder')}Show in folder</button>`);
  if (selectable(r)) act.push(`<button class="btn ghost danger" data-action="del-rec-one" data-id="${r.id}">${ic('trash')}Delete</button>`);
  const html = `<div class="flyout" role="dialog" aria-label="${esc(r.file)}"><div class="flyhead"><h2 title="${esc(r.file)}">${esc(when(r.recorded))}</h2><button class="iconbtn" data-action="close-detail" aria-label="Close">${ic('x')}</button></div>
   <div class="flybody">${videoBox(r.path, `${r.game}, ${when(r.recorded)}`)}
    ${st === 'recording' ? `<div class="warnbox">${ic('warn')}<span>This file is still being recorded. Playback stops where the recording is up to now.</span></div>` : ''}
    <div><span class="tpill st-${st}">${st === 'processing' ? ic('loader', 'spin') : st === 'done' ? ic('check') : ''}${esc(label)}</span></div>
    ${st === 'processing' && j ? `<div class="stepname" data-recstep>${recStep(j)}</div>` : ''}
    ${st === 'failed' && r.reason ? `<div class="report bad">${esc(r.reason)}</div>` : ''}
    <dl class="facts num big">
     ${row('File', esc(r.file))}${row('Game', esc(r.game))}${row('Recorded', esc(when(r.recorded)))}${row('Length', dur(r.dur))}${row('Size', size(r.size))}
     ${row('Video', r.w ? `${r.w}×${r.h}${r.fps ? `, ${r.fps} fps` : ''}` : '')}${row('Audio', audio)}
     ${row('Processed', r.completed_at ? esc(when(r.completed_at)) : '')}${row('Failed', st === 'failed' && r.failed_at ? esc(when(r.failed_at)) : '')}
    </dl>
    <div class="jobacts">${act.join('')}</div>
    <p class="note" style="margin:0">Tip: tick the box on a card, or Ctrl+click it, to select several recordings.</p></div></div>`;
  // the live step text updates in place, so a playing video isn't restarted
  const sig = html.replace(/<div class="stepname" data-recstep>[\s\S]*?<\/div>/, '');
  const cur = host.querySelector('.flyout');
  if (cur && cur.dataset.sig === sig) {
    const s = cur.querySelector('[data-recstep]'); if (s && j) s.innerHTML = recStep(j);
    return;
  }
  host.innerHTML = RESIZER + html;
  host.querySelector('.flyout').dataset.sig = sig;
}
const recStep = j => `<span>Step ${(j.step || 0) + 1} of ${j.steps.length}: ${esc(j.steps[j.step] || '')}. ${esc(j.activity || '')}</span>`;
function uploadCard(j) {
  const pct = Math.round((j.progress || 0) * 100), el = dur(j.elapsed);
  const name = `YouTube: ${esc(j.title)}`, vis = j.meta && j.meta.publish_at ? 'scheduled' : esc(j.privacy || 'private');
  if (j.state === 'queued') return `<div class="job"><div class="top">${ic('activity')}<div class="grow"><b>${name}</b><span>${vis}. Waiting for the current upload.</span></div><button class="btn sm ghost" data-action="cancel" data-id="${j.id}">Cancel</button></div></div>`;
  if (j.state === 'running') return `<div class="job"><div class="top">${ic('loader', 'spin')}<div class="grow"><b>${name}</b><span>${vis}, <span class="num" data-el="${j.id}">${el}</span> so far</span></div><button class="btn sm ghost" data-action="cancel" data-id="${j.id}">Cancel</button></div>
    <div class="ubar"><i data-upbar="${j.id}" style="width:${pct}%"></i></div><div class="stepname"><span data-upact="${j.id}">${esc(j.activity || 'Uploading')}</span></div></div>`;
  if (j.state === 'done') return `<div class="job"><div class="top"><span class="${j.forced_private ? 'bad' : 'ok'}">${ic(j.forced_private ? 'warn' : 'check')}</span><div class="grow"><b>${name}</b><span>Uploaded in ${el}</span></div></div>
    <div class="report">${esc(j.report)}</div><div class="jobacts"><button class="btn sm ${j.forced_private ? 'primary' : ''}" data-action="open-url" data-url="${esc(j.studio)}">Open in YouTube Studio</button><button class="btn sm ghost" data-action="open-url" data-url="${esc(j.out)}">Watch</button></div></div>`;
  return `<div class="job"><div class="top"><span class="bad">${ic('warn')}</span><div class="grow"><b>${name}</b><span>${j.state === 'cancelled' ? 'Cancelled' : 'Failed'} after ${el}</span></div></div>
    ${j.error ? `<div class="report ${j.state === 'cancelled' ? '' : 'bad'}">${esc(j.error)}</div>` : ''}<div class="jobacts"><button class="btn sm" data-action="nav" data-page="merged">Back to Merged</button></div></div>`;
}
function jobCard(j) {
  if (j.kind === 'upload') return uploadCard(j);
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
function closeDialog() {
  if (theaterEl && dlg.contains(theaterEl)) exitTheater();
  dlg.querySelectorAll('video,audio').forEach(v => { try { v.pause(); } catch (_) {} }); if (dlg.open) dlg.close(); dlg.innerHTML = '';
}
dlg.addEventListener('cancel', e => { if (theaterEl) { e.preventDefault(); exitTheater(); } });
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
  openDialog(`<div class="player ${portrait ? 'portrait' : ''}">
   <div class="pbar top"><b title="${esc(name)}">${esc(name)}</b><button class="btn sm ghost" data-action="reveal" data-p="${esc(path)}">${ic('folder')}Show in folder</button><button class="iconbtn" data-action="dlg-close" aria-label="Close">${ic('x')}</button></div>
   ${videoBox(path, name, true)}</div>`, 'player' + (portrait ? ' portrait' : ''));
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
function buildDesc(m) {
  const cs = m.clips.map(clipOfPath).filter(Boolean), t = trackOfPath(m.music);
  const tagList = [...new Set(cs.flatMap(c => String(c.tags || '').split(/\s+/)).filter(x => x.startsWith('#')))].slice(0, 8);
  let credit = '', warn = '';
  if (t && t.credit_state === 'ready') credit = t.credit;
  else if (m.music && !t) warn = `The music (${base(m.music)}) isn't in your library any more, so its credit isn't known. Add it yourself before posting.`;
  else if (t && t.credit_state === 'missing') warn = `"${trackLabel(t)}" has no credit line. Add one on the Music page first.`;
  return {txt: [m.name, credit, tagList.join(' ')].filter(Boolean).join('\n\n'), warn, tagList};
}
function descDialog(m) {
  const {txt, warn} = buildDesc(m);
  openDialog(`<div class="dlg-body"><h2>YouTube description</h2><p>Built from the shorts' text and the music credit. Edit it before copying if you like.</p>
   ${warn ? `<div class="warnbox">${ic('warn')}<span>${esc(warn)}</span></div>` : ''}
   <div class="form"><textarea id="descTxt" style="min-height:240px">${esc(txt)}</textarea></div></div>
   <div class="dlg-foot"><button class="btn primary" data-action="copy-desc">${ic('copy')}Copy</button><button class="btn" data-action="dlg-close">Close</button></div>`);
}
/* ---------- YouTube upload ---------- */
async function refreshYt() { D.yt = await API().yt_status(); return D.yt; }
function ytGuide() {
  const yt = D.yt || {};
  const step = (n, title, body, btn) => `<li class="ystep"><span class="yn num">${n}</span><div><span class="yt-t">${title}</span><p>${body}</p>${btn || ''}</div></li>`;
  const link = (url, label) => `<button class="btn sm" data-action="open-url" data-url="${url}">${label}</button>`;
  openDialog(`<div class="dlg-body"><h2>Set up YouTube uploads</h2>
    <p>A one-time setup of about 15 minutes. It's free: no billing account is needed. It gives the app permission to upload to your channel; the app still only uploads when you press Upload.</p>
    <ol class="ysteps">
     ${step(1, 'Create a Google Cloud project', 'Sign in with the Google account that owns your YouTube channel, then create a project named "Highlight Studio".', link('https://console.cloud.google.com/projectcreate', 'Open project page'))}
     ${step(2, 'Turn on the YouTube Data API v3', 'With the new project selected, click Enable.', link('https://console.cloud.google.com/apis/library/youtube.googleapis.com', 'Open YouTube Data API'))}
     ${step(3, 'Set up the consent screen', 'User type <b>External</b>. Under Branding, fill in only the app name and your email: leave the logo, links and domains empty. Under Data access, add the scopes <code>youtube.upload</code> and <code>youtube.readonly</code>. Under Audience, leave it in <b>Testing</b> and add your own Gmail under <b>Test users</b>. In Testing, Google asks you to sign in again about once a week; the app opens that sign-in for you when you upload.', link('https://console.cloud.google.com/auth/overview', 'Open consent screen'))}
     ${step(4, 'Create the app key', 'Clients → Create client → Application type <b>Desktop app</b> → Create → <b>Download JSON</b>.', link('https://console.cloud.google.com/auth/clients', 'Open clients'))}
     ${step(5, 'Connect it here', `Choose the JSON file you downloaded, then sign in. Google warns "Google hasn't verified this app" because it's your own private app: choose <b>Advanced → Go to Highlight Studio</b>.`,
       `<div class="jobacts"><button class="btn sm ${yt.client ? '' : 'primary'}" data-action="yt-client">${yt.client ? ic('check') + 'Client file added' : 'Choose client file'}</button><button class="btn sm ${yt.client && !yt.signed_in ? 'primary' : ''}" data-action="yt-signin" ${yt.client ? '' : 'disabled'}>${yt.signed_in ? ic('check') + 'Signed in as ' + esc(yt.channel.title) : 'Sign in'}</button></div>`)}
    </ol>
    <p class="note">New API apps may only be allowed to upload as Private until Google reviews them. If that happens, the app tells you and links to YouTube Studio, where you publish with one click.</p></div>
    <div class="dlg-foot"><button class="btn" data-action="dlg-close">Close</button></div>`);
}
function uploadDialog(m) {
  const {txt, warn, tagList} = buildDesc(m);
  const short = m.fmt === 'short' && m.len <= 180;
  const prev = (m.youtube || []).slice(-1)[0];
  const tags = tagList.map(t => t.replace(/^#/, '')).join(', ');
  const now = new Date(Date.now() + 3600e3); now.setMinutes(0, 0, 0);
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60e3).toISOString().slice(0, 16);
  S.uploadPath = m.path;
  openDialog(`<div class="dlg-body"><h2>Upload to YouTube</h2>
    <p>Everything is filled in from the shorts and the music credit. Check it, then press Upload. ${D.yt && D.yt.channel ? `Channel: <b>${esc(D.yt.channel.title)}</b>.` : ''}</p>
    ${prev ? `<div class="warnbox">${ic('warn')}<span>This video was already uploaded on ${esc(when(prev.uploaded_at))} (<a href="#" data-action="open-url" data-url="${esc(prev.studio)}">open in Studio</a>). Uploading again makes a second copy.</span></div>` : ''}
    ${warn ? `<div class="warnbox">${ic('warn')}<span>${esc(warn)}</span></div>` : ''}
    <div class="form">
     <label>Title <span class="count-hint num" id="tCount"></span><input type="text" id="yTitle" maxlength="100" value="${esc(m.name)}"></label>
     <label>Description <span class="count-hint num" id="dCount"></span><textarea id="yDesc" maxlength="5000" style="min-height:170px">${esc(txt)}</textarea></label>
     <label>Tags (comma separated)<input type="text" id="yTags" value="${esc(tags)}"></label>
     <div class="two"><label>Visibility<select id="yPriv"><option value="private" selected>Private</option><option value="unlisted">Unlisted</option><option value="public">Public</option><option value="scheduled">Scheduled</option></select></label>
      <label id="yWhenWrap" hidden>Publish at (your time)<input type="datetime-local" id="yWhen" value="${local}"></label></div>
     <div class="two"><label>Made for kids<select id="yKids"><option value="0" selected>No, it's not made for kids</option><option value="1">Yes, it's made for kids</option></select></label>
      <label>Category<select disabled><option>Gaming</option></select></label></div>
     <label class="checkline"><input type="checkbox" id="yNotify" checked> Notify subscribers</label>
     ${short ? `<p class="note" style="margin:0">This is vertical and ${dur(m.len)} long, so YouTube shows it as a Short automatically.</p>` : ''}
    </div></div>
    <div class="dlg-foot"><button class="btn primary" data-action="yt-upload">${ic('play')}Upload to YouTube</button><button class="btn" data-action="dlg-close">Cancel</button></div>`);
  const upd = () => { $('#tCount').textContent = `${$('#yTitle').value.length}/100`; $('#dCount').textContent = `${$('#yDesc').value.length}/5000`; };
  $('#yTitle').addEventListener('input', upd); $('#yDesc').addEventListener('input', upd); upd();
  $('#yPriv').addEventListener('change', e => { $('#yWhenWrap').hidden = e.target.value !== 'scheduled'; });
}
async function startUpload() {
  const priv = $('#yPriv').value;
  let publishAt = '';
  if (priv === 'scheduled') {
    const d = new Date($('#yWhen').value);
    if (isNaN(d) || d.getTime() < Date.now() + 15 * 60e3) { toast('Pick a time at least 15 minutes from now'); return; }
    publishAt = d.toISOString();
  }
  const r = await API().yt_upload({path: S.uploadPath, title: $('#yTitle').value, description: $('#yDesc').value, tags: $('#yTags').value,
    privacy: priv === 'scheduled' ? 'private' : priv, publish_at: publishAt, made_for_kids: $('#yKids').value === '1', notify: $('#yNotify').checked});
  if (!r.ok) { toast("Can't upload yet", r.error); return; }
  closeDialog(); S.jobsOpen = true; S.detail = null; S.detailRec = null;
  toast('Upload started', 'Watch it under Jobs. You can keep using the app.');
  await pollJobs(); render();
}

/* ---------- playbook viewer (read-only; playbooks are changed by asking Claude outside the app) ---------- */
async function openPlaybooks() {
  openDialog(`<div class="dlg-body"><h2>Game playbooks</h2><div class="loading">${ic('loader', 'spin')}Loading…</div></div>`, 'pbview');
  S.pbList = await API().playbooks();
  if (!S.pbSel || !S.pbList.some(p => p.id === S.pbSel)) S.pbSel = S.pbList[0] && S.pbList[0].id;
  renderPlaybook();
}
function renderPlaybook() {
  const list = S.pbList || [], pb = list.find(p => p.id === S.pbSel);
  if (!pb) { openDialog(`<div class="dlg-body"><h2>Game playbooks</h2><p>No playbooks found in the pipeline's games folder.</p></div><div class="dlg-foot"><button class="btn" data-action="dlg-close">Close</button></div>`, 'pbview'); return; }
  const usedBy = pb.default
    ? (pb.used_by.length ? `Used for ${pb.used_by.map(esc).join(', ')}, which don't have a playbook of their own yet.` : 'Used for any game folder without its own playbook.')
    : `Used for recordings in the ${esc(pb.game)} folder.`;
  openDialog(`<div class="pb">
    <nav class="pb-list" aria-label="Games">${list.map(p => `<button data-action="pb-pick" data-id="${esc(p.id)}" ${p.id === pb.id ? 'aria-current="true"' : ''}>${ic('book')}<span>${esc(p.game)}</span></button>`).join('')}</nav>
    <div class="pb-main" id="pbMain">
      <div class="pb-head"><div><h2>${esc(pb.game)}</h2><p>${usedBy} Last updated ${esc(when(pb.updated))}.</p></div>
        <div class="pb-acts"><button class="btn sm ghost" data-action="pb-reveal">${ic('folder')}Show file</button><button class="iconbtn" data-action="dlg-close" aria-label="Close">${ic('x')}</button></div></div>
      <div class="banner pb-note">${ic('book')}<p>These are the rules the highlight maker follows for this game: what counts as a highlight, how clips are cut and scored, and what to skip. The commands it runs are folded away under <b>Show command</b>. To change anything, ask Claude in the terminal, for example: <i>"Update the ${esc(pb.default ? 'default' : pb.game)} playbook so that…"</i></p></div>
      <div class="pb-toc" id="pbToc"></div>
      <article class="md">${pb.html}</article>
    </div></div>`, 'pbview');
  const md = dlg.querySelector('.md');
  md.querySelectorAll('pre').forEach(pre => {  // commands for the agent: folded by default
    const d = document.createElement('details'); d.className = 'cmd';
    d.innerHTML = '<summary>Show command</summary>'; pre.replaceWith(d); d.appendChild(pre);
  });
  const hs = [...md.querySelectorAll('h2')];
  dlg.querySelector('#pbToc').innerHTML = hs.length > 1 ? hs.map((h, i) => `<button class="chip" data-action="pb-jump" data-i="${i}">${esc(h.textContent)}</button>`).join('') : '';
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
  D.jobs = DEMO ? [...DEMO_JOBS, ...r.jobs] : r.jobs; D.watch = r.watch;
  const wasRec = D.rec ? D.rec.recording : null, wasPhase = D.rec ? D.rec.phase : '';
  D.rec = r.rec;
  if (r.rec.phase === 'failed' && wasPhase !== 'failed') toast(wasPhase === 'stopping' ? "Recording didn't stop" : "Recording didn't start", r.rec.error, ['Settings', 'nav', 'settings']);
  let reloadF = wasRec !== null && wasRec !== r.rec.recording, reloadS = false, reloadM = false;
  for (const j of D.jobs) {
    const prev = prevJobState.get(j.id);
    if (prev && prev !== j.state) {
      if (j.state === 'running' && j.kind === 'highlight') reloadF = true;
      if (j.state === 'done') {
        if (j.kind === 'highlight') { reloadF = reloadS = true; toast(`${j.title}: ${j.clips != null ? plural(j.clips, 'short') : 'done'}`, 'Highlights are ready.', ['View shorts', 'nav', 'shorts']); }
        else if (j.kind === 'upload') { reloadM = true; toast(j.forced_private ? `Uploaded "${j.title}" as Private` : `Uploaded "${j.title}" to YouTube`, j.forced_private ? 'YouTube kept it private. Publish it in YouTube Studio.' : j.out, ['Show jobs', 'show-jobs']); }
        else { reloadM = reloadS = true; toast(`Merged "${j.title}"`, `Saved to ${D.roots.merged}`, ['Open Merged', 'nav', 'merged']); }
      } else if (j.state === 'failed') { reloadF = true; toast(`${{merge: 'Merge', upload: 'Upload'}[j.kind] || 'Highlight run'} failed: ${j.title}`, String(j.error || '').slice(0, 160), ['Show jobs', 'show-jobs']); }
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
  if (S.jobsOpen || S.detailRec) renderFlyout();
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
async function playAudio(key, url, info) {
  const a = $('#audio');
  if (S.playing === key) { a.pause(); S.playing = null; render(); return; }
  a.src = url; a.volume = S.musicVol; S.playing = key; S.playingInfo = info || {};
  try { await a.play(); } catch (_) { S.playing = null; toast("Couldn't play that track"); }
  render();
}
/* now-playing bar: play/pause, seek and volume for music previews */
function renderNow() {
  const el = $('#nowplaying'), a = $('#audio'), on = !!S.playing || (!!S.playingInfo && !a.paused);
  el.hidden = !S.playing;
  if (!S.playing) return;
  const i = S.playingInfo || {};
  el.innerHTML = `<button class="playbtn on" data-action="np-toggle" aria-label="${a.paused ? 'Play' : 'Pause'}">${a.paused ? ic('play') : ic('pause')}</button>
    <div class="np-t"><b title="${esc(i.title || '')}">${esc(i.title || 'Preview')}</b><span>${esc(i.artist || '')}</span></div>
    <span class="num np-time" id="npTime">0:00</span><input type="range" id="npSeek" min="0" max="1000" value="0" aria-label="Position">
    <label class="np-vol" title="Volume">${ic('music')}<input type="range" id="npVol" min="0" max="100" value="${Math.round(S.musicVol * 100)}" aria-label="Volume"><span class="num" id="npVolTxt">${Math.round(S.musicVol * 100)}%</span></label>
    <button class="iconbtn" data-action="np-stop" aria-label="Stop">${ic('x')}</button>`;
  updateNow();
}
function updateNow() {
  const a = $('#audio'), s = $('#npSeek'), tm = $('#npTime'); if (!s) return;
  if (a.duration && !s.matches(':active')) s.value = Math.round(a.currentTime / a.duration * 1000);
  tm.textContent = `${dur(a.currentTime)} / ${a.duration ? dur(a.duration) : '-:--'}`;
}
$('#audio').addEventListener('timeupdate', updateNow);
$('#audio').addEventListener('ended', () => { S.playing = null; render(); });
document.addEventListener('input', e => {
  if (e.target.id === 'npVol') { S.musicVol = +e.target.value / 100; $('#audio').volume = S.musicVol; $('#npVolTxt').textContent = e.target.value + '%'; lsSet('musicVol', S.musicVol); }
  if (e.target.id === 'npSeek') { const a = $('#audio'); if (a.duration) a.currentTime = +e.target.value / 1000 * a.duration; }
});

document.addEventListener('click', async e => {
  const t = e.target.closest('[data-action]'); if (!t) return;
  const a = t.dataset.action, id = t.dataset.id, kind = t.dataset.kind;
  switch (a) {
    case 'nav': S.page = t.dataset.page; S.q = ''; S.detail = null; S.detailRec = null; S.jobsOpen = false; $('#toastHost').innerHTML = ''; closeDialog();
      if (S.page === 'shorts' && !S.queueOpen && S.queue.length) S.queueOpen = true;
      if (S.page === 'music' && S.musicTab === 'ncs' && !S.ncsItems) ncsSearch();
      API().settings_set({last_page: S.page}); render(); $('#main').scrollTop = 0; break;
    case 'toggle-queue': S.queueOpen = !S.queueOpen; render(); break;
    case 'toggle-jobs': S.jobsOpen = !S.jobsOpen; render(); break;
    case 'show-jobs': S.jobsOpen = true; S.detail = null; $('#toastHost').innerHTML = ''; render(); break;
    case 'clear-jobs': await API().clear_jobs(); await pollJobs(); render(); break;
    case 'view': S.view = t.dataset.view; lsSet('view', S.view); render(); break;
    case 'refresh': t.disabled = true; await Promise.all([loadFootage(), loadShorts(), loadMerged(), loadMusic(), loadDisk()]); render(); toast('Folders scanned again'); break;
    case 'collapse': { const g = t.dataset.g; S.collapsed.has(g) ? S.collapsed.delete(g) : S.collapsed.add(g); lsSet('collapsed', [...S.collapsed]); render(); break; }
    case 'check': { e.stopPropagation(); const s = S.sel[kind]; s.has(id) ? s.delete(id) : s.add(id); render(); break; }
    case 'card': { const r = recById.get(id); if (!r) break;
      if (e.ctrlKey || e.shiftKey || e.metaKey) {  // Ctrl+click selects, like Explorer
        if (!selectable(r)) { toast(effStatus(r) === 'recording' ? 'This file is still being recorded' : 'This recording is being processed', 'Wait for it to finish before selecting it.'); break; }
        const s = S.sel.footage; s.has(id) ? s.delete(id) : s.add(id); render(); break;
      }
      S.detailRec = id; S.detail = null; S.jobsOpen = false; render(); break; }
    case 'open-clip':
      if (e.ctrlKey || e.shiftKey || e.metaKey) { const s = S.sel.shorts; s.has(id) ? s.delete(id) : s.add(id); render(); break; }
      S.detail = id; S.detailRec = null; S.jobsOpen = false; render(); break;
    case 'close-detail': S.detail = null; S.detailRec = null; render(); break;
    case 'view-set': { const set = D.sets.find(s => s.id === id); if (!set) break;
      S.page = 'shorts'; S.detailRec = null; S.q = ''; S.minScore = 0; S.collapsed.delete('s:' + set.game); S.collapsed.delete('r:' + set.id); lsSet('collapsed', [...S.collapsed]);
      render(); const el = document.querySelector(`[data-set-id="${set.id}"]`); if (el) el.scrollIntoView({block: 'start'}); break; }
    case 'make-one': { const n = await API().make_highlights([t.dataset.p]); toast(n ? 'Started a highlight job' : 'Nothing to start', n ? 'Follow it here or under Jobs.' : 'It may already be queued.'); await pollJobs(); render(); break; }
    case 'del-rec-one': deleteDialog('footage', [recById.get(id)].filter(Boolean)); break;
    case 'collapse-sets': { const sets = D.sets.filter(s => s.game === t.dataset.g);
      sets.forEach(s => t.dataset.mode === 'collapse' ? S.collapsed.add('r:' + s.id) : S.collapsed.delete('r:' + s.id)); lsSet('collapsed', [...S.collapsed]); render(); break; }
    case 'open-url': e.preventDefault(); API().open_url(t.dataset.url); break;
    case 'yt-setup': await refreshYt(); ytGuide(); break;
    case 'yt-client': { const r = await API().yt_choose_client(); if (!r.ok && r.error) toast("That file didn't work", r.error);
      await refreshYt(); if (dlg.open) ytGuide(); render(); break; }
    case 'rec-toggle': {
      t.disabled = true;
      const r = await API().rec_toggle();
      if (!r.ok) { t.disabled = false; toast("Can't control recording", r.error, ['Settings', 'nav', 'settings']); break; }
      await pollJobs(); break; }
    case 'yt-signin': { t.disabled = true; toast('Finish signing in in your browser', 'Choose your channel\'s Google account, then Advanced → Go to Highlight Studio.');
      const r = await API().yt_sign_in(); await refreshYt();
      toast(r.ok && D.yt.signed_in ? `Signed in as ${D.yt.channel.title}` : "Sign-in didn't finish", r.ok ? (D.yt.error || '') : r.error);
      if (dlg.open) ytGuide(); render(); break; }
    case 'yt-signout': await API().yt_sign_out(); await refreshYt(); toast('Signed out of YouTube'); render(); break;
    case 'upload-yt': { const m = D.merged.find(x => x.id === id); if (!m) break; t.disabled = true; await refreshYt();
      if (!D.yt.signed_in && D.yt.client) {  // set up before but the sign-in expired (Testing mode: weekly): sign in, then continue
        toast('Signing in to YouTube', 'Finish in your browser. The upload form opens right after.');
        const r = await API().yt_sign_in(); await refreshYt();
        if (!r.ok) toast("Sign-in didn't finish", r.error);
      }
      t.disabled = false;
      if (D.yt.signed_in) uploadDialog(m); else if (!D.yt.client) ytGuide(); break; }
    case 'yt-upload': startUpload(); break;
    case 'fs-enter': enterTheater(t.closest('.vwrap')); break;
    case 'fs-exit': exitTheater(); break;
    case 'playbooks': openPlaybooks(); break;
    case 'pb-pick': S.pbSel = t.dataset.id; renderPlaybook(); break;
    case 'pb-jump': { const hs = dlg.querySelectorAll('.md h2'); const h = hs[+t.dataset.i]; if (h) h.scrollIntoView({block: 'start', behavior: 'smooth'}); break; }
    case 'pb-reveal': { const pb = (S.pbList || []).find(p => p.id === S.pbSel); if (pb) API().reveal_playbook(pb.file); break; }
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
    case 'play-local': { const tr = D.tracks.find(x => x.id === id); if (tr) playAudio(tr.path, mediaUrl(tr.path), {title: tr.title || tr.file, artist: tr.artist}); break; }
    case 'np-toggle': { const a = $('#audio'); if (a.paused) a.play().catch(() => {}); else a.pause(); setTimeout(renderNow, 50); break; }
    case 'np-stop': $('#audio').pause(); S.playing = null; render(); break;
    case 'play-ncs': { const slug = t.dataset.slug, key = 'ncs:' + slug;
      if (S.playing === key) { playAudio(key); break; }
      t.disabled = true; const info = await API().ncs_track(slug); t.disabled = false;
      const n = (S.ncsItems || []).find(x => x.slug === slug) || {};
      if (info.ok && info.preview) playAudio(key, info.preview, {title: n.title, artist: n.artist}); else toast('No preview for this track', info.error || ''); break; }
    case 'ncs-search': S.ncsQ = ($('#ncsQ') || {}).value || ''; ncsSearch(); break;
    case 'get-ncs': { const n = (S.ncsItems || []).find(x => x.slug === t.dataset.slug); if (!n) break;
      if (!S.settings.watch_downloads) toast('Adding from Downloads is off', 'Turn it on in Settings, or import the file yourself after downloading.');
      await API().ncs_get(n); toast(`Opened "${n.title}" on ncs.io`, 'Click Download on that page. Studio adds the file when it lands in Downloads.'); await pollJobs(); render(); break; }
    case 'ncs-cancel': await API().ncs_cancel(t.dataset.slug); toast('Stopped waiting for that download', 'If you download it later, import it from Other sources.'); await pollJobs(); render(); break;
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
  if (e.target.id === 'mvol') { S.merge.mvol = +e.target.value; $('#mvolTxt').textContent = e.target.value + '%'; }
  if (e.target.id === 'linkIn') S.link = e.target.value;
  if (e.target.id === 'ncsQ') S.ncsQ = e.target.value;
});
document.addEventListener('keydown', e => {
  if (e.target.id === 'recKey') {
    e.preventDefault();
    const k = e.key.length === 1 ? e.key.toUpperCase() : e.key;
    if (!/^[A-Z0-9]$|^F\d{1,2}$/.test(k)) return;
    const hk = [e.ctrlKey && 'Ctrl', e.shiftKey && 'Shift', e.altKey && 'Alt', e.metaKey && 'Win', k].filter(Boolean).join('+');
    e.target.value = hk; S.settings.rec_hotkey = hk; API().settings_set({rec_hotkey: hk});
    if (D.rec) D.rec.hotkey = hk; renderRec(); toast('Record hotkey saved', hk); return;
  }
  if (theaterEl && e.key === 'Escape') { e.preventDefault(); exitTheater(); return; }
  if (e.target.id === 'ncsQ' && e.key === 'Enter') { ncsSearch(); return; }
  if (e.target.id === 'linkIn' && e.key === 'Enter') { document.querySelector('[data-action="lookup"]')?.click(); return; }
  if (e.target.matches('input,select,textarea') || dlg.open) return;
  if (e.key === 'Escape') {  // closes the Jobs popup first, then the details panel
    if (S.jobsOpen) { S.jobsOpen = false; render(); } else if (S.detail || S.detailRec) { S.detail = null; S.detailRec = null; render(); }
  }
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
  if (id === 'mixSel') { S.merge.mix = e.target.value; saveMergeOpts(); renderQueue(); }
  if (id === 'mvol') saveMergeOpts();
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
  S.musicVol = lsGet('musicVol', 0.5); S.detailW = lsGet('detailW', DDEF);
  S.queue = lsGet('queue', []); S.queueW = lsGet('queueW', QDEF); S.view = lsGet('view', 'grid'); S.sort = lsGet('sort', 'newest'); S.collapsed = new Set(lsGet('collapsed', []));
  const open = /open=([a-z]+)(?::([a-z]+))?/.exec(location.hash || '');
  if (open) { S.page = open[1]; if (open[2] === 'queue') S.queueOpen = true; else if (open[2] === 'jobs') S.jobsOpen = true; else if (open[2] && S.page === 'music') S.musicTab = open[2]; }
  S.queueOpen = S.queueOpen || (S.page === 'shorts' && S.queue.length > 0);
  render();
  await pollJobs();
  await Promise.all([loadFootage().then(render), loadShorts().then(render), loadMerged(), loadMusic()]);
  render();
  if (S.page === 'music' && S.musicTab === 'ncs') ncsSearch();
  if (open && open[2] === 'playbooks') openPlaybooks();
  if (open && open[2] === 'ytguide') { await refreshYt(); ytGuide(); }
  if (DEMO) {
    const long = D.sets.flatMap(s => s.clips).sort((a, b) => b.title.length - a.title.length).slice(0, 4);
    S.queue = long.map(c => c.path); S.merge.name = 'A very long merged video name for the weekend Valorant and Arena Breakout montage';
    S.queueOpen = true; S.jobsOpen = open[2] !== 'demoq'; render();
  }
  if (open && open[2] === 'detail' && S.page === 'footage') {
    const r = D.footage.find(x => x.status === 'done') || D.footage[0]; if (r) { S.detailRec = r.id; render(); }
  }
  refreshYt().then(() => { if (S.page === 'settings') render(); });
  API().rec_info().then(ri => { D.recInfo = ri; if (S.page === 'settings') render(); });
  // polling: jobs every second while something runs, every 4 s when idle; nothing but
  // a slow jobs check while the window is minimised or hidden
  let tick = 0;
  setInterval(() => {
    tick++;
    const busy = D.jobs.some(j => j.state === 'running' || j.state === 'queued') || (D.watch && (D.watch.waiting.length || D.watch.ytal)) || (D.rec && (D.rec.phase === 'starting' || D.rec.phase === 'stopping'));
    if (tick % 15 === 0 && !document.hidden) tickRec();
    if (document.hidden ? tick % 10 === 0 : (busy || tick % 4 === 0)) pollJobs();
  }, 1000);
  setInterval(() => { if (!document.hidden) loadDisk(); }, 30000);
  setInterval(async () => {  // pick up new or finished recordings without a manual refresh
    if (document.hidden || S.page !== 'footage' || dlg.open || document.querySelector('.card:hover')) return;
    const sig = () => JSON.stringify(D.footage.map(r => [r.id, r.status, r.status === 'recording' ? 0 : r.size]));
    const before = sig();
    await loadFootage();
    if (sig() !== before) return render();
    // only a recording in progress grew: update its size text, no re-render
    for (const r of D.footage) if (r.status === 'recording') document.querySelectorAll(`[data-rsize="${r.id}"]`).forEach(el => { el.textContent = size(r.size); });
  }, 20000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) { pollJobs(); loadDisk(); } });
}
if (window.pywebview && window.pywebview.api) boot(); else window.addEventListener('pywebviewready', boot);
})();
