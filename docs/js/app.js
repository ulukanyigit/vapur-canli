import { Timetable, VESSEL, clock, hm, istanbulSecondOfDay, istanbulWeekday, pointAt } from './schedule.js';
import { buildStyle } from './style.js';

/* global maplibregl */

// ---------------------------------------------------------------- zaman
// ?saat=08:15 ile başka bir saatten başlat, ?hiz=30 ile zamanı hızlandır (test ve ileride oynatıcı için)
const qs = new URLSearchParams(location.search);
const SPEED = Math.max(1, Math.min(600, Number(qs.get('hiz')) || 1));
const OFFSET = qs.get('saat') ? hm(qs.get('saat')) - istanbulSecondOfDay() : 0;
const T0 = performance.now();
const BASE = istanbulSecondOfDay();
const now = () => (((BASE + OFFSET + ((performance.now() - T0) / 1000) * SPEED) % 86400) + 86400) % 86400;
const simulated = OFFSET !== 0 || SPEED !== 1;

const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
const isWide = () => matchMedia('(min-width: 900px)').matches;
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// ---------------------------------------------------------------- veri
const network = await fetch('data/network.json').then((r) => r.json());
// ?gun=0..6 (0 = Pazartesi) ile başka bir günün tarifesi denenebilir
const DAY_OVERRIDE = qs.has('gun') ? Math.max(0, Math.min(6, Number(qs.get('gun')))) : null;
const today = () => DAY_OVERRIDE ?? istanbulWeekday();
let tt = new Timetable(network, today());
const vessel = (op) => VESSEL[op] ?? VESSEL['Şehir Hatları'];
const piers = tt.piers;
const pierName = (id) => piers.get(id)?.name ?? id;

// ---------------------------------------------------------------- harita
const HOME = isWide()
  ? { center: [29.012, 41.045], zoom: 12.4, pitch: 60, bearing: -24 }
  : { center: [29.004, 41.012], zoom: 12.1, pitch: 55, bearing: -18 };

const map = new maplibregl.Map({
  container: 'map',
  style: buildStyle(),
  ...HOME,
  maxPitch: 75,
  maxBounds: [[28.62, 40.70], [29.52, 41.36]],
  attributionControl: { compact: true },
  hash: false,
});
map.touchZoomRotate.enableRotation();
map.on('error', (e) => console.warn('[vapur] harita hatası', e?.error?.message || e));
window.__vapur = { map, tt };

await new Promise((r) => map.once('load', r));
// Atıf kutusu mobilde kapalı başlasın (i düğmesiyle açılır)
if (!isWide()) document.querySelector('.maplibregl-ctrl-attrib')?.classList.remove('maplibregl-compact-show');

map.addSource('lines', { type: 'geojson', data: linesFC() });
map.addSource('line-sel', { type: 'geojson', data: fc([]) });
map.addSource('piers', { type: 'geojson', data: piersFC() });
map.addSource('wakes', { type: 'geojson', data: fc([]), lineMetrics: true });
map.addSource('hulls', { type: 'geojson', data: fc([]) });
map.addSource('dots', { type: 'geojson', data: fc([]) });

