// <maxgen-dna-evidence>
// Renders DNA chains that touch a person (their dna_evidence[]).
// Each chain is two living kits + shared cM + likelihood = a Bayesian boost
// to this ancestor's confidence. The whole point of MAXGEN's DNA model.

import { html, css } from 'https://esm.sh/lit@3';
import { MaxgenElement, defineOnce, noisyOR, bandFor, pct } from './_base.js';

class MaxgenDnaEvidence extends MaxgenElement {
  static properties = {
    person:    { type: Object },  // a MaxPerson (.dna_evidence[])
    baseConf:  { type: Number },  // the documentary confidence before DNA
  };
  constructor() { super(); this.person = null; this.baseConf = null; }

  static styles = [MaxgenElement.styles, css`
    :host { display: block; }
    .panel {
      background: white;
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 16px;
      box-shadow: var(--shadow-card);
    }
    h3 { margin: 0 0 12px; font-family: var(--font-body); font-size: var(--text-md); }
    .summary {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 12px;
      margin-bottom: 16px;
    }
    .summary .cell {
      padding: 10px 12px;
      background: var(--paper);
      border-radius: var(--radius);
      text-align: center;
    }
    .cell .lbl { font-family: var(--font-ui); font-size: var(--text-xs); color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 4px; }
    .cell .val { font-family: var(--font-body); font-size: var(--text-lg); font-weight: bold; color: var(--ink); }
    .chains { list-style: none; padding: 0; margin: 0; }
    .chain {
      display: grid;
      grid-template-columns: 60px 1fr auto auto;
      gap: 12px;
      align-items: center;
      padding: 10px 8px;
      border-top: 1px solid var(--border);
      font-family: var(--font-ui);
      font-size: var(--text-sm);
    }
    .chain:first-of-type { border-top: none; }
    .chain .cm {
      font-family: var(--font-mono);
      font-size: var(--text-md);
      font-weight: bold;
      color: var(--gold-dark);
      font-variant-numeric: tabular-nums;
    }
    .chain .desc { color: var(--ink); }
    .chain .kits { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--muted); }
    .formula {
      margin-top: 16px;
      padding: 12px;
      background: var(--paper);
      border-left: 3px solid var(--gold);
      border-radius: var(--radius);
      font-family: var(--font-mono);
      font-size: var(--text-xs);
      color: var(--ink);
      line-height: 1.6;
    }
    .formula .step { display: block; }
  `];

  render() {
    const p = this.person;
    const chains = (p?.dna_evidence) || [];
    if (!chains.length) {
      return html`<maxgen-empty message="No DNA evidence linked to this person yet." cta="See DNA tools" href="/dna"></maxgen-empty>`;
    }
    const base = this.baseConf ?? p.composite_confidence ?? 0;
    const boosts = chains.map(c => c.confidence_delta ?? c.likelihood ?? 0);
    // Posterior: 1 - (1-base) * Π(1-boost)
    let prod = 1 - base;
    boosts.forEach(b => { prod *= (1 - b); });
    const posterior = 1 - prod;
    const lift = posterior - base;

    return html`
      <div class="panel">
        <h3>DNA evidence for this ancestor</h3>
        <div class="summary">
          <div class="cell">
            <div class="lbl">Doc-only confidence</div>
            <div class="val">${pct(base)}</div>
            <maxgen-confidence-chip compact .confidence=${base}></maxgen-confidence-chip>
          </div>
          <div class="cell">
            <div class="lbl">After DNA boost</div>
            <div class="val">${pct(posterior)}</div>
            <maxgen-confidence-chip compact .confidence=${posterior}></maxgen-confidence-chip>
          </div>
          <div class="cell">
            <div class="lbl">Lift</div>
            <div class="val" style="color: var(--success);">+${(lift * 100).toFixed(1)}%</div>
            <span style="font-family: var(--font-ui); font-size: var(--text-xs); color: var(--muted);">from ${chains.length} chain${chains.length === 1 ? '' : 's'}</span>
          </div>
        </div>

        <ol class="chains">
          ${chains.map((c, i) => html`
            <li class="chain">
              <span class="cm">${c.shared_cm} cM</span>
              <span class="desc">
                ${c.path_length_generations} generations apart
                · likelihood ${pct(c.likelihood)}
              </span>
              <span class="kits">
                ${(c.dna_id_a || '').slice(0, 8)} ↔ ${(c.dna_id_b || '').slice(0, 8)}
              </span>
              <maxgen-confidence-chip compact .confidence=${c.confidence_delta ?? c.likelihood}></maxgen-confidence-chip>
            </li>
          `)}
        </ol>

        <div class="formula">
          <span class="step">Noisy-OR aggregation (per CONFIDENCE_CALIBRATION.md):</span>
          <span class="step">posterior = 1 − (1 − base) × ∏(1 − boost_i)</span>
          <span class="step">= 1 − (1 − ${base.toFixed(2)}) × ${chains.map((_, i) => `(1 − ${(boosts[i]).toFixed(2)})`).join(' × ')}</span>
          <span class="step">= ${posterior.toFixed(3)}</span>
        </div>
      </div>
    `;
  }
}
defineOnce('maxgen-dna-evidence', MaxgenDnaEvidence);
