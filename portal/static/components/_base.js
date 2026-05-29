// MAXGEN base — shared Lit class + confidence formatter + helpers.
// Every <maxgen-*> component imports MaxgenElement from here.
//
// brand.md: voice/tokens.  microcopy.md: labels.  CONFIDENCE_CALIBRATION.md: bands.

import { LitElement, css } from 'https://esm.sh/lit@3';

// ─── Confidence formatting ─────────────────────────────────────────────
// Mirrors docs/CONFIDENCE_CALIBRATION.md bands.

export const CONF_BANDS = [
  { min: 0.95, max: 1.00, key: 'near-certain', label: 'Near-certain',
    tooltip: 'Direct primary source. Filed at the event by an informed witness.' },
  { min: 0.85, max: 0.95, key: 'strong',       label: 'Strong',
    tooltip: 'Direct evidence with a minor caveat (e.g. informant slightly removed).' },
  { min: 0.70, max: 0.85, key: 'good',         label: 'Good',
    tooltip: 'Consistent secondary sources, or one solid derivative.' },
  { min: 0.50, max: 0.70, key: 'moderate',     label: 'Moderate',
    tooltip: 'Single secondary source, or indirect inference.' },
  { min: 0.30, max: 0.50, key: 'weak',         label: 'Weak',
    tooltip: 'Uncorroborated late or derivative source.' },
  { min: 0.00, max: 0.30, key: 'speculative',  label: 'Speculative',
    tooltip: 'Guess, placeholder, or actively conflicting.' },
];

/** Return the band (object) for a confidence value 0..1. */
export function bandFor(c) {
  if (c == null || isNaN(c)) return { key: 'unknown', label: 'Unknown', tooltip: 'No confidence recorded.' };
  const v = Math.max(0, Math.min(1, +c));
  // Upper-inclusive ranges; we walk top-down so near-certain wins ties.
  for (const b of CONF_BANDS) if (v >= b.min && (v < b.max || b.max === 1.00 && v <= 1.00)) return b;
  return CONF_BANDS[CONF_BANDS.length - 1];
}

/** "73%"  •  used in chip + bar labels. */
export function pct(c) {
  if (c == null || isNaN(c)) return '—';
  return Math.round(c * 100) + '%';
}

/** Color token CSS var for a band key. */
export function bandColorVar(key) {
  return `var(--conf-${key})`;
}

// ─── Date helpers (docs/microcopy.md date display table) ───────────────

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

/** Render an assertion-style date object as the patterned string. */
export function formatDate(d) {
  if (!d) return '';
  const { year_min, year_max, month, day, date_type } = d;
  if (year_min == null && year_max == null) return '';
  if (year_min != null && year_max != null && year_min === year_max) {
    if (day && month) return `${day} ${MONTHS[month-1]} ${year_min}`;
    if (month)        return `${MONTHS[month-1]} ${year_min}`;
    return (date_type === 'estimated') ? `around ${year_min}` : `${year_min}`;
  }
  if (year_min != null && year_max != null) return `${year_min}–${year_max}`;
  if (year_max != null) return `before ${year_max}`;
  if (year_min != null) return `after ${year_min}`;
  return '';
}

/** Pick the highest-confidence assertion from an array; null if empty. */
export function bestOf(assertions) {
  if (!Array.isArray(assertions) || !assertions.length) return null;
  return assertions.slice().sort((a, b) => (b.confidence || 0) - (a.confidence || 0))[0];
}

/** Combine independent assertions via noisy-OR (per CONFIDENCE_CALIBRATION.md). */
export function noisyOR(confidences) {
  if (!confidences.length) return 0;
  let p = 1;
  for (const c of confidences) p *= (1 - Math.max(0, Math.min(1, +c || 0)));
  return 1 - p;
}

// ─── Shared component base ─────────────────────────────────────────────

export class MaxgenElement extends LitElement {
  // Inherited reset + token plumbing for every component.
  static styles = css`
    :host { box-sizing: border-box; font-family: Georgia, serif; color: var(--ink, #1a1209); }
    :host([hidden]) { display: none; }
    *, *::before, *::after { box-sizing: border-box; }
    button { font: inherit; cursor: pointer; }
    button:focus-visible { outline: 2px solid var(--gold, #d4a843); outline-offset: 2px; }
    a:focus-visible      { outline: 2px solid var(--gold, #d4a843); outline-offset: 2px; }
  `;
}

// Tag every defineCustomElement call so we never accidentally re-register.
export function defineOnce(tag, ctor) {
  if (!customElements.get(tag)) customElements.define(tag, ctor);
}
