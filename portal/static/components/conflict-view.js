// <maxgen-conflict-view>
// Two (or more) assertions that disagree — render side-by-side, never hide.
// Per the MAXGEN philosophy: conflict is data, not error.

import { html, css } from 'https://esm.sh/lit@3';
import { MaxgenElement, defineOnce } from './_base.js';

class MaxgenConflictView extends MaxgenElement {
  static properties = {
    label:      { type: String },  // e.g. "Birth year"
    assertions: { type: Array },   // [{value, confidence, source}]
  };
  constructor() { super(); this.label = ''; this.assertions = []; }

  static styles = [MaxgenElement.styles, css`
    :host { display: block; }
    .conflict {
      border: 1px solid var(--warn, #e0a83b);
      border-radius: var(--radius-lg, 12px);
      overflow: hidden;
      background: var(--warn-bg, #fff7ea);
    }
    .header {
      display: flex; align-items: center; gap: 8px;
      padding: 8px 14px;
      background: rgba(224, 168, 59, 0.18);
      font-family: var(--font-ui);
      font-size: var(--text-xs);
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: #8a5a10;
      font-weight: 600;
    }
    .icon { width: 14px; height: 14px; }
    .options {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 0;
    }
    .option {
      padding: 12px 14px;
      background: white;
      border-right: 1px dashed var(--border);
      display: flex; flex-direction: column; gap: 6px;
    }
    .option:last-child { border-right: none; }
    .value {
      font-family: var(--font-body);
      font-size: var(--text-md);
      color: var(--ink);
      font-weight: 500;
    }
    .source {
      display: flex; flex-wrap: wrap; gap: 4px;
    }
    .footer {
      padding: 6px 14px;
      background: rgba(224, 168, 59, 0.08);
      font-family: var(--font-ui);
      font-size: var(--text-xs);
      color: var(--muted);
      font-style: italic;
    }
  `];

  render() {
    const a = this.assertions || [];
    return html`
      <div class="conflict" role="region" aria-label="Conflicting ${this.label} — ${a.length} assertions">
        <div class="header">
          <svg class="icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M12 2L1 21h22L12 2zm0 6l7.5 13H4.5L12 8zm-1 4v3h2v-3h-2zm0 4v2h2v-2h-2z"/>
          </svg>
          ${this.label} — ${a.length} assertions disagree
        </div>
        <div class="options">
          ${a.map(x => html`
            <div class="option">
              <div class="value">${x.value}</div>
              <maxgen-confidence-chip .confidence=${x.confidence}></maxgen-confidence-chip>
              ${x.source ? html`
                <div class="source">
                  <maxgen-source-chip
                    label="${x.source.label || 'Source'}"
                    url="${x.source.url || ''}"
                    kind="${x.source.kind || 'other'}">
                  </maxgen-source-chip>
                </div>` : ''}
            </div>
          `)}
        </div>
        <div class="footer">
          Both kept — MAXGEN never hides a disagreement. New evidence shifts the confidence; nothing is deleted.
        </div>
      </div>
    `;
  }
}
defineOnce('maxgen-conflict-view', MaxgenConflictView);
