// <maxgen-confidence-chip> and <maxgen-confidence-bar>
// The cross-cutting visual signal of MAXGEN. Used everywhere a fact has confidence.

import { html, css } from 'https://esm.sh/lit@3';
import { MaxgenElement, defineOnce, bandFor, pct } from './_base.js';

class MaxgenConfidenceChip extends MaxgenElement {
  static properties = {
    confidence: { type: Number },
    compact:    { type: Boolean },
  };
  constructor() { super(); this.confidence = null; this.compact = false; }
  static styles = [MaxgenElement.styles, css`
    :host { display: inline-block; }
    .chip {
      display: inline-flex; align-items: center; gap: 6px;
      padding: 2px 10px;
      border-radius: var(--radius-pill, 999px);
      font-family: var(--font-ui, system-ui, sans-serif);
      font-size: var(--text-xs, 0.72rem);
      font-weight: 600;
      line-height: 1.6;
      letter-spacing: 0.02em;
      white-space: nowrap;
      vertical-align: middle;
    }
    .dot {
      width: 7px; height: 7px; border-radius: 50%;
      background: currentColor; opacity: 0.7;
    }
    .label { text-transform: uppercase; }
    .pct   { opacity: 0.85; font-variant-numeric: tabular-nums; }
    .b-near-certain { background: var(--conf-near-certain); color: var(--ink); }
    .b-strong       { background: var(--conf-strong);       color: var(--ink); }
    .b-good         { background: var(--conf-good);         color: var(--paper); }
    .b-moderate     { background: var(--conf-moderate);     color: var(--paper); }
    .b-weak         { background: var(--conf-weak);         color: var(--ink); }
    .b-speculative  { background: var(--conf-speculative);  color: var(--ink); }
    .b-unknown      { background: #e5e1d8; color: var(--muted); }
  `];
  render() {
    const b = bandFor(this.confidence);
    const cls = `chip b-${b.key}`;
    return html`
      <span class="${cls}" title="${b.tooltip}"
            role="img"
            aria-label="Confidence ${b.label}, ${pct(this.confidence)}">
        <span class="dot" aria-hidden="true"></span>
        <span class="label">${b.label}</span>
        ${this.compact ? null : html`<span class="pct">${pct(this.confidence)}</span>`}
      </span>
    `;
  }
}
defineOnce('maxgen-confidence-chip', MaxgenConfidenceChip);

class MaxgenConfidenceBar extends MaxgenElement {
  static properties = { confidence: { type: Number } };
  constructor() { super(); this.confidence = null; }
  static styles = [MaxgenElement.styles, css`
    :host { display: inline-block; min-width: 80px; vertical-align: middle; }
    .wrap { display: inline-flex; flex-direction: column; gap: 2px; min-width: 80px; }
    .track {
      height: 6px; width: 100%;
      background: var(--border, #ddd8cc);
      border-radius: 3px; overflow: hidden;
    }
    .fill { height: 100%; border-radius: 3px; transition: width var(--dur-base, 220ms) var(--ease-out); }
    .meta {
      display: flex; justify-content: space-between;
      font-family: var(--font-ui); font-size: var(--text-xs);
      color: var(--muted);
    }
    .f-near-certain { background: var(--conf-near-certain); }
    .f-strong       { background: var(--conf-strong); }
    .f-good         { background: var(--conf-good); }
    .f-moderate     { background: var(--conf-moderate); }
    .f-weak         { background: var(--conf-weak); }
    .f-speculative  { background: var(--conf-speculative); }
    .f-unknown      { background: #c2bdb1; }
  `];
  render() {
    const b = bandFor(this.confidence);
    const w = this.confidence == null ? 0 : Math.round(Math.max(0, Math.min(1, this.confidence)) * 100);
    return html`
      <div class="wrap" title="${b.tooltip}"
           role="img"
           aria-label="Confidence ${b.label}, ${pct(this.confidence)}">
        <div class="track"><div class="fill f-${b.key}" style="width:${w}%"></div></div>
        <div class="meta"><span>${b.label}</span><span>${pct(this.confidence)}</span></div>
      </div>
    `;
  }
}
defineOnce('maxgen-confidence-bar', MaxgenConfidenceBar);
