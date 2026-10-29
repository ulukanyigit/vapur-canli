"""Kanonik iskele listesi (OSM koordinatlarından) + hat tanımları + OSM ferry way grafiğinden geometri."""
import json, math, heapq, sys
from shapely.geometry import LineString, Point
from shapely.ops import transform
from pyproj import Transformer
OSM = json.load(open('build/osm_ferry.json'))
fwd = Transformer.from_crs(4326, 5254, always_xy=True).transform  # TUREF/TM30
inv = Transformer.from_crs(5254, 4326, always_xy=True).transform

# id: (ad, lat, lon, osm kaynağı, bölge)
P = {
 'eminonu':('Eminönü',41.01765,28.97470,'w112174276','Tarihi Yarımada'),
 'karakoy':('Karaköy',41.02142,28.97670,'w52089506','Beyoğlu'),
 'kadikoy':('Kadıköy',40.99290,29.02270,'n2349794761','Kadıköy'),
 'moda':('Moda',40.97893,29.02519,'n12965332590','Kadıköy'),
 'kabatas':('Kabataş',41.03310,28.99380,'w1383311663','Beyoğlu'),
 'besiktas':('Beşiktaş',41.04004,29.00550,'w415337536','Beşiktaş'),
 'uskudar':('Üsküdar',41.02762,29.01518,'w415099414','Üsküdar'),
 'kuzguncuk':('Kuzguncuk',41.03691,29.02969,'w401120302','Üsküdar'),
 'beylerbeyi':('Beylerbeyi',41.04496,29.04458,'w401123337','Üsküdar'),
 'ortakoy':('Ortaköy',41.04721,29.02566,'n6919989286','Beşiktaş'),
 'cengelkoy':('Çengelköy',41.05102,29.05145,'w229826483','Üsküdar'),
 'arnavutkoy':('Arnavutköy',41.06678,29.04338,'n513655728','Beşiktaş'),
 'bebek':('Bebek',41.07634,29.04443,'w1370661359','Beşiktaş'),
 'kandilli':('Kandilli',41.07463,29.05816,'n2383689265','Üsküdar'),
 'asiyan':('Aşiyan',41.08114,29.05486,'n10139241929','Sarıyer'),
 'kucuksu':('Küçüksu',41.07962,29.06541,'w984258520','Beykoz'),
 'anadoluhisari':('Anadolu Hisarı',41.08323,29.06664,'w525436004','Beykoz'),
 'kanlica':('Kanlıca',41.10024,29.06533,'w525436005','Beykoz'),
 'emirgan':('Emirgan',41.10304,29.05607,'w692626936','Sarıyer'),
 'istinye':('İstinye',41.11325,29.06117,'n6502486594','Sarıyer'),
 'cubuklu':('Çubuklu',41.10745,29.08043,'w525436006','Beykoz'),
 'pasabahce':('Paşabahçe',41.11665,29.09324,'w525436007','Beykoz'),
 'yenikoy':('Yeniköy',41.12171,29.07119,'n27611418','Sarıyer'),
 'beykoz':('Beykoz',41.13466,29.09036,'w739105702','Beykoz'),
 'sariyer':('Sarıyer',41.16628,29.05759,'n2201648932','Sarıyer'),
 'rumelikavagi':('Rumeli Kavağı',41.18164,29.07520,'n27607896','Sarıyer'),
 'anadolukavagi':('Anadolu Kavağı',41.17343,29.08787,'n1200223872','Beykoz'),
 'kasimpasa':('Kasımpaşa',41.03031,28.96608,'n1667301250','Haliç'),
 'fener':('Fener',41.03097,28.95263,'w240079127','Haliç'),
 'balat':('Balat',41.03485,28.94922,'w1305509987','Haliç'),
 'haskoy':('Hasköy',41.04055,28.94906,'n414979679','Haliç'),
 'ayvansaray':('Ayvansaray',41.04081,28.94485,'n27609492','Haliç'),
 'sutluce':('Sütlüce',41.04667,28.94069,'n3341121788','Haliç'),
 'eyup':('Eyüp',41.04726,28.93780,'w1068175244','Haliç'),
 'bostanci':('Bostancı',40.95188,29.09429,'w404524230','Kadıköy'),
 'maltepe':('Maltepe',40.91822,29.12846,'w264038066','Maltepe'),
 'kinaliada':('Kınalıada',40.91056,29.05557,'w401651883','Adalar'),
 'burgazada':('Burgazada',40.88108,29.07080,'n409178527','Adalar'),
 'heybeliada':('Heybeliada',40.87802,29.10066,'n5470035019','Adalar'),
 'buyukada':('Büyükada',40.87610,29.12778,'n493262183','Adalar'),
}
# Hatlar: id, ad, işletme, durak sırası, örnek sefer aralığı (dk) [yoğun, sakin], ilk-son kalkış, hız (knot)
L = [
 ('sh-kadikoy-karakoy','Kadıköy – Karaköy','Şehir Hatları',['kadikoy','karakoy'],[15,30],'06:30','23:30',11),
 ('sh-kadikoy-eminonu','Kadıköy – Eminönü','Şehir Hatları',['kadikoy','eminonu'],[20,30],'07:00','23:00',11),
 ('sh-kadikoy-besiktas','Kadıköy – Beşiktaş','Şehir Hatları',['kadikoy','besiktas'],[20,40],'07:00','23:00',11),
 ('sh-kadikoy-kabatas','Kadıköy – Kabataş','Şehir Hatları',['kadikoy','kabatas'],[30,60],'07:15','21:15',11),
 ('sh-uskudar-eminonu','Üsküdar – Karaköy – Eminönü','Şehir Hatları',['uskudar','karakoy','eminonu'],[15,25],'06:45','23:00',10),
 ('sh-bogaz','Boğaz Hattı (Eminönü – Anadolu Kavağı)','Şehir Hatları',['eminonu','besiktas','uskudar','kuzguncuk','beylerbeyi','cengelkoy','arnavutkoy','kandilli','bebek','kucuksu','anadoluhisari','kanlica','emirgan','istinye','yenikoy','pasabahce','beykoz','sariyer','rumelikavagi','anadolukavagi'],[60,120],'07:00','19:00',12),
 ('sh-halic','Haliç Hattı (Üsküdar – Eyüp)','Şehir Hatları',['uskudar','karakoy','kasimpasa','fener','balat','haskoy','ayvansaray','sutluce','eyup'],[45,60],'07:15','21:00',10),
 ('sh-adalar','Kabataş – Kadıköy – Adalar','Şehir Hatları',['kabatas','kadikoy','kinaliada','burgazada','heybeliada','buyukada'],[60,90],'07:00','22:00',13),
 ('sh-bostanci-adalar','Bostancı – Adalar','Şehir Hatları',['bostanci','kinaliada','burgazada','heybeliada','buyukada'],[45,90],'07:30','21:30',12),
 ('sh-bostanci-moda-kabatas','Bostancı – Moda – Karaköy – Kabataş','Şehir Hatları',['bostanci','moda','karakoy','kabatas'],[60,90],'07:30','20:30',12),
 ('sh-ortakoy-eminonu','Ortaköy – Beşiktaş – Eminönü','Şehir Hatları',['ortakoy','besiktas','eminonu'],[60,90],'08:00','20:00',11),
 ('sh-asiyan-uskudar','Aşiyan – Üsküdar','Şehir Hatları',['asiyan','uskudar'],[60,90],'07:30','20:00',11),
 ('sh-asiyan-ring','Aşiyan – Anadolu Hisarı – Küçüksu','Şehir Hatları',['asiyan','anadoluhisari','kucuksu'],[30,60],'07:30','20:00',8),
 ('sh-maltepe-buyukada','Maltepe – Büyükada','Şehir Hatları',['maltepe','buyukada'],[90,120],'08:00','20:00',12),
 ('sh-istinye-cubuklu','İstinye – Çubuklu','Şehir Hatları',['istinye','cubuklu'],[20,30],'06:30','23:00',8),
 ('sh-sariyer-rkavagi','Sarıyer – Rumeli Kavağı – Anadolu Kavağı','Şehir Hatları',['sariyer','rumelikavagi','anadolukavagi'],[60,90],'07:00','20:00',10),
 ('ty-kadikoy-karakoy','Kadıköy – Karaköy','Turyol',['kadikoy','karakoy'],[15,20],'07:00','22:30',10),
 ('ty-kadikoy-eminonu','Kadıköy – Eminönü','Turyol',['kadikoy','eminonu'],[20,30],'07:00','22:00',10),
 ('ty-uskudar-eminonu','Üsküdar – Eminönü','Turyol',['uskudar','eminonu'],[15,20],'07:00','23:00',10),
 ('ty-beykoz-sariyer','Beykoz – Sarıyer','Turyol',['beykoz','sariyer'],[60,90],'07:30','20:00',10),
 ('dt-uskudar-besiktas','Üsküdar – Beşiktaş','Dentur Avrasya',['uskudar','besiktas'],[15,20],'07:00','23:00',9),
 ('dt-uskudar-kabatas','Üsküdar – Kabataş','Dentur Avrasya',['uskudar','kabatas'],[20,30],'07:00','22:00',9),
 ('dt-kadikoy-kabatas','Kadıköy – Kabataş','Dentur Avrasya',['kadikoy','kabatas'],[30,45],'07:30','21:00',9),
]

