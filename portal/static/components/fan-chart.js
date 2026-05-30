// <maxgen-fan-chart>
// Radial pedigree. Subject at center. Each ancestor = an arc segment
// colored by their confidence band. Like Gramps Web's fan view.

import { html, css, svg } from 'https://esm.sh/lit@3';
import { MaxgenElement, defineOnce, bestOf, bandFor } from './_base.js';

class MaxgenFanChart extends MaxgenElement {
  static properties = {
    pedigree:    { type: Object },  // same shape as pedigree-chart
    generations: { type: Number },  // 5-8
    size:        { type: Number },  // px
    colorBy:     { type: String },  // 'confidence' | 'surname' | 'birth_decade'
  };
  constructor() {
    super();
    this.pedigree = null;
    this.generations = 6;
    this.size = 640;
    this.colorBy = 'confidence';
  }

  static styles = [MaxgenElement.styles, css`
    :host { display: block; }
    .wrap {
      position: relative;
      background: var(--paper);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 16px;
      box-shadow: var(--shadow-card);
    }
    .toolbar {
      display: flex; gap: 8px; align-items: center;
      margin-bottom: 12px;
      font-family: var(--font-ui);
      font-size: var(--text-sm);
    }
    select {
      font-family: var(--font-ui);
      font-size: var(--text-sm);
      padding: 4px 8px;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      background: white;
    }
    svg.fan {
      display: block; margin: 0 auto;
    }
    .arc-text {
      font-family: var(--font-ui);
      font-size: 10px;
      fill: var(--ink);
      pointer-events: none;
    }
    .center-label {
      font-family: var(--font-body);
      font-weight: bold;
      text-anchor: middle;
      fill: var(--ink);
    }
  `];

  // Color for an ancestor at gen k, slot s
  _colorFor(person, gen, slot) {
    if (this.colorBy === 'birth_decade' && person) {
      const b = bestOf(person.birth_assertions);
      const y = b?.year_min;
      if (y) {
        const dec = Math.floor(y / 10) * 10;
        const hue = (dec - 1700) * 4 % 360;
        return `hsl(${hue}, 50%, 70%)`;
      }
    }
    if (this.colorBy === 'surname' && person) {
      const sur = bestOf(person.name_assertions)?.surname || '';
      let h = 0;
      for (const c of sur) h = (h * 31 + c.charCodeAt(0)) % 360;
      return `hsl(${h}, 45%, 72%)`;
    }
    // Default: confidence
    if (!person) return '#e0d8c8';
    const c = person.composite_confidence ?? bestOf(person.name_assertions)?.confidence ?? 0;
    const b = bandFor(c);
    return `var(--conf-${b.key})`;
  }

  _arcPath(cx, cy, r1, r2, a1, a2) {
    // Arc from angle a1 to a2 (radians), between radii r1 (inner) and r2 (outer)
    const x1 = cx + r1 * Math.cos(a1);
    const y1 = cy + r1 * Math.sin(a1);
    const x2 = cx + r2 * Math.cos(a1);
    const y2 = cy + r2 * Math.sin(a1);
    const x3 = cx + r2 * Math.cos(a2);
    const y3 = cy + r2 * Math.sin(a2);
    const x4 = cx + r1 * Math.cos(a2);
    const y4 = cy + r1 * Math.sin(a2);
    const largeArc = (a2 - a1) > Math.PI ? 1 : 0;
    return `M ${x1},${y1} L ${x2},${y2} A ${r2},${r2} 0 ${largeArc} 1 ${x3},${y3} L ${x4},${y4} A ${r1},${r1} 0 ${largeArc} 0 ${x1},${y1} Z`;
  }

  // Flatten the pedigree tree into a per-generation array of persons (or null)
  _flatten() {
    const gens = this.generations;
    const out = Array.from({ length: gens }, () => []);
    const walk = (ped, gen, slot) => {
      if (gen >= gens) return;
      out[gen][slot] = ped?.person || null;
      if (ped?.father) walk(ped.father, gen + 1, slot * 2);
      if (ped?.mother) walk(ped.mother, gen + 1, slot * 2 + 1);
    };
    if (this.pedigree) walk(this.pedigree, 0, 0);
    // pad each gen to its slot count
    for (let k = 0; k < gens; k++) {
      const need = Math.pow(2, k);
      while (out[k].length < need) out[k].push(null);
    }
    return out;
  }

