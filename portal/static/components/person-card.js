// <maxgen-person-card> — compact card with photo, name, dates, confidence chip.
// The atomic unit that appears in pedigree nodes, search results, group sheets.

import { html, css } from 'https://esm.sh/lit@3';
import { MaxgenElement, defineOnce, bestOf, formatDate } from './_base.js';

class MaxgenPersonCard extends MaxgenElement {
  static properties = {
    person:     { type: Object },
    size:       { type: String },  // 'compact' | 'standard' | 'hero'
    clickable:  { type: Boolean },
  };
  constructor() {
    super();
    this.person = null;
    this.size = 'standard';
    this.clickable = true;
  }
  static styles = [MaxgenElement.styles, css`
    :host { display: inline-block; }
    .card {
      display: flex;
      gap: 12px;
      padding: 12px;
      background: var(--paper, #f7f4ee);
      border: 1px solid var(--border, #ddd8cc);
      border-radius: var(--radius-lg, 12px);
      box-shadow: var(--shadow-card);
      transition: box-shadow var(--dur-base) var(--ease-out);
      max-width: 360px;
      text-decoration: none;
      color: var(--ink);
    }
    .card.clickable:hover { box-shadow: var(--shadow-pop); cursor: pointer; }
    .body { display: flex; flex-direction: column; min-width: 0; flex: 1; gap: 4px; }
    .name {
      font-family: var(--font-body, Georgia, serif);
      font-size: var(--text-md);
      font-weight: bold;
      line-height: 1.2;
      color: var(--ink);
    }
    .dates {
      font-family: var(--font-ui);
      font-size: var(--text-sm);
      color: var(--muted);
      font-variant-numeric: tabular-nums;
    }
    .place {
      font-family: var(--font-ui);
      font-size: var(--text-xs);
      color: var(--muted);
      font-style: italic;
    }
    .chip-row { margin-top: 4px; }
    /* Size variants */
    .card.compact  { padding: 8px;  max-width: 260px; }
    .card.compact .name { font-size: var(--text-base); }
    .card.hero {
      padding: 20px; max-width: 540px;
      background: white;
    }
    .card.hero .name { font-size: var(--text-xl); }
    .card.hero .dates { font-size: var(--text-md); }
  `];

  _photoSize() { return this.size === 'hero' ? 'xl' : (this.size === 'compact' ? 'sm' : 'md'); }

  render() {
    const p = this.person;
    if (!p) return html`<div class="card">No person</div>`;
    const name = bestOf(p.name_assertions);
    const birth = bestOf(p.birth_assertions);
    const death = bestOf(p.death_assertions);
    const cls = `card ${this.size} ${this.clickable && p.person_id ? 'clickable' : ''}`;
    const tag = this.clickable && p.person_id ? 'a' : 'div';
    const attrs = (tag === 'a') ? `href="/person/${p.person_id}"` : '';

    const dateStr = [formatDate(birth), formatDate(death)].filter(Boolean).join(' – ');
    const placeStr = birth?.place_as_written || death?.place_as_written || '';

    // Best confidence from composite or top assertion
    const conf = (typeof p.composite_confidence === 'number' && p.composite_confidence) ||
                 name?.confidence || null;

    const content = html`
      <maxgen-photo .person=${p} size="${this._photoSize()}"></maxgen-photo>
      <div class="body">
        <div class="name">${name?.name_as_written || 'Unknown'}</div>
        ${dateStr ? html`<div class="dates">${dateStr}</div>` : ''}
        ${placeStr ? html`<div class="place">${placeStr}</div>` : ''}
        ${conf != null
          ? html`<div class="chip-row"><maxgen-confidence-chip .confidence=${conf}></maxgen-confidence-chip></div>`
          : ''}
      </div>
    `;

    return this.clickable && p.person_id
      ? html`<a class="${cls}" href="/person/${p.person_id}">${content}</a>`
      : html`<div class="${cls}">${content}</div>`;
  }
}
defineOnce('maxgen-person-card', MaxgenPersonCard);