BERTHS = {}
# --- OSM ferry way grafiği (TM30 metre) ---
ways = {**OSM['ferryways'], **OSM['ways']}
nodes=[]; idx={}
def nid(x,y):
    k=(round(x/40),round(y/40))  # 40 m ızgara ile birleştir
    if k not in idx: idx[k]=len(nodes); nodes.append((x,y))
    return idx[k]
adj={}
def add(a,b):
    if a==b: return
    d=math.dist(nodes[a],nodes[b]); adj.setdefault(a,[]).append((b,d)); adj.setdefault(b,[]).append((a,d))
for w in ways.values():
    op=(w['tags'].get('operator') or '')
    if any(x in op for x in ('BUDO','Marmara Ro-Ro','TCDD')): continue
    nm=w['tags'].get('name') or ''
    if 'Tur' in nm and 'Turyol' not in nm: continue  # turları atla
    pts=[fwd(*c) for c in w['coords']]
    # uzun kenarları ara noktalarla böl (bağlantı olasılığı)
    ids=[]
    for i,p in enumerate(pts):
        if i>0:
            q=pts[i-1]; seg=math.dist(p,q); n=int(seg//150)
            for k in range(1,n+1):
                f=k/(n+1); ids.append(nid(q[0]+(p[0]-q[0])*f,q[1]+(p[1]-q[1])*f))
        ids.append(nid(*p))
    for a,b in zip(ids,ids[1:]): add(a,b)
# yakın düğümleri birbirine bağla (≤120 m)
import itertools
grid={}
for i,(x,y) in enumerate(nodes): grid.setdefault((int(x//120),int(y//120)),[]).append(i)
for (gx,gy),lst in grid.items():
    for dx in (-1,0,1):
        for dy in (-1,0,1):
            for j in grid.get((gx+dx,gy+dy),[]):
                for i in lst:
                    if i<j and math.dist(nodes[i],nodes[j])<=120: add(i,j)
print('graph nodes',len(nodes), file=sys.stderr)

def near(p, r=450):
    out=[(math.dist(p,n),i) for i,n in enumerate(nodes) if abs(n[0]-p[0])<r and abs(n[1]-p[1])<r]
    return sorted(x for x in out if x[0]<=r)[:6]
WAYS_M=[[fwd(*c) for c in w['coords']] for w in ways.values()]
def direct(a,b,r=550):
    pa=fwd(P[a][2],P[a][1]); pb=fwd(P[b][2],P[b][1]); best=None
    for pts in WAYS_M:
        for seq in (pts, pts[::-1]):
            if math.dist(seq[0],pa)<=r and math.dist(seq[-1],pb)<=r:
                ia=min(range(len(seq)),key=lambda i:math.dist(seq[i],pa)); ib=min(range(len(seq)),key=lambda i:math.dist(seq[i],pb))
                if ib<=ia: continue
                seq=seq[ia:ib+1]
                if len(seq)>1 and math.dist(seq[0],pa)<60: seq=seq[1:]
                if len(seq)>1 and math.dist(seq[-1],pb)<60: seq=seq[:-1]
                L_=LineString([pa]+seq+[pb]).length
                if best is None or L_<best[0]: best=(L_,[pa]+seq+[pb])
    return best[1] if best else None
def path(a,b):
    d=direct(a,b)
    if d: return d
    pa=fwd(P[a][2],P[a][1]); pb=fwd(P[b][2],P[b][1])
    starts=near(pa); goals={i:d for d,i in near(pb)}
    if not starts or not goals: return None
    dist={}; prev={}; pq=[]
    for d,i in starts: dist[i]=d; heapq.heappush(pq,(d,i)); prev[i]=None
    straight=math.dist(pa,pb)
    while pq:
        d,u=heapq.heappop(pq)
        if d>dist.get(u,1e18): continue
        if u in goals:
            seq=[]; x=u
            while x is not None: seq.append(nodes[x]); x=prev[x]
            seq=[pa]+seq[::-1]+[pb]
            L_=LineString(seq)
            if L_.length>straight*1.9+600: return None  # saçma dolambaç
            return seq
        if d>straight*2.5+2000: break
        for v,w in adj.get(u,[]):
            nd=d+w
            if nd<dist.get(v,1e18): dist[v]=nd; prev[v]=u; heapq.heappush(pq,(nd,v))
    return None

def curve(a,b):
    """Grafik yoksa: kıyıdan uzaklaşan hafif yay (Bezier)."""
    pa=fwd(P[a][2],P[a][1]); pb=fwd(P[b][2],P[b][1])
    mx,my=(pa[0]+pb[0])/2,(pa[1]+pb[1])/2; dx,dy=pb[0]-pa[0],pb[1]-pa[1]; L_=math.hypot(dx,dy)
    off=0.08*L_; cx,cy=mx-dy/L_*off, my+dx/L_*off
    return [((1-t)**2*pa[0]+2*(1-t)*t*cx+t*t*pb[0], (1-t)**2*pa[1]+2*(1-t)*t*cy+t*t*pb[1]) for t in [i/24 for i in range(25)]]

def smooth(seq):
    ls=LineString(seq).simplify(25)
    # Chaikin
    pts=list(ls.coords)
    for _ in range(2):
        if len(pts)<3: break
        out=[pts[0]]
        for p,q in zip(pts,pts[1:]):
            out+= [(0.75*p[0]+0.25*q[0],0.75*p[1]+0.25*q[1]),(0.25*p[0]+0.75*q[0],0.25*p[1]+0.75*q[1])]
        out.append(pts[-1]); pts=out
    return pts

# --- İBB "Şehir Hatları İskeleleri" KML: varsa resmi koordinatlar OSM'nin yerine geçer ---
import os, re
KML = os.environ.get('IBB_KML', 'data_raw/sehir-hatlari-iskeleleri.kml')
IBB = {  # bizim kimlik -> KML'deki iskele adı(ları); ilk ad haritadaki temsilci nokta
 'eminonu':['EMİNÖNÜ-2','EMİNÖNÜ-1','EMİNÖNÜ-3','EMİNÖNÜ-4'], 'karakoy':['KARAKÖY','KARAKÖY-2'], 'kadikoy':['KADIKÖY-2','KADIKÖY-1'],
 'moda':['MODA'], 'kabatas':['KABATAŞ'], 'besiktas':['BEŞİKTAŞ-2','BEŞİKTAŞ-1'], 'uskudar':['ÜSKÜDAR'], 'kuzguncuk':['KUZGUNCUK'],
 'beylerbeyi':['BEYLERBEYİ'], 'ortakoy':['ORTAKÖY'], 'cengelkoy':['ÇENGELKÖY'], 'arnavutkoy':['ARNAVUTKÖY'], 'bebek':['BEBEK'],
 'kandilli':['KANDİLLİ'], 'asiyan':['AŞİYAN'], 'kucuksu':['KÜÇÜKSU'], 'anadoluhisari':['ANADOLU HİSARI'], 'kanlica':['KANLICA'],
 'emirgan':['EMİRGAN'], 'istinye':['İSTİNYE'], 'cubuklu':['ÇUBUKLU'], 'pasabahce':['PAŞABAHÇE'], 'yenikoy':['YENİKÖY'],
 'beykoz':['BEYKOZ'], 'sariyer':['SARIYER'], 'rumelikavagi':['RUMELİ KAVAĞI'], 'anadolukavagi':['ANADOLU KAVAĞI'],
 'kasimpasa':['KASIMPAŞA'], 'fener':['FENER'], 'balat':['BALAT'], 'haskoy':['HASKÖY'], 'ayvansaray':['AYVANSARAY'],
 'sutluce':['SÜTLÜCE'], 'eyup':['EYÜP SULTAN'], 'bostanci':['BOSTANCI'], 'maltepe':['MALTEPE'], 'kinaliada':['KINALIADA'],
 'burgazada':['BURGAZADA'], 'heybeliada':['HEYBELİADA'], 'buyukada':['BÜYÜKADA'],
}
kml_pts = {}
if os.path.exists(KML):
    txt = open(KML, encoding='utf-8').read()
    for pm in re.findall(r'<Placemark>(.*?)</Placemark>', txt, re.S):
        n = re.search(r'<name>(.*?)</name>', pm, re.S); c = re.search(r'<coordinates>\s*([-\d.]+),([-\d.]+)', pm)
        if n and c: kml_pts[n.group(1).strip()] = (float(c.group(2)), float(c.group(1)))
    print('İBB KML iskele sayısı', len(kml_pts), file=sys.stderr)
for k, names in IBB.items():
    hits = [(nm, kml_pts[nm]) for nm in names if nm in kml_pts]
    if not hits: continue
    lat, lon = hits[0][1]
    name, _, _, osm, area = P[k]
    shift = math.dist(fwd(P[k][2], P[k][1]), fwd(lon, lat))
    if shift > 300: print(f'  uyarı: {k} OSM ile İBB arası {shift:.0f} m', file=sys.stderr)
    P[k] = (name, lat, lon, 'İBB:' + hits[0][0], area)
    BERTHS[k] = [{'name': nm, 'lat': round(la, 6), 'lon': round(lo, 6)} for nm, (la, lo) in hits]

piers=[{'id':k,'name':v[0],'lat':v[1],'lon':v[2],'src':v[3],'area':v[4],'berths':BERTHS.get(k,[]),'lines':[]} for k,v in P.items()]
pidx={p['id']:p for p in piers}
lines=[]; report=[]
for lid,name,op,stops,hw,first,last,kn in L:
    coords=[]; cum=[0.0]; legs=[]
    for a,b in zip(stops,stops[1:]):
        seq=path(a,b); src='osm'
        if seq is None: seq=curve(a,b); src='yay'
        seq=smooth(seq); legs.append(src)
        if coords: seq=seq[1:]
        coords+=seq
        cum.append(LineString(coords).length)
    for s in stops:
        if lid not in pidx[s]['lines']: pidx[s]['lines'].append(lid)
    ll=[tuple(round(v,6) for v in inv(*c)) for c in coords]
    lines.append({'id':lid,'name':name,'operator':op,'stops':stops,'stop_m':[round(c) for c in cum],'length_m':round(cum[-1]),
                  'headway':hw,'first':first,'last':last,'knots':kn,'legs':legs,'coords':ll})
    report.append(f"{lid:22} {round(cum[-1]/1000,1):>5} km  legs={legs}")
json.dump({'piers':piers,'lines':lines},open('docs/data/network.json','w'),ensure_ascii=False,separators=(',',':'))
print('\n'.join(report))