map.addLayer({
  id: 'route', type: 'line', source: 'lines',
  layout: { 'line-cap': 'round', 'line-join': 'round' },
  paint: {
    'line-color': '#CFE3DF',
    'line-opacity': 0.26,
    'line-width': ['interpolate', ['linear'], ['zoom'], 10, 0.8, 15, 1.8],
    'line-dasharray': [2, 2.5],
  },
}, 'building-3d');
map.addLayer({
  id: 'route-sel', type: 'line', source: 'line-sel',
  layout: { 'line-cap': 'round', 'line-join': 'round' },
  paint: {
    'line-color': '#E39B2D',
    'line-opacity': 0.95,
    'line-width': ['interpolate', ['linear'], ['zoom'], 10, 2, 15, 4],
  },
}, 'building-3d');
map.addLayer({
  id: 'wake', type: 'line', source: 'wakes',
  layout: { 'line-cap': 'round' },
  paint: {
    'line-width': ['interpolate', ['exponential', 2], ['zoom'], 11, 2, 14, 7, 17, 22],
    'line-gradient': ['interpolate', ['linear'], ['line-progress'], 0, 'rgba(242,244,239,0)', 0.7, 'rgba(242,244,239,0.28)', 1, 'rgba(242,244,239,0.75)'],
    'line-opacity': ['interpolate', ['linear'], ['zoom'], 11, 0, 12, 1],
  },
}, 'building-3d');
map.addLayer({
  id: 'pier-dot', type: 'circle', source: 'piers',
  paint: {
    'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 2.5, 15, 6],
    'circle-color': ['case', ['boolean', ['feature-state', 'sel'], false], '#E39B2D', '#F2F4EF'],
    'circle-stroke-color': '#0E2A2F',
    'circle-stroke-width': 1.5,
    'circle-pitch-alignment': 'map',
  },
});
map.addLayer({
  id: 'ferry-3d', type: 'fill-extrusion', source: 'hulls',
  paint: {
    'fill-extrusion-color': ['get', 'color'],
    'fill-extrusion-base': ['get', 'base'],
    'fill-extrusion-height': ['get', 'height'],
    'fill-extrusion-opacity': ['interpolate', ['linear'], ['zoom'], 11.4, 0, 11.9, 1],
    'fill-extrusion-vertical-gradient': true,
  },
});
map.addLayer({
  id: 'ferry-dot', type: 'circle', source: 'dots',
  paint: {
    'circle-radius': ['interpolate', ['linear'], ['zoom'], 9, 3.5, 12, 6.5],
    'circle-color': ['match', ['get', 'sig'], 'live', '#2E9E6B', '#0F3A41'],
    'circle-stroke-color': ['match', ['get', 'sig'], 'live', '#F2F4EF', 'lost', '#C8463A', '#E39B2D'],
    'circle-stroke-width': ['case', ['get', 'sel'], 3.5, 2.2],
    'circle-opacity': ['interpolate', ['linear'], ['zoom'], 11.3, ['get', 'fade'], 11.8, 0],
    'circle-stroke-opacity': ['interpolate', ['linear'], ['zoom'], 11.3, ['get', 'fade'], 11.8, 0],
    'circle-pitch-alignment': 'map',
  },
});
// 3D gövde görünürken durum halkası suyun üstünde kalsın
map.addLayer({
  id: 'ferry-ring', type: 'circle', source: 'dots',
  paint: {
    'circle-radius': ['interpolate', ['exponential', 2], ['zoom'], 11.3, 11, 13, 16, 16, 34],
    'circle-color': 'rgba(0,0,0,0)',
    'circle-stroke-color': ['match', ['get', 'sig'], 'live', '#2E9E6B', 'lost', '#C8463A', '#E39B2D'],
    'circle-stroke-width': ['case', ['get', 'sel'], 3, 1.6],
    'circle-stroke-opacity': ['interpolate', ['linear'], ['zoom'], 11.3, 0, 11.8, ['*', ['get', 'fade'], ['case', ['get', 'sel'], 1, 0.75]]],
    'circle-pitch-alignment': 'map',
  },
}, 'ferry-3d');
map.addLayer({
  id: 'pier-label', type: 'symbol', source: 'piers',
  minzoom: 11.2,
  layout: {
    'text-field': ['get', 'name'],
    'text-font': ['Noto Sans Bold'],
    'text-size': ['interpolate', ['linear'], ['zoom'], 11, 11, 15, 14],
    'text-offset': [0, 1.1], 'text-anchor': 'top',
    'text-padding': 4,
  },
  paint: { 'text-color': '#F2F4EF', 'text-halo-color': '#0F3A41', 'text-halo-width': 1.6 },
});

// ---------------------------------------------------------------- geometri yardımcıları
function fc(features) { return { type: 'FeatureCollection', features }; }
function linesFC() {
  // Aynı güzergâhı kullanan desenler üst üste binmesin: her geometri bir kez çizilir
  const seen = new Set();
  const feats = [];
  for (const l of network.patterns) {
    const key = JSON.stringify(l.coords);
    if (seen.has(key)) continue;
    seen.add(key);
    feats.push({ type: 'Feature', properties: { id: l.id }, geometry: { type: 'LineString', coordinates: l.coords } });
  }
  return fc(feats);
}
function piersFC() {
  return fc(network.piers.map((p, i) => ({ type: 'Feature', id: i, properties: { id: p.id, name: p.name }, geometry: { type: 'Point', coordinates: [p.lon, p.lat] } })));
}
const pierFeatureId = new Map(network.piers.map((p, i) => [p.id, i]));

