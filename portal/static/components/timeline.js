// <maxgen-timeline>
// Vertical life-event timeline. Reads MaxPerson birth/death/marriage/occupation/
// event_assertions and lays them out chronologically with confidence + sources.

import { html, css } from 'https://esm.sh/lit@3';
import { MaxgenElement, defineOnce, bestOf, formatDate } from './_base.js';

const ICONS = {
  birth: '✦', death: '✕', marriage: '∞', occupation: '⚒',
  baptism: '☩', christening: '☩', immigration: '⇨', emigration: '⇦',
  naturalization: '⊕', residence: '⌂', census_enumeration: '☷', burial: '⌂',
  cremation: '⌂', military_service: '⚔', will: '✎', probate: '⚖',
  land_grant: '⚐', education: '✶', ordination: '✟',
  divorce: '⊘', other: '·'
};

function eventDate(e) {
  // Returns sortable year (lowest year_min) and the formatted string
  const y = e.year_min ?? e.year_max ?? null;
  return { sortYear: y, label: formatDate(e) };
}

class MaxgenTimeline extends MaxgenElement {
  static properties = { person: { type: Object } };
  constructor() { super(); this.person = null; }

  static styles = [MaxgenElement.styles, css`
    :host { display: block; }
    .timeline {
      position: relative;
      padding-left: 32px;
    }
    .timeline::before {
      content: '';
      position: absolute;
      left: 14px;
      top: 8px;
      bottom: 8px;
      width: 2px;
      background: var(--gold-dark);
      opacity: 0.25;
    }
    .event {
      position: relative;
      padding: 12px 0 12px 24px;
    }
    .event::before {
      content: attr(data-icon);
      position: absolute;
      left: -32px;
      top: 10px;
      width: 30px; height: 30px;
      display: flex; align-items: center; justify-content: center;
      background: var(--paper);
      border: 2px solid var(--gold-dark);
      border-radius: 50%;
      font-family: var(--font-ui);
      font-size: 14px;
      color: var(--gold-dark);
    }
    .head {
      display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap;
      margin-bottom: 4px;
    }
    .date {
      font-family: var(--font-mono);
      font-variant-numeric: tabular-nums;
      font-size: var(--text-sm);
      color: var(--ink);
      font-weight: 600;
      min-width: 110px;
    }
    .age { font-family: var(--font-ui); font-size: var(--text-xs); color: var(--muted); }
    .kind {
      font-family: var(--font-ui);
      font-size: var(--text-xs);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--gold-dark);
    }
    .body { font-family: var(--font-body); font-size: var(--text-base); color: var(--ink); }
    .place { font-style: italic; color: var(--muted); margin-left: 4px; }
    .description {
      font-family: var(--font-ui);
      font-size: var(--text-sm);
      color: var(--muted);
      margin-top: 2px;
      line-height: 1.4;
    }
    .meta {
      display: flex; gap: 8px; flex-wrap: wrap; margin-top: 6px; align-items: center;
    }
  `];

  _collect() {
    const p = this.person;
    if (!p) return [];
    const events = [];

    bestOf(p.birth_assertions) && events.push({ ...bestOf(p.birth_assertions), kind: 'birth', label: 'Born' });
    bestOf(p.death_assertions) && events.push({ ...bestOf(p.death_assertions), kind: 'death', label: 'Died' });

    (p.occupation_assertions || []).forEach(o => events.push({
      ...o, kind: 'occupation', label: 'Worked as',
      _value: o.occupation_as_written,
      year_min: o.year_min ?? o.year_max
    }));

    (p.spouse_assertions || []).forEach(s => events.push({
      ...s, kind: 'marriage', label: 'Married',
      _value: s.spouse_person_id || 'spouse',
      year_min: s.marriage_year_min, year_max: s.marriage_year_max,
      place_as_written: s.marriage_place_as_written
    }));

    (p.event_assertions || []).forEach(e => events.push({
      ...e,
      kind: e.event_type,
      label: e.event_type.replace(/_/g,' ').replace(/^./, c => c.toUpperCase())
    }));

    // Sort by start year
    events.sort((a, b) => (a.year_min || 9999) - (b.year_min || 9999));
    return events;
  }

  _ageAt(e) {
    const birth = bestOf(this.person?.birth_assertions);
    if (!birth || !birth.year_min || !e.year_min) return null;
    if (e.kind === 'birth') return null;
    const age = e.year_min - birth.year_min;
    if (age < 0 || age > 130) return null;
    return age;
  }

  render() {
    const events = this._collect();
    if (!events.length) {
      return html`<maxgen-empty message="No timeline events yet." cta="Add an event" href="#"></maxgen-empty>`;
    }

    return html`
      <div class="timeline">
        ${events.map(e => {
          const icon = ICONS[e.kind] || ICONS.other;
          const age = this._ageAt(e);
          const dateStr = formatDate(e);
          const value = e._value || '';
          return html`
            <div class="event" data-icon="${icon}">
              <div class="head">
                <span class="date">${dateStr || '—'}</span>
                ${age != null ? html`<span class="age">age ${age}</span>` : ''}
                <span class="kind">${e.label || e.kind}</span>
              </div>
              <div class="body">
                ${value}
                ${e.place_as_written ? html`<span class="place">· ${e.place_as_written}</span>` : ''}
              </div>
              ${e.description ? html`<div class="description">${e.description}</div>` : ''}
              <div class="meta">
                ${e.confidence != null ? html`<maxgen-confidence-chip compact .confidence=${e.confidence}></maxgen-confidence-chip>` : ''}
                ${e.source_record_id ? html`<maxgen-source-chip label="Record" url="/record/${e.source_record_id}" kind="other"></maxgen-source-chip>` : ''}
              </div>
            </div>
          `;
        })}
      </div>
    `;
  }
}
defineOnce('maxgen-timeline', MaxgenTimeline);
