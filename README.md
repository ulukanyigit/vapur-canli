# Vapur Canlı

**Canlı sürüm:** https://ulukanyigit.github.io/vapur-canli/

İstanbul Boğazı, Haliç, Kadıköy–Karaköy–Eminönü hattı ve Adalar'daki vapurları 3D haritada gösteren, telefondan açılan bağımsız bir web uygulaması. Soru tek: vapurum nerede, iskeleye kaç dakikada gelir?

> Bu proje İBB, Şehir Hatları, Turyol ya da Dentur Avrasya'nın resmi ürünü değildir ve onlarla bağlantısı yoktur. Kurum logoları kullanılmaz. Bir seyir aracı değildir.

## Durum: Aşama A (tarife sürümü)

- Vapurlar şu an **örnek tarifeden** hesaplanıyor. Sefer aralıkları yaklaşık değerlerdir, gerçek saatler değildir. Uygulamada her vapur "Tarifeden tahmin" olarak işaretlenir.
- İBB Açık Veri Portalı'ndaki GTFS tarifesi bağlandığında `data/network.json` içindeki hat ve sefer bilgisi gerçek saatlerle değişecek.
- Canlı AIS (Aşama B) henüz bağlı değil. Bağlandığında vapurlar "Canlı", yayın kesilirse "Sinyal kesildi" olarak görünecek.

## Yolculuk planlama

Panelin üstündeki **Nereden / Nereye** kartından ya da bir iskelenin "Buradan bin / Burada in" düğmelerinden kalkış ve varış iskelesi seçilir. Uygulama günün kalan doğrudan seferlerini kalkış saatine göre listeler (kalkışa kalan süre, varış saati, yolculuk süresi, işletme). Doğrudan sefer yoksa tek aktarmalı seçenekler önerilir (en az 3 dakika aktarma payı, en fazla 1 saat bekleme). Tarifede süresi bariz hatalı seferler (en kısa yolculuğun 2,2 katından uzun olanlar) listelenmez. Seçim adres çubuğunda tutulur, paylaşılabilir: `?nereden=kadikoy&nereye=karakoy`.

## Klasör yapısı

```
docs/                 GitHub Pages'e yayınlanan statik site
  index.html
  css/app.css         görsel kimlik ve arayüz
  js/app.js           harita, vapur çizimi, panel
  js/schedule.js      tarife modeli (saf fonksiyonlar, Node'da test edilebilir)
  js/style.js         altlık harita stili
  data/network.json   iskeleler + hatlar (üretilmiş)
  data/dem/           Copernicus GLO-30'dan terrarium karoları (z8–12)
  fonts/              Sofia Sans (OFL), yerelde sunulur
  vendor/             MapLibre GL JS 5.24.0
scripts/
  extract_osm.py      OSM PBF'ten vapur hatları ve iskeleler
  piers_lines.py      kanonik iskele listesi + hat tanımları + OSM ferry way grafiğinden geometri
  make_terrain.py     GLO-30 mozaik -> terrarium PNG karoları
  shoot.py            Playwright ile görsel test
data_raw/             indirilen ham veri (repoya girmez)
```

## Veriyi yeniden üretmek

```bash
pip install osmium shapely pyproj rasterio mercantile pillow
python scripts/extract_osm.py data_raw/Istanbul.osm.pbf build/osm_ferry.json
python scripts/piers_lines.py          # docs/data/network.json
python scripts/make_terrain.py docs/data/dem
```

Ham veri kaynakları: İBB Şehir Hatları İskeleleri KML'i, BBBike İstanbul OSM özeti (`Istanbul.osm.pbf`) ve AWS Open Data üzerindeki Copernicus DEM karoları (`Copernicus_DSM_COG_10_N40/N41_00_E028/E029_00_DEM`).

## Yerelde çalıştırmak

```bash
cd docs && python -m http.server 8000
# http://localhost:8000/?saat=08:15&hiz=20   (benzetim: 08.15'ten başla, zamanı 20 kat hızlandır)
```

## Hat geometrisi nasıl üretildi

İskele koordinatları İBB'nin "İstanbul Şehir Hatları İskeleleri" KML dosyasından geliyor (`data_raw/sehir-hatlari-iskeleleri.kml`, 55 iskele/rıhtım). Birden fazla rıhtımı olan iskelelerde (Eminönü 1–4, Kadıköy 1–2, Beşiktaş 1–2, Karaköy 1–2) tümü `berths` alanında tutulur, haritada biri temsilci nokta olur. KML yoksa betik OSM'deki `amenity=ferry_terminal` noktalarına döner. Kaynak `network.json` içinde `src` alanında yazar. Hat çizgileri, ardışık iki iskele arasında önce o iki iskeleyi doğrudan bağlayan bir OSM `route=ferry` yolu aranarak, yoksa tüm vapur yollarından kurulan grafikte en kısa yol bulunarak çıkarıldı. Hiçbiri yoksa hafif bir yay çizilir: şu an yalnızca Boğaz Hattı'nın İstinye–Yeniköy–Paşabahçe–Beykoz arasındaki üç bacağı böyle.

## Lisanslar ve atıflar

| Veri / yazılım | Kaynak | Lisans | Atıf |
|---|---|---|---|
| İskele konumları | İBB Açık Veri Portalı, İstanbul Şehir Hatları İskeleleri (KML, veri tarihi 5 Mart 2025) | İBB Açık Veri Lisansı | Kaynak: İBB Açık Veri Portalı |
| Hat çizgileri, binalar | OpenStreetMap | ODbL 1.0 | © OpenStreetMap katkıcıları |
| Altlık vektör karolar | OpenFreeMap / OpenMapTiles | OSM verisi ODbL, şema BSD/CC-BY | OpenFreeMap © OpenMapTiles Data from OpenStreetMap |
| Arazi gölgesi | Copernicus GLO-30 DEM (AWS Open Data) | Copernicus DEM lisansı, atıfla ücretsiz | Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved |
| Harita motoru | MapLibre GL JS 5.24.0 | BSD-3-Clause | `docs/vendor/MAPLIBRE-LICENSE.txt` |
| Yazı tipi | Sofia Sans, Sofia Sans Extra Condensed (Lettersoup) | SIL OFL 1.1 | — |
| Tarife (gelecek) | İBB Açık Veri Portalı, Toplu Ulaşım GTFS Verisi | İBB Açık Veri Lisansı | Lisans metni bağlandığında buraya birebir yazılacak |
| Canlı AIS (gelecek) | aisstream.io | aisstream kullanım koşulları | — |

## Kurallar

- Yalnızca resmi API'ler ve açık veri. MarineTraffic, VesselFinder gibi sitelerden ya da belgelenmemiş iç API'lerden veri kazınmaz.
- API anahtarları repoya girmez. Canlı AIS anahtarı yalnızca aktarıcı servisin ortam değişkeninde durur (`AISSTREAM_API_KEY`).
- Kurum logoları ve kurumsal renk kimlikleri kullanılmaz.