// Yerel metre koordinatlarını (x = pruva yönü, y = sancak) boylam/enleme çevirir
function placer(c, headingDeg) {
  const h = (headingDeg * Math.PI) / 180;
  const fx = Math.sin(h), fy = Math.cos(h);     // pruva (doğu, kuzey)
  const sx = Math.cos(h), sy = -Math.sin(h);    // sancak
  const mLat = 1 / 111320, mLon = 1 / (111320 * Math.cos((c[1] * Math.PI) / 180));
  return ([x, y]) => [c[0] + (x * fx + y * sx) * mLon, c[1] + (x * fy + y * sy) * mLat];
}
function poly(place, pts) { const ring = pts.map(place); ring.push(ring[0]); return { type: 'Polygon', coordinates: [ring] }; }

function vesselParts(c, heading, op, s) {
  const { length: L, beam: B } = vessel(op);
  const l = L * s, b = B * s, hs = Math.pow(s, 0.85);
  const p = placer(c, heading);
  const hull = [[-l / 2, -b * 0.4], [-l / 2 + b * 0.25, -b / 2], [l / 2 - b * 1.1, -b / 2], [l / 2 - b * 0.4, -b * 0.3], [l / 2, 0],
    [l / 2 - b * 0.4, b * 0.3], [l / 2 - b * 1.1, b / 2], [-l / 2 + b * 0.25, b / 2], [-l / 2, b * 0.4]];
  const house = [[-l * 0.33, -b * 0.36], [l * 0.2, -b * 0.36], [l * 0.26, -b * 0.2], [l * 0.26, b * 0.2], [l * 0.2, b * 0.36], [-l * 0.33, b * 0.36]];
  const bridge = [[l * 0.08, -b * 0.3], [l * 0.22, -b * 0.3], [l * 0.22, b * 0.3], [l * 0.08, b * 0.3]];
  const funnel = [[-l * 0.08, -b * 0.13], [l * 0.0, -b * 0.13], [l * 0.0, b * 0.13], [-l * 0.08, b * 0.13]];
  return [
    { g: poly(p, hull), base: 0, height: 3.2 * hs, color: '#E9E6DC' },
    { g: poly(p, house), base: 3.2 * hs, height: 8.4 * hs, color: '#FBFBF7' },
    { g: poly(p, bridge), base: 8.4 * hs, height: 11 * hs, color: '#D8E1DE' },
    { g: poly(p, funnel), base: 8.4 * hs, height: 15.5 * hs, color: '#E39B2D' },
  ];
}

// ---------------------------------------------------------------- canlandırma
let selected = { type: null, id: null };   // {type:'ferry'|'pier', id}
let lastActive = [];
let follow = false;

function frame() {
  const t = now();
  const z = map.getZoom();
  const s = Math.max(1, Math.min(7, Math.pow(2, 15.3 - z)));   // uzaktan görünürlük için ölçek
  const active = tt.active(t);
  lastActive = active;
  const hulls = [], dots = [], wakes = [];
  for (const a of active) {
    const st = a.state;
    const isSel = selected.type === 'ferry' && selected.id === a.trip.id;
    dots.push({ type: 'Feature', properties: { id: a.trip.id, sig: 'plan', sel: isSel, fade: st.fade }, geometry: { type: 'Point', coordinates: st.lngLat } });
    if (z > 11.3) {
      for (const part of vesselParts(st.lngLat, st.heading, a.line.operator, s)) {
        hulls.push({ type: 'Feature', properties: { id: a.trip.id, base: part.base, height: part.height * st.fade, color: part.color }, geometry: part.g });
      }
      if (st.speedKn > 1.5) {
        const len = Math.min(900, st.speedKn * 26 * Math.min(s, 3.5));
        const sign = a.trip.dir === 0 ? -1 : 1;
        const coords = [];
        for (let k = 8; k >= 0; k--) coords.push(pointAt(a.line, st.distance + sign * (len * k) / 8 + sign * 0.35 * vessel(a.line.operator).length * s).lngLat);
        wakes.push({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: coords } });
      }
    }
  }
  map.getSource('hulls').setData(fc(hulls));
  map.getSource('dots').setData(fc(dots));
  map.getSource('wakes').setData(fc(wakes));

  if (follow && selected.type === 'ferry') {
    const a = active.find((x) => x.trip.id === selected.id);
    if (a) map.jumpTo({ center: a.state.lngLat });
  }
}

