// <maxgen-merge-ui>
// Side-by-side merge interface. Two people that might be the same;
// pick which assertions to keep on the survivor. Writes a merge_history
// entry per MAXGEN v1.3 — the absorbed entity survives as duplicate_of,
// merge is reversible.

import { html, css } from 'https://esm.sh/lit@3';
import { MaxgenElement, defineOnce, bestOf, formatDate } from './_base.js';

class MaxgenMergeUI extends MaxgenElement {
  static properties = {
    personA: { type: Object },
    personB: { type: Object },
    matchSignals: { type: Object },  // {name_similarity, year_overlap, place_match, ...}
  };
  constructor() {
    super();
    this.personA = null;
    this.personB = null;
    this.matchSignals = null;
    this._chosen = {};   // per-field: 'A' | 'B' | 'both'
  }

  static styles = [MaxgenElement.styles, css`
    :host { display: block; }
    .panel {
      background: white;
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 20px;
      box-shadow: var(--shadow-card);
    }
    h3 { margin: 0 0 4px; font-family: var(--font-body); font-size: var(--text-md); }
    .sub {
      font-family: var(--font-ui);
      font-size: var(--text-sm);
      color: var(--muted);
      margin-bottom: 16px;
    }
    .signals {
      display: flex; gap: 16px;
      padding: 10px 14px;
      background: var(--paper);
      border-radius: var(--radius);
      margin-bottom: 16px;
      font-family: var(--font-ui);
      font-size: var(--text-sm);
    }
    .signal { display: flex; flex-direction: column; align-items: flex-start; }
    .signal .lbl { font-size: var(--text-xs); color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }
    .signal .val { font-weight: 600; }
    .grid {
      display: grid;
      grid-template-columns: 1fr 200px 1fr;
      gap: 0;
      border-top: 1px solid var(--border);
    }
    .row {
      display: contents;
    }
    .cell {
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      font-family: var(--font-ui);
      font-size: var(--text-sm);
      display: flex; align-items: center; gap: 8px;
    }
    .cell.label {
      justify-content: center;
      background: var(--paper);
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: var(--text-xs);
      font-weight: 600;
    }
    .cell.a { border-right: 1px dashed var(--border); }
    .cell.b { border-left: 1px dashed var(--border); }
    .picker {
      display: flex; gap: 4px;
      justify-content: center;
      background: var(--paper);
    }
    .picker button {
      padding: 2px 6px;
      font-family: var(--font-ui);
      font-size: var(--text-xs);
      background: transparent;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      cursor: pointer;
      color: var(--muted);
    }
    .picker button.active {
      background: var(--gold);
      color: var(--ink);
      border-color: var(--gold-dark);
      font-weight: 600;
    }
    .picker button:hover { color: var(--ink); }
    .controls {
      display: flex; gap: 12px; justify-content: flex-end;
      margin-top: 16px;
      padding-top: 16px;
      border-top: 2px solid var(--border);
    }
    button.primary {
      padding: 8px 20px;
      background: var(--gold);
      color: var(--ink);
      border: none;
      border-radius: var(--radius);
      font-family: var(--font-ui);
      font-weight: 600;
      cursor: pointer;
    }
    button.primary:hover { background: var(--gold-dark); color: var(--paper); }
    button.secondary {
      padding: 8px 20px;
      background: white;
      color: var(--ink);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      font-family: var(--font-ui);
      cursor: pointer;
    }
    .preview {
      margin-top: 14px;
      padding: 12px;
      background: var(--success-bg);
      border-left: 3px solid var(--success);
      border-radius: var(--radius);
      font-family: var(--font-ui);
      font-size: var(--text-sm);
      line-height: 1.5;
    }
  `];

  _pickSide(field, side) {
    this._chosen = { ...this._chosen, [field]: side };
    this.requestUpdate();
  }

  _fact(person, kind) {
    if (kind === 'name')      return bestOf(person?.name_assertions)?.name_as_written;
    if (kind === 'birth')     {
      const b = bestOf(person?.birth_assertions);
      return b ? `${formatDate(b)}${b.place_as_written ? ', ' + b.place_as_written : ''}` : '';
    }
    if (kind === 'death')     {
      const d = bestOf(person?.death_assertions);
      return d ? `${formatDate(d)}${d.place_as_written ? ', ' + d.place_as_written : ''}` : '';
    }
    if (kind === 'father')    {
      const p = (person?.parent_assertions || []).find(a => a.parent_role === 'father');
      return p?.parent_name || p?.parent_person_id;
    }
    if (kind === 'mother')    {
      const p = (person?.parent_assertions || []).find(a => a.parent_role === 'mother');
      return p?.parent_name || p?.parent_person_id;
    }
    if (kind === 'sources')   { return (person?.source_record_ids || []).length + ' source(s)'; }
    if (kind === 'photos')    { return (person?.photo_assertions || []).length + ' photo(s)'; }
    return '';
  }

