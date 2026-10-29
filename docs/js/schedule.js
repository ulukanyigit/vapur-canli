// Tarife modeli: hat geometrisi + sefer listesi -> zamana bağlı vapur konumu.
// Saf fonksiyonlar; DOM ve harita bilgisi yok, Node'da da test edilebilir.

const KNOT = 0.514444;          // m/s
const RAMP_S = 45;              // kalkış/yanaşma hızlanma süresi (sn)
const R = 6371008.8;

export const VESSEL = {
  'Şehir Hatları': { length: 68, beam: 14 },
  'Turyol': { length: 32, beam: 8 },
  'Dentur Avrasya': { length: 26, beam: 7 },
  'İDO': { length: 40, beam: 10 },
};

const rad = (d) => (d * Math.PI) / 180;
const deg = (r) => (r * 180) / Math.PI;

function haversine(a, b) {
  const dLat = rad(b[1] - a[1]);
  const dLon = rad(b[0] - a[0]);
  const s = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a[1])) * Math.cos(rad(b[1])) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
}

function bearing(a, b) {
  const y = Math.sin(rad(b[0] - a[0])) * Math.cos(rad(b[1]));
  const x = Math.cos(rad(a[1])) * Math.sin(rad(b[1])) - Math.sin(rad(a[1])) * Math.cos(rad(b[1])) * Math.cos(rad(b[0] - a[0]));
  return (deg(Math.atan2(y, x)) + 360) % 360;
}

/** "07:30" -> saniye */
export function hm(s) {
  const [h, m] = s.split(':').map(Number);
  return h * 3600 + m * 60;
}