let raf = 0, lastDraw = 0;
function loop(ts) {
  raf = requestAnimationFrame(loop);
  if (document.hidden) return;
  if (ts - lastDraw < 50) return;          // ~20 fps yeterli: hareket zamandan hesaplanıyor, atlama olmaz
  lastDraw = ts;
  frame();
}
raf = requestAnimationFrame(loop);

// ---------------------------------------------------------------- saat ve panel
const $clock = document.getElementById('clock');
const $clockNote = document.getElementById('clockNote');
const $sheet = document.getElementById('sheet');
const $body = document.getElementById('sheetBody');

function tick() {
  if (!simulated && DAY_OVERRIDE == null && istanbulWeekday() !== tt.weekday) tt = new Timetable(network, today());   // gece yarısı yeni gün
  const t = now();
  $clock.textContent = clock(t);
  $clockNote.textContent = simulated ? (SPEED > 1 ? `Benzetim ×${SPEED}` : 'Benzetim saati') : '';
  render();
}
setInterval(tick, 1000);

const mins = (sec) => Math.max(0, Math.round(sec / 60));
const minHTML = (sec) => (sec < 45 ? '<span class="min now">şimdi</span>' : `<span class="min">${mins(sec)}<small>dk</small></span>`);
const statusChip = () => '<button class="status" data-about><span class="sig sig--plan" aria-hidden="true"></span>Tarifeden tahmin</button>';
const backBtn = () => '<button class="back" data-home><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg>Tüm iskeleler</button>';

let homeQuery = '';
let userPos = null;

function render() {
  const t = now();
  if (selected.type === 'ferry') return renderFerry(t);
  if (selected.type === 'pier') return renderPier(t);
  return renderHome(t);
}

// İskeleye bir sonraki uğrayış; gün bittiyse ertesi sabahın ilk seferi
function nextCall(pierId, t) {
  const today = tt.arrivalsAt(pierId, t, 86400 - t)[0];
  if (today) return { time: today.time, tomorrow: false };
  const first = tt.arrivalsAt(pierId, 0, 86400)[0];
  return first ? { time: first.time, tomorrow: true } : null;
}

function renderHome(t) {
  const sailing = lastActive.filter((a) => a.state.phase === 'sail').length;
  const keepFocus = document.activeElement?.id === 'pierSearch';
  let list = network.piers.map((p) => {
    const next = nextCall(p.id, t);
    const dist = userPos ? Math.hypot((p.lon - userPos[0]) * 84, (p.lat - userPos[1]) * 111) : null;
    return { p, next, dist };
  });
  const q = homeQuery.trim().toLocaleLowerCase('tr');
  if (q) list = list.filter(({ p }) => p.name.toLocaleLowerCase('tr').includes(q) || p.area.toLocaleLowerCase('tr').includes(q));
  list.sort((a, b) => (userPos ? a.dist - b.dist : a.p.name.localeCompare(b.p.name, 'tr')));

  const head = sailing > 0
    ? `<p class="kicker">Şu an denizde</p><h1 class="headline">${sailing} vapur</h1>`
    : `<p class="kicker">Şu an denizde vapur yok</p><h1 class="headline">İlk sefer ${clock(tt.firstDepartureAfter(t))}</h1>`;
  const html = `${head}
    <div class="row">${statusChip()}</div>
    <div class="search">
      <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5L21 21"/></svg>
      <input id="pierSearch" type="search" placeholder="İskele ara" autocomplete="off" value="${esc(homeQuery)}" aria-label="İskele ara">
    </div>
    ${userPos ? '<p class="note" style="margin:0 0 4px">Sana en yakın iskeleler üstte.</p>' : ''}
    <ul class="piers">${list.map(({ p, next, dist }) => `
      <li><button data-pier="${p.id}">
        <span><b>${esc(p.name)}</b><br><span>${esc(p.area)}${dist != null ? `, ${dist < 1 ? Math.round(dist * 1000) + ' m' : dist.toFixed(1) + ' km'}` : ''}</span></span>
        <span class="next">${!next ? 'sefer yok' : next.tomorrow ? `yarın ${clock(next.time)}` : next.time - t < 45 ? 'şimdi' : next.time - t <= 5400 ? mins(next.time - t) + ' dk' : clock(next.time)}</span>
      </button></li>`).join('') || '<li class="empty">Bu adla bir iskele yok. Yazımı kontrol et ya da listeden seç.</li>'}
    </ul>`;
  if (!keepFocus) { $body.innerHTML = html; return; }
  // Arama yazılırken input'u yeniden kurma: sadece listeyi güncelle
  const tmp = document.createElement('div'); tmp.innerHTML = html;
  $body.querySelector('.piers').replaceWith(tmp.querySelector('.piers'));
  $body.querySelector('.headline').replaceWith(tmp.querySelector('.headline'));
}