  _factConf(person, kind) {
    if (kind === 'name')  return bestOf(person?.name_assertions)?.confidence;
    if (kind === 'birth') return bestOf(person?.birth_assertions)?.confidence;
    if (kind === 'death') return bestOf(person?.death_assertions)?.confidence;
    return null;
  }

  _row(field, label) {
    const a = this._fact(this.personA, field);
    const b = this._fact(this.personB, field);
    const aConf = this._factConf(this.personA, field);
    const bConf = this._factConf(this.personB, field);
    const chosen = this._chosen[field] || 'A';
    return html`
      <div class="row">
        <div class="cell a">
          ${a || html`<span style="color:var(--muted)">—</span>`}
          ${aConf != null ? html`<maxgen-confidence-chip compact .confidence=${aConf}></maxgen-confidence-chip>` : ''}
        </div>
        <div class="cell label">
          ${label}
          <div class="picker">
            <button class="${chosen==='A'?'active':''}" @click=${() => this._pickSide(field,'A')}>Keep A</button>
            <button class="${chosen==='both'?'active':''}" @click=${() => this._pickSide(field,'both')}>Both</button>
            <button class="${chosen==='B'?'active':''}" @click=${() => this._pickSide(field,'B')}>Keep B</button>
          </div>
        </div>
        <div class="cell b">
          ${b || html`<span style="color:var(--muted)">—</span>`}
          ${bConf != null ? html`<maxgen-confidence-chip compact .confidence=${bConf}></maxgen-confidence-chip>` : ''}
        </div>
      </div>
    `;
  }

  _doMerge() {
    // Emits event — the page is responsible for the actual write.
    this.dispatchEvent(new CustomEvent('maxgen-merge', {
      detail: {
        survivor: this.personA.person_id,
        absorbed: this.personB.person_id,
        choices: this._chosen,
        merge_confidence: this.matchSignals?.combined || 0.8,
        merge_method: 'manual',
      },
      bubbles: true, composed: true
    }));
  }

  render() {
    if (!this.personA || !this.personB) {
      return html`<div class="panel"><maxgen-empty message="No merge candidates to review." cta="See suggestions" href="#"></maxgen-empty></div>`;
    }
    return html`
      <div class="panel">
        <h3>Merge candidate review</h3>
        <div class="sub">
          MAXGEN merges are reversible — the absorbed entity persists with
          <code>merge_status='merged_away'</code> and <code>duplicate_of</code> pointing
          to the survivor.
        </div>

        ${this.matchSignals ? html`
          <div class="signals">
            <div class="signal">
              <span class="lbl">Match score</span>
              <maxgen-confidence-chip .confidence=${this.matchSignals.combined || 0.5}></maxgen-confidence-chip>
            </div>
            <div class="signal"><span class="lbl">Name similarity</span><span class="val">${Math.round((this.matchSignals.name_similarity || 0) * 100)}%</span></div>
            <div class="signal"><span class="lbl">Year overlap</span><span class="val">${Math.round((this.matchSignals.year_overlap || 0) * 100)}%</span></div>
            <div class="signal"><span class="lbl">Place match</span><span class="val">${this.matchSignals.place_match ? 'Yes' : 'No'}</span></div>
          </div>
        ` : ''}

        <div class="grid">
          <div class="row">
            <div class="cell label" style="grid-column: 1 / 2; background: var(--ink); color: var(--paper); justify-content: flex-start;">Person A (survivor)</div>
            <div class="cell label" style="background: var(--ink); color: var(--paper);">Field</div>
            <div class="cell label" style="grid-column: 3 / 4; background: var(--ink); color: var(--paper); justify-content: flex-start;">Person B (will be absorbed)</div>
          </div>
          ${this._row('name', 'Name')}
          ${this._row('birth', 'Born')}
          ${this._row('death', 'Died')}
          ${this._row('father', 'Father')}
          ${this._row('mother', 'Mother')}
          ${this._row('sources', 'Sources')}
          ${this._row('photos', 'Photos')}
        </div>

        <div class="controls">
          <button class="secondary">Not a match — keep separate</button>
          <button class="primary" @click=${this._doMerge}>Merge B into A</button>
        </div>

        <div class="preview">
          <strong>Result if you merge:</strong>
          Person A keeps its <code>person_id</code> and gains a new
          <code>merge_history[]</code> entry. Person B's <code>merge_status</code>
          becomes <code>merged_away</code> and its <code>duplicate_of</code> points
          to A. Nothing is deleted — undo is one click for 30 days.
        </div>
      </div>
    `;
  }
}
defineOnce('maxgen-merge-ui', MaxgenMergeUI);
