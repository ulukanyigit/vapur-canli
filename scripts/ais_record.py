"""aisstream.io kayıt testi: İstanbul Boğazı, Haliç ve Adalar'daki AIS mesajlarını belirli bir süre kaydeder.

kullanım: python ais_record.py <çıktı_klasörü> [saat=24] [bbox_json]

- API anahtarı AISSTREAM_API_KEY ortam değişkeninden (Windows'ta gerekirse kullanıcı kaydından) okunur,
  hiçbir dosyaya ya da loga yazılmaz.
- Çıktı: saatlik positions-YYYYMMDD-HH.jsonl.gz dosyaları + her dakika güncellenen status.json ve vessels.json.
- Durdurmak için çıktı klasörüne STOP adında boş bir dosya koymak yeterli.
"""
import asyncio, gzip, json, os, random, sys, time, datetime

import websockets

URL = 'wss://stream.aisstream.io/v0/stream'
BBOX = [[[40.84, 28.85], [41.25, 29.20]]]           # Adalar'dan Rumeli Feneri'ne, Haliç dahil
TYPES = ['PositionReport', 'StandardClassBPositionReport', 'ExtendedClassBPositionReport', 'ShipStaticData', 'StaticDataReport']
SHORT = {'PositionReport': 'A', 'StandardClassBPositionReport': 'B', 'ExtendedClassBPositionReport': 'BX', 'ShipStaticData': 'S', 'StaticDataReport': 'SB'}

OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else 'ais_kayit')
HOURS = float(sys.argv[2]) if len(sys.argv) > 2 else 24.0
if len(sys.argv) > 3:                                 # test için başka bir kutu: '[[[lat,lon],[lat,lon]]]'
    BBOX = json.loads(sys.argv[3])
os.makedirs(OUT, exist_ok=True)


def api_key():
    k = os.environ.get('AISSTREAM_API_KEY')
    if not k and os.name == 'nt':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as h:
                k = winreg.QueryValueEx(h, 'AISSTREAM_API_KEY')[0]
        except OSError:
            k = None
    if not k:
        raise SystemExit('AISSTREAM_API_KEY bulunamadı')
    return k.strip()


def log(msg):
    with open(os.path.join(OUT, 'record.log'), 'a', encoding='utf-8') as f:
        f.write(f'{datetime.datetime.now().isoformat(timespec="seconds")} {msg}\n')


