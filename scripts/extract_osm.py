import osmium, json, sys
from collections import defaultdict
PBF = sys.argv[1]; OUT = sys.argv[2]
S,W,N,E = 40.80, 28.85, 41.26, 29.30

class Rels(osmium.SimpleHandler):
    def __init__(s): super().__init__(); s.rels={}; s.way_ids=set(); s.node_ids=set()
    def relation(s, r):
        t = dict(r.tags)
        if t.get('route')=='ferry' or (t.get('type')=='route_master' and t.get('route_master')=='ferry'):
            mem=[(m.type,m.ref,m.role) for m in r.members]
            s.rels[r.id]={'tags':t,'members':mem}
            for ty,ref,ro in mem:
                if ty=='w': s.way_ids.add(ref)
                elif ty=='n': s.node_ids.add(ref)
h=Rels(); h.apply_file(PBF)
print('ferry relations', len(h.rels), file=sys.stderr)

class Geo(osmium.SimpleHandler):
    def __init__(s): super().__init__(); s.ways={}; s.nodes={}; s.terms=[]; s.ferryways={}
    def node(s,n):
        t=dict(n.tags)
        if n.id in h.node_ids or t.get('amenity')=='ferry_terminal' or (t.get('ferry')=='yes' and t.get('public_transport') in ('stop_position','platform','station')):
            s.nodes[n.id]={'lon':n.location.lon,'lat':n.location.lat,'tags':t}
    def way(s,w):
        t=dict(w.tags)
        try: coords=[(nd.lon,nd.lat) for nd in w.nodes]
        except osmium.InvalidLocationError: return
        if w.id in h.way_ids: s.ways[w.id]={'coords':coords,'tags':t}
        if t.get('route')=='ferry': s.ferryways[w.id]={'coords':coords,'tags':t}
        if t.get('amenity')=='ferry_terminal' or (t.get('ferry')=='yes' and t.get('public_transport') in ('platform','station')):
            lon=sum(c[0] for c in coords)/len(coords); lat=sum(c[1] for c in coords)/len(coords)
            s.terms.append({'osm':f'w{w.id}','lon':lon,'lat':lat,'tags':t})
g=Geo(); g.apply_file(PBF, locations=True)
json.dump({'rels':{str(k):v for k,v in h.rels.items()},'ways':{str(k):v for k,v in g.ways.items()},'nodes':{str(k):v for k,v in g.nodes.items()},'terms':g.terms,'ferryways':{str(k):v for k,v in g.ferryways.items()}}, open(OUT,'w'), ensure_ascii=False)
print('ways',len(g.ways),'nodes',len(g.nodes),'terms(way)',len(g.terms),'ferryways',len(g.ferryways), file=sys.stderr)
