// <maxgen-person-profile>
// The most-visited page's content. Hero + tabbed body.
// Reads a full MaxPerson JSON; composes from primitives.

import { html, css } from 'https://esm.sh/lit@3';
import { MaxgenElement, defineOnce, bestOf, formatDate } from './_base.js';

const TABS = [
  { key: 'facts',   label: 'Facts' },
  { key: 'family',  label: 'Family' },
  { key: 'photos',  label: 'Photos' },
  { key: 'dna',     label: 'DNA' },
  { key: 'sources', label: 'Sources' },
];

class MaxgenPersonProfile extends MaxgenElement {
  static properties = {
    person:    { type: Object },
    family:    { type: Object },  // optional context: {father, mother, spouses[], children[]}
    activeTab: { type: String },
  };
  constructor() {
    super();
    this.person = null;
    this.family = null;
    this.activeTab = 'facts';
  }

  static styles = [MaxgenElement.styles, css`
    :host { display: block; max-width: 1040px; margin: 0 auto; }

    /* ── Hero ───────────────────────────────────────────── */
    .hero {
      background: white;
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 24px;
      box-shadow: var(--shadow-card);
      display: grid;
      grid-template-columns: 200px 1fr auto;
      gap: 24px;
      align-items: start;
      margin-bottom: 16px;
    }
    @media (max-width: 720px) {
      .hero { grid-template-columns: 1fr; text-align: center; }
    }
    .name {
      font-family: var(--font-body);
      font-size: var(--text-xl);
      font-weight: bold;
      color: var(--ink);
      margin-bottom: 4px;
      line-height: 1.1;
    }
    .dates {
      font-family: var(--font-ui);
      font-size: var(--text-md);
      color: var(--muted);
      font-variant-numeric: tabular-nums;
      margin-bottom: 4px;
    }
    .place {
      font-family: var(--font-ui);
      font-size: var(--text-sm);
      color: var(--muted);
      font-style: italic;
      margin-bottom: 12px;
    }
    .parents-line {
      font-family: var(--font-ui);
      font-size: var(--text-sm);
      color: var(--ink);
      margin-bottom: 12px;
    }
    .parents-line .pname {
      font-family: var(--font-body);
      font-weight: bold;
    }
    .pad-actions {
      display: flex; flex-direction: column; gap: 8px;
      align-items: flex-end;
    }
    @media (max-width: 720px) {
      .pad-actions { align-items: center; }
    }

    /* ── Tabs ───────────────────────────────────────────── */
    .tabs {
      display: flex; gap: 4px;
      border-bottom: 2px solid var(--border);
      margin-bottom: 16px;
      overflow-x: auto;
    }
    .tab {
      padding: 10px 16px;
      background: transparent;
      border: none;
      border-bottom: 3px solid transparent;
      font-family: var(--font-ui);
      font-size: var(--text-sm);
      color: var(--muted);
      cursor: pointer;
      white-space: nowrap;
      margin-bottom: -2px;
      letter-spacing: 0.03em;
    }
    .tab.active {
      color: var(--gold-dark);
      border-bottom-color: var(--gold);
      font-weight: 600;
    }
    .tab:hover { color: var(--ink); }
    .tab:focus-visible {
      outline: 2px solid var(--gold);
      outline-offset: 2px;
    }

    /* ── Tab panels ─────────────────────────────────────── */
    .panel {
      background: white;
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 20px;
      box-shadow: var(--shadow-card);
    }
    .section-h {
      font-family: var(--font-ui);
      font-size: var(--text-xs);
      color: var(--gold-dark);
      text-transform: uppercase;
      letter-spacing: 0.1em;
      margin: 0 0 8px;
    }
    .section + .section { margin-top: 16px; }
    .photo-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
      gap: 12px;
    }
    .photo-grid figure {
      margin: 0;
      text-align: center;
    }
    .photo-grid figcaption {
      font-family: var(--font-ui);
      font-size: var(--text-xs);
      color: var(--muted);
      margin-top: 4px;
    }
    .family-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 12px;
    }
    ul.bare { list-style: none; padding: 0; margin: 0; }
    .empty-row {
      padding: 12px;
      font-family: var(--font-ui);
      font-size: var(--text-sm);
      color: var(--muted);
      font-style: italic;
    }
  `];

  _set(tab) { this.activeTab = tab; }

  _facts() {
    const p = this.person;
    const out = [];
    bestOf(p.birth_assertions) && out.push(['Born', bestOf(p.birth_assertions)]);
    bestOf(p.death_assertions) && out.push(['Died', bestOf(p.death_assertions)]);
    (p.occupation_assertions || []).forEach(o => out.push(['Occupation', o, true]));
    (p.event_assertions || []).forEach(e => out.push([e.event_type[0].toUpperCase() + e.event_type.slice(1).replace(/_/g,' '), e]));
    return out;
  }