class Recorder:
    def __init__(self):
        self.t0 = time.time()
        self.deadline = self.t0 + HOURS * 3600
        self.counts = {}
        self.total = 0
        self.vessels = {}        # mmsi -> özet
        self.reconnects = 0
        self.last_error = None
        self.last_msg = None
        self.connected_since = None
        self._fh = None
        self._fh_hour = None

    def file(self):
        hour = datetime.datetime.utcnow().strftime('%Y%m%d-%H')
        if hour != self._fh_hour:
            if self._fh: self._fh.close()
            self._fh = gzip.open(os.path.join(OUT, f'positions-{hour}.jsonl.gz'), 'at', encoding='utf-8')
            self._fh_hour = hour
        return self._fh

    def handle(self, raw):
        now = time.time()
        msg = json.loads(raw)
        mt = msg.get('MessageType')
        if mt == 'SubscriptionConfirmation':
            log(f'abonelik onaylandı, sıkıştırma={msg.get("Message", {}).get("CompressionEnabled")}')
            return
        body = msg.get('Message', {}).get(mt, {})
        meta = msg.get('MetaData', {})
        mmsi = meta.get('MMSI') or body.get('UserID')
        rec = {'t': round(now, 1), 'mt': SHORT.get(mt, mt), 'm': mmsi, 'n': (meta.get('ShipName') or '').strip()}
        if mt in ('PositionReport', 'StandardClassBPositionReport', 'ExtendedClassBPositionReport'):
            rec.update(la=body.get('Latitude', meta.get('latitude')), lo=body.get('Longitude', meta.get('longitude')),
                       sog=body.get('Sog'), cog=body.get('Cog'), hdg=body.get('TrueHeading'), ns=body.get('NavigationalStatus'),
                       ts=body.get('Timestamp'))
        elif mt == 'ShipStaticData':
            dim = body.get('Dimension') or {}
            rec.update(st=body.get('Type'), cs=(body.get('CallSign') or '').strip(), imo=body.get('ImoNumber'),
                       dest=(body.get('Destination') or '').strip(), dim=[dim.get('A'), dim.get('B'), dim.get('C'), dim.get('D')])
        elif mt == 'StaticDataReport':
            rb = body.get('ReportB') or {}
            ra = body.get('ReportA') or {}
            if ra.get('Valid'): rec['n'] = (ra.get('Name') or rec['n']).strip()
            if rb.get('Valid'): rec.update(st=rb.get('ShipType'), cs=(rb.get('CallSign') or '').strip())
        self.file().write(json.dumps(rec, ensure_ascii=False, separators=(',', ':')) + '\n')

        self.total += 1
        self.counts[rec['mt']] = self.counts.get(rec['mt'], 0) + 1
        self.last_msg = now
        v = self.vessels.setdefault(str(mmsi), {'name': '', 'type': None, 'pos': 0, 'first': now, 'last': now})
        if rec['n']: v['name'] = rec['n']
        if rec.get('st') is not None: v['type'] = rec['st']
        if 'la' in rec: v['pos'] += 1
        v['last'] = now

    def write_status(self, final=False):
        now = time.time()
        passenger = {m: v for m, v in self.vessels.items() if isinstance(v['type'], int) and 60 <= v['type'] <= 69}
        status = {
            'started': datetime.datetime.fromtimestamp(self.t0).isoformat(timespec='seconds'),
            'updated': datetime.datetime.fromtimestamp(now).isoformat(timespec='seconds'),
            'ends': datetime.datetime.fromtimestamp(self.deadline).isoformat(timespec='seconds'),
            'running_min': round((now - self.t0) / 60, 1),
            'finished': final,
            'messages': self.total, 'by_type': self.counts,
            'msg_per_min': round(self.total / max(1, (now - self.t0) / 60), 1),
            'vessels': len(self.vessels), 'passenger_type_vessels': len(passenger),
            'reconnects': self.reconnects, 'last_error': self.last_error,
            'seconds_since_last_msg': round(now - self.last_msg, 1) if self.last_msg else None,
            'connected': self.connected_since is not None,
        }
        tmp = os.path.join(OUT, 'status.json.tmp')
        json.dump(status, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        os.replace(tmp, os.path.join(OUT, 'status.json'))
        tmp = os.path.join(OUT, 'vessels.json.tmp')
        json.dump(self.vessels, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False)
        os.replace(tmp, os.path.join(OUT, 'vessels.json'))
        if self._fh: self._fh.flush()

    def should_stop(self):
        return time.time() >= self.deadline or os.path.exists(os.path.join(OUT, 'STOP'))

    async def status_loop(self):
        while not self.should_stop():
            self.write_status()
            await asyncio.sleep(60)

    async def stream(self):
        key = api_key()
        sub = json.dumps({'APIKey': key, 'BoundingBoxes': BBOX, 'FilterMessageTypes': TYPES})
        backoff = 2
        while not self.should_stop():
            try:
                async with websockets.connect(URL, compression='deflate', open_timeout=20, ping_interval=20, ping_timeout=30, max_size=2 ** 22) as ws:
                    await ws.send(sub)                          # 3 saniye içinde abonelik
                    self.connected_since = time.time()
                    log('bağlandı')
                    backoff = 2
                    while not self.should_stop():
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=120)
                        except asyncio.TimeoutError:
                            log('120 sn mesaj yok, yeniden bağlanılıyor'); break
                        try:
                            self.handle(raw if isinstance(raw, str) else raw.decode('utf-8'))
                        except Exception as e:              # tek bozuk mesaj kaydı durdurmasın
                            self.last_error = f'parse: {type(e).__name__}: {e}'[:300]
            except Exception as e:
                msg = str(e).replace(key, '***')
                self.last_error = f'{type(e).__name__}: {msg}'[:300]
                log(f'bağlantı hatası: {self.last_error}')
            self.connected_since = None
            if self.should_stop(): break
            self.reconnects += 1
            wait = min(300, backoff) + random.uniform(0, 2)
            backoff *= 2
            await asyncio.sleep(wait)

    async def run(self):
        log(f'başladı, süre {HOURS} saat, çıktı {OUT}')
        await asyncio.gather(self.stream(), self.status_loop())
        self.write_status(final=True)
        if self._fh: self._fh.close()
        log('bitti')


def single_instance():
    pidf = os.path.join(OUT, 'record.pid')
    if os.path.exists(pidf):
        try:
            pid = int(open(pidf).read().strip())
            if os.name == 'nt':
                import ctypes
                h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
                code = ctypes.c_ulong()
                alive = bool(h) and ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code)) and code.value == 259
            else:
                os.kill(pid, 0); alive = True
            if alive: raise SystemExit(f'kayıt zaten çalışıyor (pid {pid})')
        except (ValueError, OSError):
            pass
    open(pidf, 'w').write(str(os.getpid()))


if __name__ == '__main__':
    single_instance()
    try:
        asyncio.run(Recorder().run())
    except SystemExit:
        raise
    except Exception as e:
        log(f'beklenmeyen hata: {type(e).__name__}: {e}')
        raise
