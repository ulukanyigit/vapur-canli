import rasterio, numpy as np, mercantile, os, glob, sys
from rasterio.merge import merge
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_bounds
from PIL import Image
SRC = sorted(glob.glob('/mnt/user-data/uploads/VAPUR CANLI/data_raw/Copernicus_*.tif'))
OUT = sys.argv[1]
W,S,E,N = 28.80, 40.80, 29.34, 41.27
srcs=[rasterio.open(p) for p in SRC]
mos, tr = merge(srcs, bounds=(W-0.02,S-0.02,E+0.02,N+0.02))
mos = mos[0].astype('float32'); crs = srcs[0].crs
print('mosaic', mos.shape, np.nanmin(mos), np.nanmax(mos))
n=0
for z in range(8,13):
    for t in mercantile.tiles(W,S,E,N,[z]):
        b = mercantile.xy_bounds(t)
        dst = np.zeros((256,256),'float32')
        reproject(mos, dst, src_transform=tr, src_crs=crs, dst_transform=from_bounds(b.left,b.bottom,b.right,b.top,256,256), dst_crs='EPSG:3857', resampling=Resampling.bilinear, src_nodata=-32767, dst_nodata=0)
        dst = np.clip(dst, -50, 1000)
        v = dst + 32768.0
        r = np.floor(v/256); g = np.floor(v - r*256); bch = np.floor((v - np.floor(v))*256)
        img = np.dstack([r,g,bch]).astype('uint8')
        p = f'{OUT}/{z}/{t.x}'; os.makedirs(p, exist_ok=True)
        Image.fromarray(img,'RGB').save(f'{p}/{t.y}.png', optimize=True); n+=1
print('tiles', n)
