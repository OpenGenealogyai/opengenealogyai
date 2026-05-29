// <maxgen-possibility-expander>
// "N possibilities, click to open" — the headline differentiator.
// Used wherever an ancestor is unknown but evidence narrows the candidates.
// Capped at 10 per Garlon. Each candidate is a probabilistic parent_assertion.

import { html, css } from 'https://esm.sh/lit@3';
import { MaxgenElement, defineOnce, bandFor, pct, formatDate } from './_base.js';

class MaxgenPossibilityExpander extends MaxgenElement {
  static properties = {
    label:      { type: String },   // e.g. "Father" / "Mother" / "Spouse"
    candidates: { type: Array },    // [{name, given_name, surname, birth, death, confidence, reasoning, source, person_id}]
    open:       { type: Boolean },
    cap:        { type: Number },   // default 10
  };
  constructor() {
    super();
    this.label = 'Unknown';
    this.candidates = [];
    this.open = false;
    this.cap = 10;
  }

  static styles = [MaxgenElement.styles, css`
    :host { display: block; }
    .expander {
      background: var(--paper, #f7f4ee);
      border: 1px dashed var(--gold-dark, #b8902d);
      border-radius: var(--radius, 6px);
      transition: box-shadow var(--dur-base) var(--ease-out);
    }
    .expander:hover { box-shadow: var(--shadow-card); }

    button.summary {
      display: flex;
      width: 100%;
      align-items: center;
      gap: 12px;
      padding: 10px 14px;
      background: transparent;
      border: none;
      text-align: left;
      cursor: pointer;
      color: var(--ink);
    }
    button.summary:focus-visible {
      outline: 2px solid var(--gold);
      outline-offset: 2px;
      border-radius: var(--radius);
    }
    .role {
      font-family: var(--font-ui);
      font-size: var(--text-xs);
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: var(--gold-dark);
      min-width: 72px;
    }
    .badge {
      font-family: var(--font-ui);
      font-weight: 600;
      font-size: var(--text-sm);
      color: var(--ink);
      flex: 1;
    }
    .badge .count {
      display: inline-block;
      padding: 2px 8px;
      background: var(--gold);
      color: var(--ink);
      border-radius: var(--radius-pill);
      font-size: var(--text-xs);
      font-variant-numeric: tabular-nums;
      margin-right: 6px;
    }
    .arrow {
      transition: transform var(--dur-base) var(--ease-out);
      color: var(--muted);
    }
    .open .arrow { transform: rotate(90deg); }

    ol.candidates {
      list-style: none;
      margin: 0;
      padding: 4px 0 8px;
      max-height: 0;
      overflow: hidden;
      transition: max-height var(--dur-slow) var(--ease-out);
    }
    .open ol.candidates {
      max-height: 1200px;
    }
    li.candidate {
      display: grid;
      grid-template-columns: 32px 1fr auto;
      gap: 12px;
      align-items: start;
      padding: 10px 14px;
      border-top: 1px solid var(--border, #ddd8cc);
    }
    li.candidate:hover { background: rgba(212, 168, 67, 0.06); }
    .rank {
      font-family: var(--font-mono);
      font-size: var(--text-sm);
      color: var(--muted);
      padding-top: 2px;
    }
    .body { min-width: 0; }
    .name {
      font-family: var(--font-body);
      font-weight: bold;
      font-size: var(--text-base);
      color: var(--ink);
    }
    .dates {
      font-family: var(--font-ui);
      font-size: var(--text-xs);
      color: var(--muted);
      font-variant-numeric: tabular-nums;
    }
    .reasoning {
      font-family: var(--font-ui);
      font-size: var(--text-sm);
      color: var(--ink);
      margin-top: 4px;
      line-height: 1.4;
    }
    .source {
      margin-top: 6px;
      display: flex; gap: 6px; flex-wrap: wrap;
    }
    .actions {
      display: flex; flex-direction: column; gap: 6px;
      align-items: flex-end;
    }
    .actions .conf { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--muted); }
    button.accept {
      padding: 4px 12px;
      background: var(--gold);
      color: var(--ink);
      border: none;
      border-radius: var(--radius-pill);
      font-family: var(--font-ui);
      font-size: var(--text-xs);
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
    }
    button.accept:hover { background: var(--gold-dark); color: var(--paper); }

    @media (prefers-reduced-motion: reduce) {
      .arrow { transition: none; }
      ol.candidates { transition: none; }
    }
  `];

  _toggle() {
    this.open = !this.open;
  }

  _accept(c) {
    this.dispatchEvent(new CustomEvent('maxgen-candidate-accepted', {
      detail: { candidate: c, label: this.label },
      bubbles: true, composed: true
    }));
  }

  render() {
    const visible = (this.candidates || []).slice(0, this.cap);
    const count = visible.length;
    const cls = `expander ${this.open ? 'open' : ''}`;

    return html`
      <div class="${cls}">
        <button class="summary"
                @click=${this._toggle}
                aria-expanded="${this.open}"
                aria-label="${this.label}, ${count} possibilities, click to ${this.open ? 'collapse' : 'expand'}">
          <span class="role">${this.label}</span>
          <span class="badge">
            <span class="count">${count}</span>
            ${count === 1 ? 'possibility' : 'possibilities'}
            <span style="color:var(--muted); font-weight: normal;">
              · click to ${this.open ? 'collapse' : 'expand'}
            </span>
          </span>
          <span class="arrow" aria-hidden="true">▶</span>
        </button>

        <ol class="candidates" role="list">
          ${visible.map((c, i) => {
            const b = bandFor(c.confidence);
            const dates = [formatDate(c.birth), formatDate(c.death)].filter(Boolean).join(' – ');
            return html`
              <li class="candidate" role="listitem">
                <div class="rank">${i + 1}.</div>
                <div class="body">
                  <div class="name">${c.name || `${c.given_name || ''} ${c.surname || ''}`.trim() || 'Unknown'}</div>
                  ${dates ? html`<div class="dates">${dates}</div>` : ''}
                  ${c.reasoning ? html`<div class="reasoning">${c.reasoning}</div>` : ''}
                  ${c.source
                    ? html`<div class="source">
                        <maxgen-source-chip
                          label="${c.source.label || 'Source'}"
                          url="${c.source.url || ''}"
                          kind="${c.source.kind || 'other'}">
                        </maxgen-source-chip>
                      </div>`
                    : ''}
                </div>
                <div class="actions">
                  <maxgen-confidence-chip compact .confidence=${c.confidence}></maxgen-confidence-chip>
                  <button class="accept"
                          @click=${() => this._accept(c)}
                          aria-label="Accept ${c.name} as the ${this.label.toLowerCase()}">
                    Accept ✓
                  </button>
                </div>
              </li>
            `;
          })}
        </ol>
      </div>
    `;
  }
}
defineOnce('maxgen-possibility-expander', MaxgenPossibilityExpander);
