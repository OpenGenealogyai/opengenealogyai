// <maxgen-fact>  •  <maxgen-date>  •  <maxgen-place>
// Atomic fact rendering. Each fact = value + confidence chip + source chips.

import { html, css } from 'https://esm.sh/lit@3';
import { MaxgenElement, defineOnce, formatDate } from './_base.js';

class MaxgenDate extends MaxgenElement {
  static properties = { d: { type: Object } };
  constructor() { super(); this.d = null; }
  static styles = [MaxgenElement.styles, css`
    :host { display: inline; }
    span { font-variant-numeric: tabular-nums; }
  `];
  render() {
    const s = formatDate(this.d);
    return html`<span>${s}</span>`;
  }
}
defineOnce('maxgen-date', MaxgenDate);

class MaxgenPlace extends MaxgenElement {
  static properties = {
    place:    { type: String },
    registry: { type: Object },  // optional matched entry from person.place_registry
  };
  constructor() { super(); this.place = ''; this.registry = null; }
  static styles = [MaxgenElement.styles, css`
    :host { display: inline; }
    .place { font-style: italic; }
    .historical {
      font-family: var(--font-ui); font-size: var(--text-xs);
      color: var(--muted); margin-left: 4px;
    }
  `];
  render() {
    if (!this.place) return html``;
    return html`
      <span class="place">${this.place}</span>
      ${this.registry?.historical_polity
        ? html`<span class="historical">(${this.registry.historical_polity})</span>`
        : ''}
    `;
  }
}
defineOnce('maxgen-place', MaxgenPlace);

class MaxgenFact extends MaxgenElement {
  static properties = {
    label:      { type: String },
    value:      { type: String },
    confidence: { type: Number },
    sources:    { type: Array },   // array of {label, url, kind}
  };
  constructor() {
    super();
    this.label = '';
    this.value = '';
    this.confidence = null;
    this.sources = [];
  }
  static styles = [MaxgenElement.styles, css`
    :host { display: block; }
    .row {
      display: grid;
      grid-template-columns: 110px 1fr auto;
      align-items: baseline;
      gap: 12px;
      padding: 6px 0;
      border-bottom: 1px dashed var(--border, #ddd8cc);
    }
    .row:last-child { border-bottom: none; }
    .label {
      font-family: var(--font-ui);
      font-size: var(--text-sm);
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .value { font-size: var(--text-base); color: var(--ink); }
    .sources {
      display: flex; flex-wrap: wrap; gap: 4px;
      justify-content: flex-end;
    }
    @media (max-width: 600px) {
      .row { grid-template-columns: 1fr; gap: 4px; }
      .sources { justify-content: flex-start; }
    }
  `];
  render() {
    return html`
      <div class="row">
        <div class="label">${this.label}</div>
        <div class="value">
          ${this.value || html`<span style="color:var(--muted)">—</span>`}
          ${this.confidence != null
            ? html`<maxgen-confidence-chip compact .confidence=${this.confidence}></maxgen-confidence-chip>`
            : ''}
        </div>
        <div class="sources">
          ${(this.sources || []).map(s => html`
            <maxgen-source-chip
              label="${s.label}"
              url="${s.url || ''}"
              kind="${s.kind || 'other'}">
            </maxgen-source-chip>`)}
        </div>
      </div>
    `;
  }
}
defineOnce('maxgen-fact', MaxgenFact);