  render() {
    const p = this.person;
    if (!p) return html`<div class="panel">Loading…</div>`;
    const name = bestOf(p.name_assertions);
    const birth = bestOf(p.birth_assertions);
    const death = bestOf(p.death_assertions);
    const dateStr = [formatDate(birth), formatDate(death)].filter(Boolean).join(' – ');
    const placeStr = birth?.place_as_written || '';
    const father = (p.parent_assertions || []).find(a => a.parent_role === 'father');
    const mother = (p.parent_assertions || []).find(a => a.parent_role === 'mother');
    const conf = (typeof p.composite_confidence === 'number') ? p.composite_confidence : name?.confidence;

    return html`
      <div class="hero">
        <maxgen-photo .person=${p} size="xl"></maxgen-photo>
        <div>
          <div class="name">${name?.name_as_written || 'Unknown'}</div>
          ${dateStr ? html`<div class="dates">${dateStr}</div>` : ''}
          ${placeStr ? html`<div class="place">${placeStr}</div>` : ''}
          <div class="parents-line">
            ${father ? html`<span class="pname">Father:</span> ${father.parent_name || father.parent_person_id}` : ''}
            ${father && mother ? ' · ' : ''}
            ${mother ? html`<span class="pname">Mother:</span> ${mother.parent_name || mother.parent_person_id}` : ''}
            ${!father && !mother ? html`<span style="color:var(--muted)">Parents unknown — see Family tab</span>` : ''}
          </div>
          ${conf != null ? html`<maxgen-confidence-chip .confidence=${conf}></maxgen-confidence-chip>` : ''}
        </div>
        <div class="pad-actions">
          <maxgen-external-search .person=${p}></maxgen-external-search>
        </div>
      </div>

      <div class="tabs" role="tablist">
        ${TABS.map(t => html`
          <button class="tab ${this.activeTab === t.key ? 'active' : ''}"
                  role="tab"
                  aria-selected="${this.activeTab === t.key}"
                  @click=${() => this._set(t.key)}>
            ${t.label}
          </button>`)}
      </div>

      <div class="panel" role="tabpanel">
        ${this._renderPanel()}
      </div>
    `;
  }

  _renderPanel() {
    if (this.activeTab === 'facts')   return this._panelFacts();
    if (this.activeTab === 'family')  return this._panelFamily();
    if (this.activeTab === 'photos')  return this._panelPhotos();
    if (this.activeTab === 'dna')     return this._panelDna();
    if (this.activeTab === 'sources') return this._panelSources();
    return html`<p>Unknown tab.</p>`;
  }

  _panelFacts() {
    const facts = this._facts();
    if (!facts.length) {
      return html`<maxgen-empty message="No facts recorded yet." cta="Add a birth, death, or other event" href="#"></maxgen-empty>`;
    }
    return html`
      <h3 class="section-h">Facts</h3>
      ${facts.map(([label, a, isOcc]) => html`
        <maxgen-fact
          label="${label}"
          value="${(isOcc ? a.occupation_as_written : formatDate(a))}${a.place_as_written ? ' · ' + a.place_as_written : ''}"
          .confidence=${a.confidence}
          .sources=${a.source_record_id ? [{label:'Record', url:`/record/${a.source_record_id}`, kind:'other'}] : []}>
        </maxgen-fact>
      `)}
    `;
  }

  _panelFamily() {
    const fam = this.family || {};
    const father = fam.father, mother = fam.mother;
    const spouses = fam.spouses || [];
    const children = fam.children || [];
    return html`
      <div class="section">
        <h3 class="section-h">Parents</h3>
        ${(father || mother) ? html`
          <div class="family-grid">
            ${father ? html`<maxgen-person-card .person=${father} size="compact"></maxgen-person-card>` : ''}
            ${mother ? html`<maxgen-person-card .person=${mother} size="compact"></maxgen-person-card>` : ''}
          </div>` : html`<div class="empty-row">Parents unknown.</div>`}
      </div>
      <div class="section">
        <h3 class="section-h">Spouses</h3>
        ${spouses.length ? html`
          <div class="family-grid">
            ${spouses.map(s => html`<maxgen-person-card .person=${s} size="compact"></maxgen-person-card>`)}
          </div>` : html`<div class="empty-row">No spouse recorded.</div>`}
      </div>
      <div class="section">
        <h3 class="section-h">Children (${children.length})</h3>
        ${children.length ? html`
          <div class="family-grid">
            ${children.map(c => html`<maxgen-person-card .person=${c} size="compact"></maxgen-person-card>`)}
          </div>` : html`<div class="empty-row">No children recorded.</div>`}
      </div>
    `;
  }

  _panelPhotos() {
    const photos = this.person.photo_assertions || [];
    if (!photos.length) {
      return html`<maxgen-empty message="No photos of this person yet." cta="Add a photo" href="#"></maxgen-empty>`;
    }
    return html`
      <h3 class="section-h">Photos (${photos.length})</h3>
      <div class="photo-grid">
        ${photos.map(p => html`
          <figure>
            <img src="${p.thumbnail_url || p.url}" alt="${p.alt_text || 'Photo'}"
                 style="width:100%; aspect-ratio:1; object-fit:cover; border-radius:var(--radius);">
            ${p.caption ? html`<figcaption>${p.caption}</figcaption>` : ''}
          </figure>
        `)}
      </div>
    `;
  }

  _panelDna() {
    const dna = this.person.dna_evidence || [];
    if (!dna.length) {
      return html`<maxgen-empty message="No DNA evidence linked to this person yet." cta="See DNA tools" href="/dna"></maxgen-empty>`;
    }
    return html`
      <h3 class="section-h">DNA evidence chains (${dna.length})</h3>
      ${dna.map(d => html`
        <maxgen-fact label="DNA chain"
          value="${d.shared_cm} cM across ${d.path_length_generations} generations"
          .confidence=${d.likelihood}>
        </maxgen-fact>
      `)}
    `;
  }

  _panelSources() {
    const ids = this.person.source_record_ids || [];
    if (!ids.length) {
      return html`<maxgen-empty message="No sources cited yet." cta="Cite a record" href="#"></maxgen-empty>`;
    }
    return html`
      <h3 class="section-h">Source records (${ids.length})</h3>
      <ul class="bare">
        ${ids.map(id => html`<li style="padding:6px 0"><maxgen-source-chip label="Record ${id.slice(0,8)}" url="/record/${id}"></maxgen-source-chip></li>`)}
      </ul>
    `;
  }
}
defineOnce('maxgen-person-profile', MaxgenPersonProfile);
