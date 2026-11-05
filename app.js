"use strict";
const SOURCES = [
  { k:'github', l:'GitHub', imgClass:'github', hint:'Most stars among repositories created in the last 12 months',
    metric: it => `<b>★ ${fmtNum(it.metric)}</b> stars`, rowMetric: it => `★ ${fmtNum(it.metric)} stars`, open:'Open on GitHub', short:'GitHub', empty:'repos' },
  { k:'steam',  l:'Steam',  imgClass:'steam',  hint:'Most players in game now among games released in the last 12 months',
    metric: it => `<b>🎮 ${fmtNum(it.metric)}</b> playing`, rowMetric: it => `🎮 ${fmtNum(it.metric)} playing`, open:'Open on Steam', short:'Steam', empty:'games' },
  { k:'itunes', l:'iTunes', imgClass:'itunes', hint:'Position in Apple’s Top Free Apps chart among apps released in the last 12 months',
    metric: it => `<b>Apple #${it.metric}</b> chart`, rowMetric: it => `Apple #${it.metric}`, open:'Open on App Store', short:'App Store', empty:'apps' },
];
const MONTHS = [1, 2, 3, 6, 12, 0];   // 0 = All
const rankTip = () => months ? 'Rank in the top 100 of the last 12 months' : 'Rank in the all-time top 100';
const $ = id => document.getElementById(id);
const ESC = { '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' };
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ESC[c]);
const safeUrl = u => { try { const x = new URL(u); return /^https?:$/.test(x.protocol) ? x.href : ''; } catch { return ''; } };
const pref = (k, f) => { try { return localStorage.getItem(k) ?? f; } catch { return f; } };
const setPref = (k, v) => { try { localStorage.setItem(k, String(v)); } catch {} };
const fmtNum = n => Number(n).toLocaleString('en-US');
const fmtDate = d => d ? new Date(d + 'T00:00:00Z').toLocaleDateString('en-US', { month:'short', day:'numeric', year:'numeric', timeZone:'UTC' }) : '—';
const span = m => `${m} month${m === 1 ? '' : 's'}`;
function ago(iso) {
  const t = new Date(iso).getTime(); if (!Number.isFinite(t)) return '—';
  const min = Math.max(0, Math.round((Date.now() - t) / 60000));
  return min < 60 ? `${min}m ago` : min < 1440 ? `${Math.floor(min / 60)}h ago` : `${Math.floor(min / 1440)}d ago`;
}

let source = pref('software_source', 'github'); if (!SOURCES.some(s => s.k === source)) source = 'github';
let months = parseInt(pref('software_months', '3'), 10); if (!MONTHS.includes(months)) months = 3;
let layout = pref('software_layout', 'tile') === 'rows' ? 'rows' : 'tile';
let sort = pref('software_sort', 'rank') === 'date' ? 'date' : 'rank';
const favs = new Map((() => { try { return Object.entries(JSON.parse(pref('software_favs2', '{}'))); } catch { return []; } })());
const saveFavs = () => setPref('software_favs2', JSON.stringify(Object.fromEntries(favs)));
let lookup = new Map();
const store = {};
const expanded = new Set();
const favKey = it => `${source}:${it.id}`;

async function load(src, force) {
  if (!force && src in store) return store[src];
  try {
    // Replaced dynamic Date.now() query parameter with a clean static resource fetch
    const r = await fetch(`data/${src}.json`, { cache:'default' });
    store[src] = r.ok ? await r.json() : null;
  } catch { store[src] = null; }
  return store[src];
}

