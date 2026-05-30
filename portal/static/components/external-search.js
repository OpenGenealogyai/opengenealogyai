// <maxgen-external-search>
// Garlon's one-click fan-out to FamilySearch / Ancestry / WikiTree / FAG / etc.
// Design-only copy of Gramps Web's external-search trick (template URLs, free).

import { html, css } from 'https://esm.sh/lit@3';
import { MaxgenElement, defineOnce, bestOf } from './_base.js';

const SITES = [
  { key: 'familysearch', label: 'FamilySearch',
    url: ({given,sur,by,dy}) => `https://www.familysearch.org/search/record/results?q.givenName=${encodeURIComponent(given||'')}&q.surname=${encodeURIComponent(sur||'')}${by?`&q.birthLikeDate.from=${by-2}&q.birthLikeDate.to=${by+2}`:''}` },
  { key: 'ancestry', label: 'Ancestry',
    url: ({given,sur,by}) => `https://www.ancestry.com/search/?name=${encodeURIComponent((given||'')+' '+(sur||''))}${by?`&birth=${by}`:''}` },
  { key: 'wikitree', label: 'WikiTree',
    url: ({given,sur,by}) => `https://www.wikitree.com/genealogy/${encodeURIComponent(sur||'')}-Family-Tree?formality=both&first=${encodeURIComponent(given||'')}${by?`&birth_year=${by}`:''}` },
  { key: 'findagrave', label: 'Find A Grave',
    url: ({given,sur,by,dy}) => `https://www.findagrave.com/memorial/search?firstname=${encodeURIComponent(given||'')}&lastname=${encodeURIComponent(sur||'')}${by?`&birthyear=${by}&birthyearfilter=5`:''}${dy?`&deathyear=${dy}&deathyearfilter=5`:''}` },
  { key: 'myheritage', label: 'MyHeritage',
    url: ({given,sur,by}) => `https://www.myheritage.com/research/?formId=master&formMode=1&action=query&qname=Name+fn.${encodeURIComponent(given||'')}+ln.${encodeURIComponent(sur||'')}${by?`+exact.false&qbirth=year.${by}`:''}` },
  { key: 'geneanet', label: 'Geneanet',
    url: ({given,sur}) => `https://en.geneanet.org/fonds/individus/?prenom=${encodeURIComponent(given||'')}&nom=${encodeURIComponent(sur||'')}` },
  { key: 'newspapers', label: 'Newspapers.com',
    url: ({given,sur,by,dy}) => `https://www.newspapers.com/search/results/?query=${encodeURIComponent((given||'')+' '+(sur||''))}${by?`&dr_year=${by}-${dy||by+90}`:''}` },
];

class MaxgenExternalSearch extends MaxgenElement {
  static properties = {
    person: { type: Object },
    open:   { type: Boolean },
  };
  constructor() { super(); this.person = null; this.open = false; }

  static styles = [MaxgenElement.styles, css`
    :host { display: inline-block; position: relative; }
    button.trigger {
      display: inline-flex; align-items: center; gap: 6px;
      padding: 6px 14px;
      background: white;
      border: 1px solid var(--border, #ddd8cc);
      border-radius: var(--radius-pill, 999px);
      font-family: var(--font-ui);
      font-size: var(--text-sm);
      color: var(--ink);
      cursor: pointer;
    }
    button.trigger:hover { border-color: var(--gold-dark); background: var(--paper); }
    .menu {
      position: absolute; right: 0; top: calc(100% + 6px);
      min-width: 240px;
      background: white;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow-pop);
      padding: 6px 0;
      z-index: 50;
      display: none;
    }
    .menu.open { display: block; }
    .menu a {
      display: flex; align-items: center; justify-content: space-between;
      padding: 8px 14px;
      color: var(--ink);
      text-decoration: none;
      font-family: var(--font-ui);
      font-size: var(--text-sm);
    }
    .menu a:hover { background: var(--paper); }
    .menu a .arrow { color: var(--muted); }
    .menu .header {
      padding: 6px 14px 8px;
      border-bottom: 1px solid var(--border);
      font-family: var(--font-ui); font-size: var(--text-xs);
      color: var(--muted); text-transform: uppercase; letter-spacing: 0.1em;
    }
  `];

  _params() {
    if (!this.person) return null;
    const name = bestOf(this.person.name_assertions);
    const birth = bestOf(this.person.birth_assertions);
    const death = bestOf(this.person.death_assertions);
    return {
      given: name?.given_name,
      sur: name?.surname,
      by: birth?.year_min,
      dy: death?.year_min,
    };
  }

  _toggle(e) { e?.stopPropagation(); this.open = !this.open; }

  connectedCallback() {
    super.connectedCallback();
    this._onDoc = (e) => { if (!this.contains(e.target)) this.open = false; };
    document.addEventListener('click', this._onDoc);
  }
  disconnectedCallback() {
    document.removeEventListener('click', this._onDoc);
    super.disconnectedCallback();
  }

  render() {
    const p = this._params();
    if (!p) return html`<button class="trigger" disabled>Search the web</button>`;
    return html`
      <button class="trigger" @click=${this._toggle} aria-expanded="${this.open}">
        Search the web ▾
      </button>
      <div class="menu ${this.open ? 'open' : ''}">
        <div class="header">Search 7 sites for this person</div>
        ${SITES.map(s => html`
          <a href="${s.url(p)}" target="_blank" rel="noopener noreferrer">
            <span>${s.label}</span><span class="arrow">↗</span>
          </a>
        `)}
      </div>
    `;
  }
}
defineOnce('maxgen-external-search', MaxgenExternalSearch);
