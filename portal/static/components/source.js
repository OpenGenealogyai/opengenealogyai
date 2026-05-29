// <maxgen-source-chip>  •  <maxgen-license-badge>
// Citation pills and license stamps. Used everywhere a fact has provenance.

import { html, css } from 'https://esm.sh/lit@3';
import { MaxgenElement, defineOnce } from './_base.js';

const LICENSE_META = {
  'CC0':            { label: 'CC0',     tip: 'Public domain (CC0). Reuse without restriction.' },
  'CC-BY':          { label: 'CC BY',   tip: 'Creative Commons Attribution.' },
  'CC-BY-SA':       { label: 'CC BY-SA',tip: 'Creative Commons Attribution-ShareAlike.' },
  'public-domain':  { label: 'PD',      tip: 'Public domain.' },
  'tier2-private':  { label: 'Private', tip: 'Tier-2 private. Not redistributed.' },
  'fair-use':       { label: 'Fair use',tip: 'Fair use claim.' },
  'unknown':        { label: 'Unknown', tip: 'License not yet determined.' },
};

class MaxgenLicenseBadge extends MaxgenElement {
  static properties = { license: { type: String } };
  constructor() { super(); this.license = 'unknown'; }
  static styles = [MaxgenElement.styles, css`
    :host { display: inline-block; vertical-align: middle; }
    .badge {
      display: inline-block;
      padding: 1px 7px;
      border: 1px solid var(--border, #ddd8cc);
      border-radius: 4px;
      font-family: var(--font-ui);
      font-size: var(--text-xs);
      color: var(--muted);
      background: var(--paper, #f7f4ee);
      white-space: nowrap;
    }
    .b-CC0,
    .b-CC-BY,
    .b-CC-BY-SA,
    .b-public-domain { color: var(--success, #2d6a4f); border-color: #b8d8c0; }
    .b-tier2-private { color: var(--accent, #6b3a2a); border-color: #d6c2b0; background: #f8efe7; }
    .b-fair-use      { color: var(--warn, #e0a83b); }
  `];
  render() {
    const m = LICENSE_META[this.license] || LICENSE_META.unknown;
    return html`<span class="badge b-${this.license}" title="${m.tip}">${m.label}</span>`;
  }
}
defineOnce('maxgen-license-badge', MaxgenLicenseBadge);

class MaxgenSourceChip extends MaxgenElement {
  static properties = {
    label:  { type: String },
    url:    { type: String },
    kind:   { type: String },  // wikidata | findagrave | internet_archive | other
  };
  constructor() { super(); this.label = 'Source'; this.url = null; this.kind = 'other'; }
  static styles = [MaxgenElement.styles, css`
    :host { display: inline-block; vertical-align: middle; }
    a, span.chip {
      display: inline-flex; align-items: center; gap: 4px;
      padding: 2px 8px;
      border-radius: var(--radius-pill, 999px);
      border: 1px solid var(--border);
      background: var(--paper);
      color: var(--ink);
      font-family: var(--font-ui);
      font-size: var(--text-xs);
      text-decoration: none;
      white-space: nowrap;
    }
    a:hover { background: #efeae0; }
    .k-wikidata        { border-color: #b8a8d0; background: #f3edfa; color: #4a2b86; }
    .k-findagrave      { border-color: #d6c2b0; background: #fbf4ec; color: #6b3a2a; }
    .k-internet_archive { border-color: #b8d0e0; background: #ecf3fa; color: #1a4a78; }
    .arrow { opacity: 0.6; font-size: 0.8em; }
  `];
  render() {
    const cls = `chip k-${this.kind || 'other'}`;
    const inner = html`<span>${this.label}</span><span class="arrow" aria-hidden="true">↗</span>`;
    return this.url
      ? html`<a class="${cls}" href="${this.url}" target="_blank" rel="noopener noreferrer">${inner}</a>`
      : html`<span class="${cls}">${inner}</span>`;
  }
}
defineOnce('maxgen-source-chip', MaxgenSourceChip);
