"""İBB GTFS (vapur alt kümesi) -> docs/data/network.json (sürüm 2).

Girdi : data_raw/gtfs_vapur/*.csv  (ham İBB GTFS'ten route_type=4 olanlar, UTF-8)
        data_raw/sehir-hatlari-iskeleleri.kml (İBB iskele koordinatları, iskele adları için)
Çıktı : docs/data/network.json

Yapı:
  piers    : iskeleler (GTFS durakları ~300 m içinde tek iskelede toplanır)
  patterns : aynı hat + aynı durak dizisi + aynı süreler = bir desen; geometri GTFS shape'inden
  trips    : desen başına, haftanın günlerine göre kalkış saatleri (saniye)
"""
import csv, json, math, re, sys, collections, os
from pyproj import Transformer
from shapely.geometry import LineString, Point

G = 'data_raw/gtfs_vapur/'
OUT = sys.argv[1] if len(sys.argv) > 1 else 'docs/data/network.json'
fwd = Transformer.from_crs(4326, 5254, always_xy=True).transform
inv = Transformer.from_crs(5254, 4326, always_xy=True).transform
BOUNDS = (28.62, 40.70, 29.52, 41.36)            # haritanın sınırları
DATA_DATE_MIN = 20230201                          # bu tarihten önce biten takvimleri at

rd = lambda f: list(csv.DictReader(open(G + f, encoding='utf-8')))
agency = {a['agency_id']: a for a in rd('agency.csv')}
routes = {r['route_id']: r for r in rd('routes.csv')}
trips = {t['trip_id']: t for t in rd('trips.csv')}
stops = {s['stop_id']: s for s in rd('stops.csv')}
cal = {c['service_id']: c for c in rd('calendar.csv')}
freqs = collections.defaultdict(list)
for f in rd('frequencies.csv'): freqs[f['trip_id']].append(f)
st = collections.defaultdict(list)
for r in rd('stop_times.csv'): st[r['trip_id']].append(r)
shp = collections.defaultdict(list)
for r in rd('shapes.csv'): shp[r['shape_id']].append(r)

OPERATOR = {'6': 'Şehir Hatları', '48': 'Turyol', '33': 'Dentur Avrasya', '20': 'İDO'}
SKIP_ROUTES = {'LALE FST', 'ERGVN'}               # festival/tur seferleri

def sec(s):
    h, m, x = (int(v) for v in s.split(':'))
    return h * 3600 + m * 60 + x

def tr_title(s):
    """Türkçe büyük/küçük harf kurallarıyla başlık biçimi."""
    low = s.replace('I', 'ı').replace('İ', 'i').lower()
    out = []
    for w in re.split(r'(\s+|-|\(|\)|/)', low):
        if not w or not w.strip() or w in '-()/': out.append(w); continue
        first = w[0]
        first = 'İ' if first == 'i' else 'I' if first == 'ı' else first.upper()
        out.append(first + w[1:])
    return ''.join(out)

# ---------------------------------------------------------------- iskeleler
IBB_KML = 'data_raw/sehir-hatlari-iskeleleri.kml'
kml = {}
if os.path.exists(IBB_KML):
    txt = open(IBB_KML, encoding='utf-8').read()
    for pm in re.findall(r'<Placemark>(.*?)</Placemark>', txt, re.S):
        n = re.search(r'<name>(.*?)</name>', pm, re.S); c = re.search(r'<coordinates>\s*([-\d.]+),([-\d.]+)', pm)
        if n and c: kml[n.group(1).strip()] = (float(c.group(1)), float(c.group(2)))

AREA = json.load(open('build/pier_areas.json', encoding='utf-8')) if os.path.exists('build/pier_areas.json') else {}
AREA.update({'bakirkoy': 'Bakırköy', 'harem': 'Üsküdar', 'sirkeci': 'Tarihi Yarımada', 'yenikapi': 'Tarihi Yarımada', 'avcilar': 'Avcılar'})

def clean_name(n):
    n = re.sub(r'\s*\((Arabalı Vapur)\)', '', n)
    n = re.sub(r'\s*(ŞH\.?|İDO|Turyol|Dentur|Feribot)\s*$', '', n).strip()
    n = re.sub(r'(-Kadıköy|-Üsküdar|-Boğaz|-Beşiktaş-Adalar|-Beşiktaş)$', '', n).strip()
    n = n.replace('Kadıköy2(Çayırbaşı)', 'Kadıköy').replace('Yeni Kadıköy', 'Kadıköy').replace('Eminönü Camlı İskele', 'Eminönü')
    return re.sub(r'\s+', ' ', n).strip()