function thumb(it, cls) {
  const u = safeUrl(it.image);
  return u ? `<img src="${esc(u)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : '<div class="thumb-fallback">No Image</div>';
}

function tileHtml(it, S) {
  const url = safeUrl(it.url), key = favKey(it), open = expanded.has(key);
  return `<article class="card">
    <div class="thumb-wrap ${S.imgClass}">${url ? `<a class="thumb-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer" aria-label="${esc(S.open)}">${thumb(it)}</a>` : thumb(it)}
      <label class="fav-toggle" title="Favorite"><input type="checkbox" class="fav-input" data-key="${esc(key)}" ${favs.has(key) ? 'checked' : ''}><span class="fav-star">★</span></label>
      ${it.rank ? `<div class="rank-pill" title="${esc(rankTip())}">#${it.rank}</div>` : ''}
    </div>
    <div class="body">
      <p class="title">${url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(it.title)}</a>` : esc(it.title)}</p>
      <p class="desc${open ? '' : ' clamp'}">${esc(it.desc || 'No description provided.')}</p>
      <button class="more" type="button" data-more="${esc(key)}"${open ? '' : ' hidden'}>${open ? 'See less' : 'See more'}</button>
      ${url ? `<a class="open-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(S.open)} <span>↗</span></a>` : ''}
      <div class="meta"><span>${esc(fmtDate(it.date))}</span><span>${S.metric(it)}</span></div>
    </div>
  </article>`;
}

function rowHtml(it, S) {
  const url = safeUrl(it.url), key = favKey(it);
  return `<div class="row-item">
    <label class="row-fav" title="Favorite"><input type="checkbox" class="fav-input" data-key="${esc(key)}" ${favs.has(key) ? 'checked' : ''}><span class="fav-star">★</span></label>
    <div class="row-thumb">${url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer" aria-label="${esc(S.open)}">${thumb(it)}</a>` : thumb(it)}</div>
    <span class="row-rank" title="${esc(rankTip())}">${it.rank ? '#' + it.rank : '—'}</span>
    <span class="row-title">${url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(it.title)}</a>` : esc(it.title)}</span>
    <span class="row-desc">${esc(it.desc || '—')}</span>
    <span class="row-date">${esc(fmtDate(it.date))}</span>
    <span class="row-metric">${esc(S.rowMetric(it))}</span>
    ${url ? `<a class="row-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(S.short)} <span>↗</span></a>` : '<span class="row-date">—</span>'}
  </div>`;
}

function rowsTableHtml(list, S, metricName) {
  return `<div class="rows-wrap"><div class="rows-table"><div class="rows-header-row"><span></span><span>Image</span><span>Rank</span><span>Name</span><span>Description</span><span>Launched</span><span>${esc(metricName)}</span><span>Link</span></div>${list.map(it => rowHtml(it, S)).join('')}</div></div>`;
}

function favEntries(items) {
  const live = new Map((items || []).map(it => [it.id, it]));
  const out = [];
  favs.forEach((snap, key) => {
    if (snap.src !== source) return;
    const cur = live.get(snap.id);
    out.push(cur ? { ...snap, ...cur, rank: cur.ranks && cur.ranks[months] || 0 } : { ...snap, rank: 0 });
  });
  return out;
}

async function render() {
  const S = SOURCES.find(s => s.k === source), out = $('out');
  const d = await load(source);
  if (S.k !== source) return;
  $('lastUpdated').textContent = d ? `Last updated: ${ago(d.updated)}` : 'Last updated: not yet';
  const items = d ? d.items : [];
  let list = items.filter(it => it.ranks && it.ranks[months]).map(it => ({ ...it, rank: it.ranks[months] }));
  list.sort((a, b) => a.rank - b.rank);
  if (sort === 'date') list.sort((a, b) => (b.date || '').localeCompare(a.date || '') || a.rank - b.rank);
  const favList = favEntries(items);
  lookup = new Map([...favList, ...list].map(it => [favKey(it), it]));
  $('count').textContent = `${list.length} ${S.empty} ${months ? `launched in the last ${span(months)}` : 'of all time'} · ranked by ${S.hint.split(' among')[0].toLowerCase()}`;
  const metricName = d && d.metric === 'stars' ? 'Stars' : d && d.metric === 'most played' ? 'Most Played' : 'Apple Ranking';
  const emptyMsg = `<div class="empty" style="grid-column:1 / -1;">${!d ? 'No data yet.' : 'Nothing in this window.'}</div>`;
  const head = n => `<div class="fav-box-header"><span class="fav-box-title">★ Favorites<span class="fav-box-count">(${n})</span></span><button class="clear-btn" type="button" data-clear>Clear</button></div>`;
  if (layout === 'rows') {
    const box = favList.length ? `<div class="rows-fav-section">${head(favList.length)}${rowsTableHtml(favList, S, metricName)}</div>` : '';
    out.innerHTML = box + (list.length ? rowsTableHtml(list, S, metricName) : emptyMsg);
  } else {
    const box = favList.length ? `<div class="fav-box" style="grid-column:span ${Math.min(favList.length, 3)};">${head(favList.length)}<div class="fav-box-items">${favList.map(it => tileHtml(it, S)).join('')}</div></div>` : '';
    out.innerHTML = `<div class="grid">${box}${list.length ? list.map(it => tileHtml(it, S)).join('') : emptyMsg}</div>`;
  }
  fitMore();
}

function fitMore() {
  document.querySelectorAll('.desc.clamp').forEach(p => {
    const b = p.nextElementSibling;
    if (b && b.classList.contains('more')) b.hidden = p.scrollHeight <= p.clientHeight + 1;
  });
}

function renderControls() {
  $('sources').innerHTML = SOURCES.map(s => `<button class="tab-btn${s.k === source ? ' active' : ''}" data-source="${s.k}" title="${esc(s.hint)}">${s.l}</button>`).join('');
  $('tabs').innerHTML = MONTHS.map(m => `<button class="tab-btn${m === months ? ' active' : ''}" data-months="${m}">${m ? span(m) : 'All'}</button>`).join('');
  document.querySelectorAll('[data-layout]').forEach(b => b.classList.toggle('active', b.dataset.layout === layout));
  document.querySelectorAll('[data-sort]').forEach(b => b.classList.toggle('active', b.dataset.sort === sort));
}

function setup() {
  $('sources').addEventListener('click', e => { const b = e.target.closest('[data-source]'); if (!b) return; source = b.dataset.source; setPref('software_source', source); renderControls(); render(); });
  $('tabs').addEventListener('click', e => { const b = e.target.closest('[data-months]'); if (!b) return; months = parseInt(b.dataset.months, 10); setPref('software_months', months); renderControls(); render(); });
  document.querySelectorAll('[data-layout]').forEach(b => b.addEventListener('click', () => { layout = b.dataset.layout; setPref('software_layout', layout); renderControls(); render(); }));
  document.querySelectorAll('[data-sort]').forEach(b => b.addEventListener('click', () => { sort = b.dataset.sort; setPref('software_sort', sort); renderControls(); render(); }));
  $('out').addEventListener('click', e => {
    if (e.target.closest('[data-clear]')) { [...favs].forEach(([k, v]) => { if (v.src === source) favs.delete(k); }); saveFavs(); render(); return; }
    const b = e.target.closest('[data-more]'); if (!b) return;
    const k = b.dataset.more, p = b.previousElementSibling, open = !expanded.has(k);
    open ? expanded.add(k) : expanded.delete(k);
    p.classList.toggle('clamp', !open);
    b.textContent = open ? 'See less' : 'See more';
  });
  $('out').addEventListener('change', e => {
    const i = e.target.closest('.fav-input'); if (!i) return;
    const key = i.dataset.key, it = lookup.get(key);
    if (i.checked && it) {
      const { rank, ranks, ...snap } = it;
      favs.set(key, { ...snap, ranks, src: source });
    } else favs.delete(key);
    saveFavs(); render();
  });
  $('refreshBtn').addEventListener('click', async () => {
    const b = $('refreshBtn'); b.disabled = true; b.textContent = 'Refreshing…';
    await load(source, true); await render(); b.disabled = false; b.textContent = 'Refresh';
  });
  document.addEventListener('error', e => {
    const t = e.target;
    if (t && t.tagName === 'IMG' && t.closest('#out')) {
      const box = document.createElement('div');
      box.className = 'thumb-fallback';
      box.textContent = 'No Image';
      t.replaceWith(box);
    }
  }, true);
  window.addEventListener('resize', fitMore);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(fitMore);
}

(async function init() {
  setup(); renderControls(); await render();
})();