function renderPier(t) {
  const p = piers.get(selected.id);
  const arr = tt.arrivalsAt(p.id, t, 2 * 3600);
  const incoming = arr.filter((a) => !a.isOrigin);
  const leaving = arr.filter((a) => !a.isTerminus);
  const item = (a, mode) => {
    const other = mode === 'in' ? `${pierName(a.from)} yönünden` : `${pierName(a.to)} yönüne`;
    return `<li><button data-ferry="${a.trip.id}" ${a.onWater || a.time - t < 180 ? '' : 'data-future'}>
      ${minHTML(a.time - t)}
      <span class="what"><b>${esc(a.line.name)}</b><span>${esc(other)}, ${esc(a.line.operator)}</span></span>
      <time>${clock(a.time)}</time></button></li>`;
  };
  $body.innerHTML = `${backBtn()}
    ${p.area !== p.name ? `<p class="kicker">${esc(p.area)}</p>` : '<p class="kicker">İskele</p>'}
    <h1 class="headline">${esc(p.name)}</h1>
    <div class="row">${statusChip()}</div>
    <h2 class="section-title">Yanaşacak vapurlar</h2>
    <ul class="board">${incoming.slice(0, 6).map((a) => item(a, 'in')).join('') || '<li class="empty">Önümüzdeki iki saatte bu iskeleye yanaşan sefer yok.</li>'}</ul>
    <h2 class="section-title">Buradan kalkışlar</h2>
    <ul class="board">${leaving.slice(0, 8).map((a) => item(a, 'out')).join('') || '<li class="empty">Önümüzdeki iki saatte buradan kalkış yok.</li>'}</ul>
    <p class="note">Saatler İBB Açık Veri Portalı'nın tarife verisinden (Şehir Hatları kısmı 2023 tarihli). Güncel tarifeyle farklar olabilir.</p>`;
}