used_stops = {r['stop_id'] for v in st.values() for r in v}
groups = []   # [{name, pts:[(x,y)], stop_ids}]
for sid in sorted(used_stops, key=lambda s: stops[s]['stop_name']):
    s = stops[sid]; lon, lat = float(s['stop_lon']), float(s['stop_lat'])
    if not (BOUNDS[0] <= lon <= BOUNDS[2] and BOUNDS[1] <= lat <= BOUNDS[3]): continue
    x, y = fwd(lon, lat); nm = clean_name(s['stop_name'])
    best = None
    for g in groups:
        gx = sum(p[0] for p in g['pts']) / len(g['pts']); gy = sum(p[1] for p in g['pts']) / len(g['pts'])
        d = math.hypot(gx - x, gy - y)
        if (d < 700 and g['name'] == nm) or d < 120 and (best is None or d < best[0]): best = (d, g)
    if best: best[1]['pts'].append((x, y)); best[1]['stop_ids'].append(sid)
    else: groups.append({'name': nm, 'pts': [(x, y)], 'stop_ids': [sid]})

def slug(n):
    t = n.lower().translate(str.maketrans('çğıöşüâî', 'cgiosuai')).replace('i̇', 'i')
    return re.sub(r'[^a-z0-9]+', '', t)

stop2pier = {}; piers = []
for g in groups:
    pid = slug(g['name'])
    while any(p['id'] == pid for p in piers): pid += 'x'
    # temsilci nokta: şehir hatları durağı varsa o, yoksa ilk durak
    sids = sorted(g['stop_ids'], key=lambda s: (0 if stops[s]['stop_name'].endswith(('ŞH.', 'ŞH')) else 1, s))
    s0 = stops[sids[0]]
    berths = [{'stop_id': s, 'name': stops[s]['stop_name'], 'lat': round(float(stops[s]['stop_lat']), 6), 'lon': round(float(stops[s]['stop_lon']), 6)} for s in g['stop_ids']]
    piers.append({'id': pid, 'name': g['name'], 'area': AREA.get(pid, ''), 'lat': round(float(s0['stop_lat']), 6), 'lon': round(float(s0['stop_lon']), 6),
                  'src': 'İBB GTFS', 'berths': berths, 'lines': []})
    for s in g['stop_ids']: stop2pier[s] = pid

# ---------------------------------------------------------------- shape'ler
def shape_line(shape_id):
    pts = sorted(shp[shape_id], key=lambda r: int(r['shape_pt_sequence']))
    xy = [fwd(float(p['shape_pt_lon']), float(p['shape_pt_lat'])) for p in pts]
    clean = [xy[0]]
    for p in xy[1:]:
        if math.dist(p, clean[-1]) > 0.5: clean.append(p)
    return LineString(clean) if len(clean) > 1 else None

shape_cache = {}
def get_shape(sid):
    if sid not in shape_cache: shape_cache[sid] = shape_line(sid) if sid in shp else None
    return shape_cache[sid]

# ---------------------------------------------------------------- desenler
patterns = {}      # key -> pattern
dropped = collections.Counter()
WEEK = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

def service_days(sid):
    c = cal.get(sid)
    if not c or int(c['end_date']) < DATA_DATE_MIN: return []
    return [i for i, d in enumerate(WEEK) if c[d] == '1']

for tid, t in trips.items():
    r = routes[t['route_id']]
    if r['route_short_name'] in SKIP_ROUTES: dropped['festival'] += 1; continue
    rows = sorted(st.get(tid, []), key=lambda x: int(x['stop_sequence']))
    if len(rows) < 2: dropped['no_stop_times'] += 1; continue
    if any(x['stop_id'] not in stop2pier for x in rows): dropped['out_of_bounds'] += 1; continue
    days = service_days(t['service_id'])
    if not days: dropped['old_calendar'] += 1; continue
    t0 = sec(rows[0]['arrival_time'])
    arr = [sec(x['arrival_time']) - t0 for x in rows]
    dep = [sec(x['departure_time']) - t0 for x in rows]
    pier_seq = [stop2pier[x['stop_id']] for x in rows]
    # aynı iskeleye arka arkaya iki durak (ör. aynı iskelenin iki rıhtımı) -> birleştir
    keep = [0] + [i for i in range(1, len(rows)) if pier_seq[i] != pier_seq[i - 1]]
    if len(keep) < 2: dropped['single_pier'] += 1; continue
    pier_seq = [pier_seq[i] for i in keep]; arr = [arr[i] for i in keep]; dep = [dep[i] for i in keep]
    key = (t['route_id'], t['shape_id'], tuple(pier_seq), tuple(arr), tuple(dep))
    p = patterns.get(key)
    if not p:
        p = patterns[key] = {'route': t['route_id'], 'shape': t['shape_id'], 'stops': pier_seq, 'stop_ids': [rows[i]['stop_id'] for i in keep],
                             'arr': arr, 'dep': dep, 'starts': collections.defaultdict(set), 'headsign': t['trip_headsign']}
    if tid in freqs:
        for f in freqs[tid]:
            s, e, h = sec(f['start_time']), sec(f['end_time']), int(f['headway_secs'])
            x = s
            while x < e:
                for d in days: p['starts'][d].add(x)
                x += h
    else:
        for d in days: p['starts'][d].add(t0)