/** saniye -> "07.30" (Türkçe saat yazımı) */
export function clock(sec) {
  const s = ((Math.round(sec) % 86400) + 86400) % 86400;
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${String(h).padStart(2, '0')}.${String(m).padStart(2, '0')}`;
}

/** İstanbul yerel saatine göre günün saniyesi (cihazın saat diliminden bağımsız). */
export function istanbulSecondOfDay(date = new Date()) {
  const p = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Europe/Istanbul', hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit',
  }).formatToParts(date);
  const g = (t) => Number(p.find((x) => x.type === t).value) % 24;
  return g('hour') * 3600 + g('minute') * 60 + g('second') + date.getMilliseconds() / 1000;
}

/** İstanbul'da bugün haftanın hangi günü: 0 = Pazartesi … 6 = Pazar */
export function istanbulWeekday(date = new Date()) {
  const wd = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Istanbul', weekday: 'short' }).format(date);
  return ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].indexOf(wd);
}

function prepareLine(line) {
  const c = line.coords;
  const cum = [0];
  for (let i = 1; i < c.length; i++) cum.push(cum[i - 1] + haversine(c[i - 1], c[i]));
  const total = cum[cum.length - 1];
  const k = total / (line.length_m || total || 1);   // TM30 -> küresel uzunluk düzeltmesi
  const stopDist = line.stop_m.map((d) => Math.min(total, d * k));
  stopDist[stopDist.length - 1] = total;
  return { ...line, cum, total, stopDist };
}

/** Desenden, verilen kalkış saniyesiyle bir sefer kurar. */
function makeTrip(line, start, tag) {
  const n = line.stops.length;
  const order = line.stops.map((_, i) => i);
  const arrive = line.arr.map((x) => start + x);
  const depart = line.dep.map((x) => start + x);
  const legs = [];
  for (let i = 0; i < n - 1; i++) {
    let t0 = depart[i];
    let t1 = arrive[i + 1];
    if (!(t1 > t0 + 30)) t1 = t0 + 60;               // bozuk süre verisine karşı
    // Tarifede bacak için gereğinden uzun süre varsa (veri hatası ya da bekleme), vapur iskelede bekler,
    // sonra makul bir hızla (10 kn) yola çıkar: suda 0,1 knotla sürünmesin
    const need = Math.abs(line.stopDist[i + 1] - line.stopDist[i]) / (10 * KNOT) + RAMP_S;
    if (t1 - t0 > need * 1.8) t0 = t1 - need;
    legs.push({ from: i, to: i + 1, dA: line.stopDist[i], dB: line.stopDist[i + 1], t0, t1 });
  }
  return { id: `${line.id}:${tag}:${start}`, line: line.id, dir: 0, order, legs, arrive, depart, start: depart[0], end: arrive[n - 1] };
}

/** Hat üzerinde mesafeden konum + yön. */
export function pointAt(line, dist) {
  const { coords: c, cum } = line;
  const d = Math.max(0, Math.min(line.total, dist));
  let lo = 0, hi = cum.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (cum[mid] <= d) lo = mid; else hi = mid;
  }
  const seg = cum[hi] - cum[lo] || 1;
  const f = (d - cum[lo]) / seg;
  const p = [c[lo][0] + (c[hi][0] - c[lo][0]) * f, c[lo][1] + (c[hi][1] - c[lo][1]) * f];
  // Yönü biraz ileriden/geriden ölç: köşelerde ani dönüş olmasın
  const a = rawPoint(line, Math.max(0, d - 60)), b = rawPoint(line, Math.min(line.total, d + 60));
  return { lngLat: p, heading: bearing(a, b) };
}

function rawPoint(line, d) {
  const { coords: c, cum } = line;
  let lo = 0, hi = cum.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (cum[mid] <= d) lo = mid; else hi = mid;
  }
  const seg = cum[hi] - cum[lo] || 1;
  const f = Math.max(0, Math.min(1, (d - cum[lo]) / seg));
  return [c[lo][0] + (c[hi][0] - c[lo][0]) * f, c[lo][1] + (c[hi][1] - c[lo][1]) * f];
}

/** Trapez hız profili: yavaş kalk, sabit seyret, yavaşça yanaş. Dönüş: [mesafe oranı, hız oranı]. */
function trapezoid(u, a) {
  const k = 1 / (1 - a);
  if (u < a) return [(u * u) / (2 * a) * k, (u / a) * k];
  if (u > 1 - a) { const r = 1 - u; return [1 - (r * r) / (2 * a) * k, (r / a) * k]; }
  return [(u - a / 2) * k, k];
}

/** Bir seferin t anındaki durumu; sefer denizde değilse null. */
export const BOARD_S = 180;   // kalkıştan önce iskelede görünme süresi
export const ALIGHT_S = 90;   // varıştan sonra iskelede kalma süresi

export function tripState(line, trip, t) {
  if (t < trip.start - BOARD_S || t > trip.end + ALIGHT_S) return null;
  if (t < trip.start) {               // kalkış öncesi: yolcu alıyor
    const d = line.stopDist[trip.order[0]];
    return { ...stateAt(line, trip, d, 0, 1), docked: trip.order[0], nextIdx: 1, phase: 'board',
      fade: Math.min(1, (t - (trip.start - BOARD_S)) / 30) };
  }
  if (t > trip.end) {                 // varış sonrası
    const k = trip.order.length - 1;
    const d = line.stopDist[trip.order[k]];
    return { ...stateAt(line, trip, d, 0, k), docked: trip.order[k], nextIdx: k, phase: 'alight',
      fade: Math.min(1, (trip.end + ALIGHT_S - t) / 30) };
  }
  for (let i = 0; i < trip.legs.length; i++) {
    const L = trip.legs[i];
    if (t < L.t0) {                       // ara iskelede bekliyor
      const d = line.stopDist[L.from];
      return { ...stateAt(line, trip, d, 0, i), docked: L.from, nextIdx: i, phase: 'dwell', fade: 1 };
    }
    if (t <= L.t1) {
      const dur = L.t1 - L.t0;
      const a = Math.min(0.3, RAMP_S / dur);
      const [s, vRatio] = trapezoid((t - L.t0) / dur, a);
      const d = L.dA + (L.dB - L.dA) * s;
      const speed = (Math.abs(L.dB - L.dA) / dur) * vRatio;
      return { ...stateAt(line, trip, d, speed, i + 1), docked: null, nextIdx: i + 1, phase: 'sail', fade: 1 };
    }
  }
  return null;
}

function stateAt(line, trip, d, speed, nextIdx) {
  const { lngLat, heading } = pointAt(line, d);
  return {
    lngLat,
    heading: trip.dir === 0 ? heading : (heading + 180) % 360,
    speedKn: speed / KNOT,
    distance: d,
    nextStop: line.stops[trip.order[Math.min(nextIdx, trip.order.length - 1)]],
    eta: trip.arrive[Math.min(nextIdx, trip.arrive.length - 1)],
  };
}

export class Timetable {
  /** network: İBB GTFS desenleri (sürüm 2). weekday: 0 = Pazartesi. */
  constructor(network, weekday) {
    this.piers = new Map(network.piers.map((p) => [p.id, p]));
    this.lines = new Map(network.patterns.map((l) => [l.id, prepareLine(l)]));
    this.weekday = weekday;
    const prev = (weekday + 6) % 7;
    this.trips = [];
    for (const l of this.lines.values()) {
      for (const st of l.starts[weekday] ?? []) this.trips.push(makeTrip(l, st, weekday));
      // dünden kalan, gece yarısını geçen seferler
      const lastOff = l.arr[l.arr.length - 1];
      for (const st of l.starts[prev] ?? []) if (st + lastOff + ALIGHT_S >= 86400) this.trips.push(makeTrip(l, st - 86400, prev));
    }
    this.trips.sort((x, y) => x.start - y.start);
    this.byId = new Map(this.trips.map((x) => [x.id, x]));
  }

  /** t anında denizde ya da iskelede olan seferler + durumları. */
  active(t) {
    const out = [];
    for (const tr of this.trips) {
      if (t < tr.start - BOARD_S || t > tr.end + ALIGHT_S) continue;
      const line = this.lines.get(tr.line);
      const st = tripState(line, tr, t);
      if (st) out.push({ trip: tr, line, state: st });
    }
    return out;
  }

  /** İskeleye uğrayacak seferler (t'den sonra, pencere içinde). */
  arrivalsAt(pierId, t, windowSec = 5400) {
    const out = [];
    for (const tr of this.trips) {
      const line = this.lines.get(tr.line);
      const k = tr.order.findIndex((i) => line.stops[i] === pierId);
      if (k < 0) continue;
      const isOrigin = k === 0;
      const isTerminus = k === tr.order.length - 1;
      const time = isOrigin ? tr.depart[0] : tr.arrive[k];
      if (time < t - 30 || time > t + windowSec) continue;
      out.push({
        trip: tr, line, time, isOrigin, isTerminus,
        onWater: t >= tr.start && t <= tr.end,
        from: line.stops[tr.order[0]], to: line.stops[tr.order[tr.order.length - 1]],
      });
    }
    return out.sort((a, b) => a.time - b.time);
  }

  /** Gün içindeki ilk kalkış (gece boş ekran için). */
  firstDepartureAfter(t) {
    let best = Infinity;
    for (const tr of this.trips) if (tr.start > t && tr.start < best) best = tr.start;
    if (best === Infinity) for (const tr of this.trips) best = Math.min(best, tr.start);
    return best;
  }
}