function renderFerry(t) {
  const tr = tt.byId.get(selected.id);
  if (!tr) { selected = { type: null, id: null }; return renderHome(t); }
  const line = tt.lines.get(tr.line);
  const a = lastActive.find((x) => x.trip.id === tr.id);
  const from = pierName(line.stops[tr.order[0]]);
  const to = pierName(line.stops[tr.order[tr.order.length - 1]]);
  let main;
  if (!a) {
    const done = t > tr.end;
    main = `<p class="empty">${done ? `Bu sefer ${clock(tr.end)}'da ${esc(to)} iskelesine vardı.` : `Bu sefer ${clock(tr.start)}'da ${esc(from)} iskelesinden kalkacak.`}</p>`;
  } else {
    const st = a.state;
    const etaSec = st.phase === 'board' ? tr.start - t : st.eta - t;
    const target = st.phase === 'board' ? from : pierName(st.nextStop);
    const label = st.phase === 'board' ? 'kalkışa' : st.phase === 'dwell' ? `${esc(pierName(st.nextStop))} yönüne kalkışa` : 'varışa';
    main = `
      <div class="eta" aria-live="polite">
        <span class="eta__min">${etaSec < 45 ? '0' : mins(etaSec)}<sub>dk</sub></span>
        <span class="eta__to"><span>${st.phase === 'sail' ? 'Sonraki iskele' : st.phase === 'board' ? 'Şu an yolcu alıyor' : 'Şu an iskelede'}</span><b>${esc(target)}</b><span>${label} ${clock(st.phase === 'board' ? tr.start : st.eta)}</span></span>
      </div>
      <dl class="facts">
        <div><dt>Hız</dt><dd>${st.speedKn < 0.5 ? 'duruyor' : `${st.speedKn.toFixed(0)} kn`}</dd></div>
        <div><dt>Kalkış</dt><dd>${clock(tr.start)}</dd></div>
        <div><dt>Son iskele</dt><dd>${clock(tr.end)}</dd></div>
      </dl>
      <div class="btnrow"><button class="btn" data-follow aria-pressed="${follow}">${follow ? 'Takibi bırak' : 'Vapuru takip et'}</button></div>`;
  }
  const nextIdx = a ? a.state.nextIdx : (t > tr.end ? tr.order.length : 0);
  const stops = tr.order.map((i, k) => {
    const cls = k < nextIdx ? 'past' : k === nextIdx ? 'next' : '';
    const time = k === 0 ? tr.depart[0] : tr.arrive[k];
    return `<li class="${cls}"><span>${esc(pierName(line.stops[i]))}</span><time>${clock(time)}</time></li>`;
  }).join('');
  $body.innerHTML = `${backBtn()}
    <p class="kicker">${esc(line.operator)}</p>
    <h1 class="headline">${esc(from)} – ${esc(to)}</h1>
    <div class="row">${statusChip()}<span class="op">${esc(line.name)} hattı</span></div>
    ${main}
    <h2 class="section-title">Duraklar</h2>
    <ol class="stops">${stops}</ol>
    <p class="note">Konum ve süreler İBB'nin açık tarife verisinden hesaplanıyor; vapurun adı canlı veri bağlanınca görünecek. Gerçek vapur gecikmiş ya da erken olabilir.${line.approx_geom ? ' Bu hattın çizgisi yaklaşık.' : ''}</p>`;
}

// ---------------------------------------------------------------- seçim
function setFeatureSel(source, id, on) { if (id != null) map.setFeatureState({ source, id }, { sel: on }); }
function clearSel() {
  if (selected.type === 'pier') setFeatureSel('piers', pierFeatureId.get(selected.id), false);
  if (selected.type === 'ferry') map.getSource('line-sel').setData(fc([]));
}
function selectPier(id, fly = true) {
  clearSel(); follow = false;
  selected = { type: 'pier', id };
  setFeatureSel('piers', pierFeatureId.get(id), true);
  const p = piers.get(id);
  if (fly) camera({ center: [p.lon, p.lat], zoom: Math.max(map.getZoom(), 14.2), pitch: 58, offset: sheetOffset() });
  openSheet('half'); render(); $body.scrollTop = 0;
}
function selectFerry(id, fly = true) {
  clearSel();
  selected = { type: 'ferry', id };
  const tr = tt.byId.get(id);
  const ln = tt.lines.get(tr.line);
  map.getSource('line-sel').setData(fc([{ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: ln.coords } }]));
  const a = lastActive.find((x) => x.trip.id === id);
  if (fly && a) camera({ center: a.state.lngLat, zoom: Math.max(map.getZoom(), 14.3), pitch: 62, offset: sheetOffset() });
  openSheet('half'); render(); $body.scrollTop = 0;
}
function goHome() { clearSel(); follow = false; selected = { type: null, id: null }; render(); $body.scrollTop = 0; }
function sheetOffset() { return isWide() ? [200, 0] : [0, -Math.round(innerHeight * 0.22)]; }
function camera(opts) { reduceMotion ? map.jumpTo(opts) : map.easeTo({ ...opts, duration: 900 }); }