print('desen', len(patterns), 'atılan', dict(dropped), file=sys.stderr)

# ---------------------------------------------------------------- geometri + çıktı
out_patterns = []; shapes_out = {}; problems = []
for i, (key, p) in enumerate(sorted(patterns.items(), key=lambda kv: (kv[1]['route'], kv[1]['stops']))):
    pier_xy = [fwd(next(q for q in piers if q['id'] == s)['lon'], next(q for q in piers if q['id'] == s)['lat']) for s in p['stops']]
    stop_xy = [fwd(float(stops[s]['stop_lon']), float(stops[s]['stop_lat'])) for s in p['stop_ids']]
    ln = get_shape(p['shape'])
    ok = False
    if ln is not None:
        # durakları shape üzerine sırayla izdüşür; sıra bozuksa ya da shape duraklara çok uzaksa kullanma
        d = [ln.project(Point(xy)) for xy in stop_xy]
        off = [Point(xy).distance(ln) for xy in stop_xy]
        ok = all(b >= a - 1 for a, b in zip(d, d[1:])) and max(off) < 600
        if ok:
            coords = list(ln.coords)
            seg = LineString(coords)
            # shape'i ilk ve son durak arasında kes
            from shapely.ops import substring
            seg = substring(ln, d[0], d[-1])
            if seg.length < 50: ok = False
            else:
                geom = [stop_xy[0]] + list(seg.simplify(4).coords) + [stop_xy[-1]]
                dist = [x - d[0] for x in d]
    if not ok:
        # yedek: duraklar arasında düz/yay
        problems.append((routes[p['route']]['route_short_name'], p['shape']))
        geom = []; dist = [0.0]
        for a, b in zip(stop_xy, stop_xy[1:]):
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2; dx, dy = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dy) or 1
            cx, cy = mx - dy / L * 0.06 * L, my + dx / L * 0.06 * L
            seg = [((1 - t) ** 2 * a[0] + 2 * (1 - t) * t * cx + t * t * b[0], (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * cy + t * t * b[1]) for t in [k / 16 for k in range(17)]]
            geom += seg if not geom else seg[1:]
            dist.append(LineString(geom).length)
    L = LineString(geom).length
    r = routes[p['route']]
    days = {str(dd): sorted(v) for dd, v in p['starts'].items() if v}
    if not days: continue
    pid = f"p{i}"
    out_patterns.append({
        'id': pid, 'route': p['route'], 'code': r['route_short_name'], 'name': tr_title(r['route_long_name']),
        'operator': OPERATOR.get(r['agency_id'], agency[r['agency_id']]['agency_name']),
        'stops': p['stops'], 'stop_m': [round(x) for x in dist], 'length_m': round(L),
        'arr': p['arr'], 'dep': p['dep'], 'starts': days, 'approx_geom': not ok,
        'coords': [[round(c, 6) for c in inv(*xy)] for xy in geom],
    })
    for s in p['stops']:
        q = next(q for q in piers if q['id'] == s)
        if r['route_short_name'] not in q['lines']: q['lines'].append(r['route_short_name'])

piers = [p for p in piers if p['lines']]
n_trips = sum(len(v) for p in out_patterns for v in p['starts'].values())
meta = {
    'version': 2,
    'source': 'İBB Açık Veri Portalı, Toplu Ulaşım GTFS Verisi (Şehir Hatları verisi 01.02.2023)',
    'calendar_note': 'GTFS takvimi 31.12.2024 tarihinde sona eriyor; sefer saatleri haftanın günü desenine göre uygulanıyor.',
    'built': __import__('datetime').date.today().isoformat(),
}
json.dump({**meta, 'piers': piers, 'patterns': out_patterns}, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(f'iskele {len(piers)}, desen {len(out_patterns)}, haftalık sefer {n_trips}, yaklaşık geometri {len(problems)}', file=sys.stderr)
for pr in sorted(set(problems)): print('  yaklaşık:', pr, file=sys.stderr)
