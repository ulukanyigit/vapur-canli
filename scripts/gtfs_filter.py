"""Ham İBB GTFS klasöründen (cp1254) vapur alt kümesini UTF-8 olarak çıkarır.
kullanım: python scripts/gtfs_filter.py "ibb veri" data_raw/gtfs_vapur
"""
import csv, io, os, sys
src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
AGENCIES = ('6', '48', '33', '20')     # Şehir Hatları, Turyol, Dentur Avrasya, İDO
rd = lambda f: csv.DictReader(io.open(os.path.join(src, f), encoding='cp1254', newline=''))
def write(name, rows, fields):
    with io.open(os.path.join(out, name), 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
routes = [r for r in rd('routes.csv') if r['route_type'] == '4' and r['agency_id'] in AGENCIES]
rids = {r['route_id'] for r in routes}
trips = [r for r in rd('trips.csv') if r['route_id'] in rids]
tids = {t['trip_id'] for t in trips}; shp = {t['shape_id'] for t in trips}
st = [r for r in rd('stop_times.csv') if r['trip_id'] in tids]
sids = {r['stop_id'] for r in st}
stops = [r for r in rd('stops.csv') if r['stop_id'] in sids]
sh = [r for r in rd('shapes.csv') if r['shape_id'] in shp]
fr = [r for r in rd('frequencies.csv') if r['trip_id'] in tids]
for name, rows in [('routes.csv', routes), ('trips.csv', trips), ('stop_times.csv', st), ('stops.csv', stops), ('shapes.csv', sh), ('frequencies.csv', fr)]:
    write(name, rows, list(rows[0].keys()) if rows else ['id'])
for f in ('agency.csv', 'calendar.csv'):
    rows = list(rd(f)); write(f, rows, list(rows[0].keys()))
print('hat', len(routes), 'sefer', len(trips), 'durak', len(stops))