map.on('click', (e) => {
  const pad = 14;
  const box = [[e.point.x - pad, e.point.y - pad], [e.point.x + pad, e.point.y + pad]];
  const f = map.queryRenderedFeatures(box, { layers: ['ferry-3d', 'ferry-dot', 'ferry-ring'] })[0];
  if (f) return selectFerry(f.properties.id);
  const p = map.queryRenderedFeatures(box, { layers: ['pier-dot', 'pier-label'] })[0];
  if (p) return selectPier(p.properties.id);
});
for (const id of ['ferry-3d', 'ferry-dot', 'pier-dot', 'pier-label']) {
  map.on('mouseenter', id, () => { map.getCanvas().style.cursor = 'pointer'; });
  map.on('mouseleave', id, () => { map.getCanvas().style.cursor = ''; });
}
map.on('dragstart', () => { if (follow) { follow = false; render(); } });

$body.addEventListener('click', (e) => {
  const el = e.target.closest('button');
  if (!el) return;
  if (el.dataset.pier) selectPier(el.dataset.pier);
  else if (el.dataset.ferry) selectFerry(el.dataset.ferry, !('future' in el.dataset));
  else if ('home' in el.dataset) goHome();
  else if ('about' in el.dataset) document.getElementById('about').showModal();
  else if ('follow' in el.dataset) { follow = !follow; if (follow) map.easeTo({ zoom: Math.max(map.getZoom(), 14.5), duration: reduceMotion ? 0 : 600 }); render(); }
});
$body.addEventListener('input', (e) => { if (e.target.id === 'pierSearch') { homeQuery = e.target.value; render(); } });
$body.addEventListener('focusin', (e) => { if (e.target.id === 'pierSearch' && !isWide()) openSheet('full'); });

document.getElementById('aboutBtn').addEventListener('click', () => document.getElementById('about').showModal());
document.getElementById('viewBtn').addEventListener('click', () => { follow = false; camera({ ...HOME, offset: [0, 0] }); });
document.getElementById('locateBtn').addEventListener('click', () => {
  if (!navigator.geolocation) return;
  navigator.geolocation.getCurrentPosition((pos) => {
    userPos = [pos.coords.longitude, pos.coords.latitude];
    let best = null, bd = Infinity;
    for (const p of network.piers) { const d = Math.hypot((p.lon - userPos[0]) * 84, (p.lat - userPos[1]) * 111); if (d < bd) { bd = d; best = p; } }
    if (best && bd < 25) selectPier(best.id); else { goHome(); openSheet('half'); }
  }, () => { goHome(); }, { enableHighAccuracy: false, timeout: 8000, maximumAge: 60000 });
});

// ---------------------------------------------------------------- panel sürükleme (mobil)
const handle = document.getElementById('sheetHandle');
const order = ['peek', 'half', 'full'];
function openSheet(state) {
  if (isWide()) return;
  if (order.indexOf(state) <= order.indexOf($sheet.dataset.state) && state !== 'peek') return;
  setSheet(state);
}
function setSheet(state) {
  $sheet.dataset.state = state; $sheet.style.height = '';
  document.body.classList.toggle('sheet-half', state === 'half');
  handle.setAttribute('aria-expanded', String(state !== 'peek'));
}
handle.addEventListener('click', () => { const i = order.indexOf($sheet.dataset.state); setSheet(order[(i + 1) % 3]); });
let drag = null;
handle.addEventListener('pointerdown', (e) => { drag = { y: e.clientY, h: $sheet.getBoundingClientRect().height, moved: false }; handle.setPointerCapture(e.pointerId); });
handle.addEventListener('pointermove', (e) => {
  if (!drag) return;
  const dy = drag.y - e.clientY;
  if (Math.abs(dy) > 6) drag.moved = true;
  if (!drag.moved) return;
  $sheet.classList.add('dragging');
  $sheet.style.height = `${Math.max(120, Math.min(innerHeight - 72, drag.h + dy))}px`;
});
handle.addEventListener('pointerup', (e) => {
  if (!drag) return;
  $sheet.classList.remove('dragging');
  if (drag.moved) {
    const h = $sheet.getBoundingClientRect().height / innerHeight;
    setSheet(h < 0.33 ? 'peek' : h < 0.74 ? 'half' : 'full');
    e.preventDefault();
    handle.addEventListener('click', (ev) => ev.stopImmediatePropagation(), { once: true, capture: true });
  }
  drag = null;
});

tick();
