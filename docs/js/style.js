// Altlık harita stili: OpenFreeMap (OpenMapTiles şeması) + Copernicus GLO-30 gölgelendirme.
// Renkler alacakaranlıkta Boğaz: koyu kıyı, derin yeşil-mavi su, ışığı yanan binalar.

const base = location.href.replace(/[?#].*$/, '').replace(/[^/]*$/, '');

export function buildStyle() {
  const C = {
    land: '#1B292C',
    green: '#20363A',
    water: '#0F3A41',
    waterDeep: '#0C3137',
    shore: '#2C5157',
    road: '#2C4145',
    roadMajor: '#3A5256',
    bridge: '#8EA6A4',
    label: '#A9BEBA',
    labelHalo: '#13252A',
  };
  return {
    version: 8,
    glyphs: 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf',
    sources: {
      omt: {
        type: 'vector', url: 'https://tiles.openfreemap.org/planet',
        attribution: '<a href="https://openfreemap.org" target="_blank">OpenFreeMap</a> <a href="https://www.openmaptiles.org/" target="_blank">© OpenMapTiles</a> Data from <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a>',
      },
      dem: {
        type: 'raster-dem', encoding: 'terrarium', tileSize: 256, minzoom: 8, maxzoom: 12,
        bounds: [28.80, 40.80, 29.34, 41.27],
        tiles: [`${base}data/dem/{z}/{x}/{y}.png`],
        attribution: 'Copernicus GLO-30 DEM © DLR e.V., © Airbus DS',
      },
    },
    sky: {
      'sky-color': '#21414A',
      'horizon-color': '#C98B57',
      'fog-color': '#1A3136',
      'sky-horizon-blend': 0.55,
      'horizon-fog-blend': 0.6,
      'fog-ground-blend': 0.82,
      'atmosphere-blend': ['interpolate', ['linear'], ['zoom'], 9, 1, 14, 0.4],
    },
    light: { anchor: 'map', position: [1.4, 210, 40], color: '#FFE3BD', intensity: 0.42 },
    layers: [
      { id: 'bg', type: 'background', paint: { 'background-color': C.land } },
      {
        id: 'landcover', type: 'fill', source: 'omt', 'source-layer': 'landcover',
        filter: ['in', ['get', 'class'], ['literal', ['wood', 'grass', 'farmland', 'scrub']]],
        paint: { 'fill-color': C.green, 'fill-opacity': 0.7 },
      },
      {
        id: 'park', type: 'fill', source: 'omt', 'source-layer': 'park',
        paint: { 'fill-color': C.green, 'fill-opacity': 0.6 },
      },
      {
        id: 'hillshade', type: 'hillshade', source: 'dem',
        paint: {
          'hillshade-exaggeration': 0.45,
          'hillshade-shadow-color': '#0A1719',
          'hillshade-highlight-color': '#4C6B6B',
          'hillshade-accent-color': '#16272A',
          'hillshade-illumination-direction': 300,
        },
      },
      {
        id: 'water', type: 'fill', source: 'omt', 'source-layer': 'water',
        paint: { 'fill-color': ['interpolate', ['linear'], ['zoom'], 9, C.waterDeep, 14, C.water], 'fill-antialias': true },
      },
      {
        id: 'water-edge', type: 'line', source: 'omt', 'source-layer': 'water',
        paint: { 'line-color': C.shore, 'line-width': ['interpolate', ['linear'], ['zoom'], 10, 0.5, 15, 1.6], 'line-blur': 0.6 },
      },
      {
        id: 'road-minor', type: 'line', source: 'omt', 'source-layer': 'transportation', minzoom: 13,
        filter: ['in', ['get', 'class'], ['literal', ['minor', 'service', 'tertiary']]],
        paint: { 'line-color': C.road, 'line-width': ['interpolate', ['exponential', 1.6], ['zoom'], 13, 0.4, 17, 4] },
      },
      {
        id: 'road-major', type: 'line', source: 'omt', 'source-layer': 'transportation',
        filter: ['all', ['in', ['get', 'class'], ['literal', ['motorway', 'trunk', 'primary', 'secondary']]], ['!=', ['get', 'brunnel'], 'bridge']],
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': C.roadMajor, 'line-width': ['interpolate', ['exponential', 1.6], ['zoom'], 9, 0.5, 13, 1.6, 17, 9] },
      },
      {
        id: 'rail', type: 'line', source: 'omt', 'source-layer': 'transportation', minzoom: 12,
        filter: ['==', ['get', 'class'], 'rail'],
        paint: { 'line-color': C.roadMajor, 'line-width': 1, 'line-dasharray': [3, 2] },
      },
      {
        // Boğaz köprüleri suyun üstünde ışıklı bir çizgi olarak öne çıksın
        id: 'bridge', type: 'line', source: 'omt', 'source-layer': 'transportation',
        filter: ['all', ['==', ['get', 'brunnel'], 'bridge'], ['in', ['get', 'class'], ['literal', ['motorway', 'trunk', 'primary']]]],
        layout: { 'line-join': 'round', 'line-cap': 'butt' },
        paint: { 'line-color': C.bridge, 'line-width': ['interpolate', ['exponential', 1.6], ['zoom'], 9, 1, 13, 2.6, 17, 12] },
      },
      {
        id: 'building-3d', type: 'fill-extrusion', source: 'omt', 'source-layer': 'building', minzoom: 12.5,
        paint: {
          'fill-extrusion-color': ['interpolate', ['linear'], ['coalesce', ['get', 'render_height'], 8], 0, '#2A3D41', 25, '#3B5155', 80, '#56706F', 200, '#7E9592'],
          'fill-extrusion-height': ['interpolate', ['linear'], ['zoom'], 12.5, 0, 13.6, ['coalesce', ['get', 'render_height'], 8]],
          'fill-extrusion-base': ['coalesce', ['get', 'render_min_height'], 0],
          'fill-extrusion-opacity': 0.88,
          'fill-extrusion-vertical-gradient': true,
        },
      },
      ...['point', 'line'].map((placement) => ({
        id: `water-label-${placement}`, type: 'symbol', source: 'omt', 'source-layer': 'water_name',
        filter: ['==', ['geometry-type'], placement === 'line' ? 'LineString' : 'Point'],
        layout: {
          'text-field': ['coalesce', ['get', 'name:tr'], ['get', 'name']],
          'text-font': ['Noto Sans Italic'], 'text-size': 13, 'text-letter-spacing': 0.18,
          'symbol-placement': placement,
        },
        paint: { 'text-color': '#6F9CA0', 'text-halo-color': C.water, 'text-halo-width': 1 },
      })),
      {
        id: 'place-label', type: 'symbol', source: 'omt', 'source-layer': 'place',
        filter: ['any',
          ['in', ['get', 'class'], ['literal', ['town', 'suburb', 'island']]],
          ['all', ['>=', ['zoom'], 14], ['in', ['get', 'class'], ['literal', ['quarter', 'neighbourhood']]]]],
        layout: {
          'text-field': ['coalesce', ['get', 'name:tr'], ['get', 'name']],
          'text-font': ['Noto Sans Regular'],
          'text-size': ['interpolate', ['linear'], ['zoom'], 10, 10.5, 15, 12.5],
          'text-padding': 14,
        },
        paint: { 'text-color': C.label, 'text-halo-color': C.labelHalo, 'text-halo-width': 1.2, 'text-opacity': 0.6 },
      },
    ],
  };
}