  render() {
    const size = this.size;
    const cx = size / 2, cy = size / 2;
    const flat = this._flatten();
    const gens = this.generations;

    // Center person is full disc; rings around it
    const innerR = 48;
    const ringW = (size / 2 - innerR - 12) / (gens - 1);

    // Fan covers full circle (2π)
    const startAngle = -Math.PI / 2;  // start at top
    const totalAngle = Math.PI * 2;

    const arcs = [];
    for (let k = 1; k < gens; k++) {
      const slotsInGen = Math.pow(2, k);
      const anglePerSlot = totalAngle / slotsInGen;
      const r1 = innerR + (k - 1) * ringW;
      const r2 = innerR + k * ringW;
      for (let s = 0; s < slotsInGen; s++) {
        const a1 = startAngle + s * anglePerSlot;
        const a2 = a1 + anglePerSlot;
        const person = flat[k][s];
        const color = this._colorFor(person, k, s);
        const name = person ? (bestOf(person.name_assertions)?.surname || bestOf(person.name_assertions)?.name_as_written?.split(' ').slice(-1)[0] || '') : '';
        const midAngle = (a1 + a2) / 2;
        const midR = (r1 + r2) / 2;
        const tx = cx + midR * Math.cos(midAngle);
        const ty = cy + midR * Math.sin(midAngle);
        arcs.push({ path: this._arcPath(cx, cy, r1, r2, a1, a2), color, name, tx, ty, hasPerson: !!person, midAngle });
      }
    }

    const center = flat[0][0];
    const centerName = center ? (bestOf(center.name_assertions)?.name_as_written || 'Subject') : 'Subject';

    return html`
      <div class="wrap">
        <div class="toolbar">
          <label>Color by:</label>
          <select @change=${(e) => { this.colorBy = e.target.value; this.requestUpdate(); }}>
            <option value="confidence" ?selected=${this.colorBy==='confidence'}>Confidence band</option>
            <option value="surname" ?selected=${this.colorBy==='surname'}>Surname</option>
            <option value="birth_decade" ?selected=${this.colorBy==='birth_decade'}>Birth decade</option>
          </select>
          <span style="margin-left: auto; color: var(--muted); font-size: var(--text-xs);">
            ${gens} generations · ${flat.reduce((acc, g) => acc + g.filter(Boolean).length, 0)} known ancestors
          </span>
        </div>
        <svg class="fan" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
          ${arcs.map(a => svg`
            <path d="${a.path}"
                  fill="${a.color}"
                  stroke="white"
                  stroke-width="1"
                  opacity="${a.hasPerson ? 1 : 0.35}">
              <title>${a.name || 'Unknown'}</title>
            </path>
            ${a.hasPerson && a.name ? svg`
              <text class="arc-text"
                    x="${a.tx}" y="${a.ty}"
                    text-anchor="middle"
                    dominant-baseline="central"
                    transform="rotate(${(a.midAngle * 180 / Math.PI) + (Math.cos(a.midAngle) < 0 ? 180 : 0)}, ${a.tx}, ${a.ty})">
                ${a.name.slice(0, 10)}
              </text>` : ''}
          `)}
          <circle cx="${cx}" cy="${cy}" r="${innerR}"
                  fill="var(--gold)"
                  stroke="white"
                  stroke-width="2"/>
          <text class="center-label" x="${cx}" y="${cy - 4}" font-size="11">
            ${centerName.split(' ').slice(0, 1).join(' ')}
          </text>
          <text class="center-label" x="${cx}" y="${cy + 10}" font-size="11">
            ${centerName.split(' ').slice(1).join(' ').slice(0, 14)}
          </text>
        </svg>
      </div>
    `;
  }
}
defineOnce('maxgen-fan-chart', MaxgenFanChart);
