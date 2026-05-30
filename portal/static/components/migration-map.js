// <maxgen-migration-map>
// Renders an interactive map showing places where a person/lineage lived,
// with arcs between them in chronological order. Uses Leaflet (vanilla, no
// build pipeline) + OpenStreetMap tiles (free, no API key).

import { html, css } from 'https://esm.sh/lit@3';
import { MaxgenElement, defineOnce, bestOf } from './_base.js';

let _leafletLoaded = null;
function loadLeaflet() {
  if (_leafletLoaded) return _leafletLoaded;
  _leafletLoaded = new Promise((resolve) => {
    if (window.L) return resolve(window.L);
    const css = document.createElement('link');
    css.rel = 'stylesheet';
    css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
    css.crossOrigin = '';
    document.head.appendChild(css);
    const s = document.createElement('script');
    s.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
    s.crossOrigin = '';
    s.onload = () => resolve(window.L);
    document.head.appendChild(s);
  });
  return _leafletLoaded;
}

class MaxgenMigrationMap extends MaxgenElement {
  static properties = {
    // Each event: {label, lat, lng, year, kind, confidence}
    events:    { type: Array },
    // Optional title shown above the map
    title:     { type: String },
  };
  constructor() {
    super();
    this.events = [];
    this.title = '';
    this._map = null;
  }

  static styles = [MaxgenElement.styles, css`
    :host { display: block; }
    .wrap {
      background: white;
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      box-shadow: var(--shadow-card);
      overflow: hidden;
    }
    h3 {
      margin: 0;
      padding: 14px 18px;
      font-family: var(--font-body);
      font-size: var(--text-md);
      border-bottom: 1px solid var(--border);
      background: var(--paper);
    }
    .map {
      width: 100%;
      height: 520px;
    }
    .legend {
      padding: 10px 14px;
      background: var(--paper);
      border-top: 1px solid var(--border);
      font-family: var(--font-ui);
      font-size: var(--text-xs);
      color: var(--muted);
      display: flex; gap: 16px; flex-wrap: wrap;
    }
    .legend .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; vertical-align: middle; }
    .pop-name { font-family: var(--font-body); font-weight: bold; font-size: var(--text-base); margin-bottom: 4px; color: var(--ink); }
    .pop-kind { font-family: var(--font-ui); text-transform: uppercase; letter-spacing: 0.08em; font-size: var(--text-xs); color: var(--gold-dark); }
    .pop-meta { font-family: var(--font-ui); font-size: var(--text-xs); color: var(--muted); margin-top: 2px; }
  `];

  async firstUpdated() {
    const L = await loadLeaflet();
    const container = this.shadowRoot.querySelector('.map');
    if (!container || this._map) return;

    // Leaflet renders into a container in the SHADOW DOM — needs explicit
    // style import in shadow root, since CSS injected to <head> doesn't
    // apply inside shadow roots.
    const leafletCss = document.createElement('link');
    leafletCss.rel = 'stylesheet';
    leafletCss.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
    this.shadowRoot.appendChild(leafletCss);

    this._map = L.map(container, { scrollWheelZoom: false }).setView([35, -90], 3);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap',
      maxZoom: 18,
    }).addTo(this._map);
    this._renderEvents(L);
  }

  updated() {
    if (this._map && window.L) this._renderEvents(window.L);
  }

  _renderEvents(L) {
    if (!this._map || !this.events) return;
    // Clear old layers (markers + lines)
    if (this._layer) this._map.removeLayer(this._layer);
    this._layer = L.layerGroup().addTo(this._map);

    const sorted = (this.events || []).filter(e => e.lat != null && e.lng != null).slice()
      .sort((a, b) => (a.year || 0) - (b.year || 0));

    const KIND_COLOR = {
      birth: '#2d6a4f',
      residence: '#d4a843',
      military_service: '#a73d3d',
      death: '#1a1209',
      burial: '#6b6458',
      immigration: '#3b6cb3',
      emigration: '#3b6cb3',
      marriage: '#b8902d',
      other: '#8a7b5e',
    };

    sorted.forEach((e, i) => {
      const color = KIND_COLOR[e.kind] || KIND_COLOR.other;
      const marker = L.circleMarker([e.lat, e.lng], {
        radius: 9, color: 'white', weight: 2,
        fillColor: color, fillOpacity: 0.9
      }).addTo(this._layer);
      const popup = `
        <div>
          <div class="pop-name">${e.label || 'Event'}</div>
          <div class="pop-kind">${e.kind || 'event'} ${e.year ? '· ' + e.year : ''}</div>
          ${e.subject ? `<div class="pop-meta">${e.subject}</div>` : ''}
        </div>`;
      marker.bindPopup(popup);
      marker.bindTooltip(`${e.year || ''} · ${e.label || ''}`.trim(), { permanent: false });
    });

    // Draw the migration line in chronological order
    if (sorted.length > 1) {
      const latlngs = sorted.map(e => [e.lat, e.lng]);
      L.polyline(latlngs, {
        color: '#b8902d',
        weight: 2.5,
        dashArray: '5 8',
        opacity: 0.75,
      }).addTo(this._layer);
    }

    // Auto-fit
    if (sorted.length) {
      const bounds = L.latLngBounds(sorted.map(e => [e.lat, e.lng]));
      this._map.fitBounds(bounds, { padding: [40, 40], maxZoom: 6 });
    }
  }

  render() {
    return html`
      <div class="wrap">
        ${this.title ? html`<h3>${this.title}</h3>` : ''}
        <div class="map"></div>
        <div class="legend">
          <span><span class="dot" style="background:#2d6a4f"></span>Birth</span>
          <span><span class="dot" style="background:#d4a843"></span>Residence</span>
          <span><span class="dot" style="background:#a73d3d"></span>Military</span>
          <span><span class="dot" style="background:#b8902d"></span>Marriage</span>
          <span><span class="dot" style="background:#1a1209"></span>Death</span>
          <span><span class="dot" style="background:#3b6cb3"></span>Migration</span>
        </div>
      </div>
    `;
  }
}
defineOnce('maxgen-migration-map', MaxgenMigrationMap);
