// <maxgen-family-group-sheet>
// The classic family group sheet: husband + wife + children, every fact with
// confidence + sources. Garlon's mom used these; this is the proving ground
// for the whole design system.

import { html, css } from 'https://esm.sh/lit@3';
import { MaxgenElement, defineOnce, bestOf, formatDate } from './_base.js';

class MaxgenFamilyGroupSheet extends MaxgenElement {
  static properties = {
    family: { type: Object },  // {husband, wife, marriage, children:[]}
  };
  constructor() { super(); this.family = null; }
  static styles = [MaxgenElement.styles, css`
    :host { display: block; max-width: 920px; margin: 0 auto; }

    .sheet {
      background: var(--paper, #f7f4ee);
      border: 1px solid var(--border, #ddd8cc);
      border-radius: var(--radius-lg, 12px);
      padding: 24px;
      box-shadow: var(--shadow-card);
      font-family: var(--font-body);
    }
    h1.title {
      font-family: var(--font-body);
      font-size: var(--text-lg);
      letter-spacing: 0.04em;
      text-align: center;
      margin: 0 0 4px 0;
      color: var(--ink);
    }
    .subtitle {
      font-family: var(--font-ui);
      font-size: var(--text-xs);
      text-align: center;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.1em;
      margin-bottom: 24px;
    }

    .couple {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 24px;
      margin-bottom: 24px;
    }
    @media (max-width: 720px) {
      .couple { grid-template-columns: 1fr; }
    }
    .person-block {
      background: white;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 16px;
    }
    .role {
      font-family: var(--font-ui);
      font-size: var(--text-xs);
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: var(--gold-dark);
      margin-bottom: 8px;
    }
    .person-header {
      display: flex; gap: 12px; align-items: center;
      margin-bottom: 12px;
    }
    .person-name {
      font-family: var(--font-body);
      font-size: var(--text-md);
      font-weight: bold;
      color: var(--ink);
    }
    .person-dates {
      font-family: var(--font-ui);
      font-size: var(--text-sm);
      color: var(--muted);
      font-variant-numeric: tabular-nums;
    }
    .facts { display: flex; flex-direction: column; }

    .marriage {
      grid-column: 1 / -1;
      margin-top: 8px;
      padding: 12px 16px;
      background: rgba(212, 168, 67, 0.08);
      border-left: 3px solid var(--gold);
      border-radius: var(--radius);
      font-family: var(--font-ui);
      font-size: var(--text-sm);
      color: var(--ink);
    }
    .marriage-label {
      text-transform: uppercase;
      letter-spacing: 0.1em;
      font-size: var(--text-xs);
      color: var(--gold-dark);
      margin-right: 8px;
    }

    .children {
      background: white;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 16px;
    }
    .children-header {
      font-family: var(--font-ui);
      font-size: var(--text-xs);
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: var(--gold-dark);
      margin-bottom: 12px;
      display: flex; justify-content: space-between; align-items: baseline;
    }
    .children-count {
      color: var(--muted);
      font-weight: normal;
    }
    ol.child-list {
      list-style: none; padding: 0; margin: 0;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 8px;
    }
    li.child {
      display: flex; align-items: center; gap: 10px;
      padding: 8px;
      border-radius: var(--radius);
      transition: background var(--dur-fast) var(--ease-out);
    }
    li.child:hover { background: var(--paper); }
    .child-num {
      font-family: var(--font-mono);
      font-size: var(--text-xs);
      color: var(--muted);
      min-width: 22px;
      text-align: right;
    }
    .child-body { flex: 1; min-width: 0; }
    .child-name {
      font-family: var(--font-body);
      font-weight: bold;
      font-size: var(--text-base);
      color: var(--ink);
    }
    .child-dates {
      font-family: var(--font-ui);
      font-size: var(--text-xs);
      color: var(--muted);
      font-variant-numeric: tabular-nums;
    }
  `];

  _personBlock(person, role) {
    if (!person) {
      return html`
        <div class="person-block">
          <div class="role">${role}</div>
          <div class="facts">
            <maxgen-empty message="${role} not yet identified." cta="Add ${role.toLowerCase()}" href="#"></maxgen-empty>
          </div>
        </div>
      `;
    }
    const name = bestOf(person.name_assertions);
    const birth = bestOf(person.birth_assertions);
    const death = bestOf(person.death_assertions);
    const dateStr = [formatDate(birth), formatDate(death)].filter(Boolean).join(' – ');

    const buildSources = (a) => {
      // The fixture format doesn't have explicit source URLs in our demo
      // payload; if a source_record_id exists, render a chip pointing to its
      // record page (placeholder).
      return a?.source_record_id
        ? [{ label: 'Record', url: `/record/${a.source_record_id}`, kind: 'other' }]
        : [];
    };

    return html`
      <div class="person-block">
        <div class="role">${role}</div>
        <div class="person-header">
          <maxgen-photo .person=${person} size="md"></maxgen-photo>
          <div>
            <div class="person-name">${name?.name_as_written || 'Unknown'}</div>
            <div class="person-dates">${dateStr}</div>
          </div>
        </div>
        <div class="facts">
          ${birth ? html`
            <maxgen-fact
              label="Born"
              value="${formatDate(birth)}${birth.place_as_written ? ', ' + birth.place_as_written : ''}"
              .confidence=${birth.confidence}
              .sources=${buildSources(birth)}>
            </maxgen-fact>` : ''}
          ${death ? html`
            <maxgen-fact
              label="Died"
              value="${formatDate(death)}${death.place_as_written ? ', ' + death.place_as_written : ''}"
              .confidence=${death.confidence}
              .sources=${buildSources(death)}>
            </maxgen-fact>` : ''}
          ${person.parent_assertions?.length ? person.parent_assertions.map(p => html`
            <maxgen-fact
              label="${p.parent_role === 'father' ? 'Father' : (p.parent_role === 'mother' ? 'Mother' : 'Parent')}"
              value="${p.parent_name || p.parent_person_id || 'Unknown'}"
              .confidence=${p.confidence}
              .sources=${buildSources(p)}>
            </maxgen-fact>
          `) : ''}
        </div>
      </div>
    `;
  }

  render() {
    if (!this.family) return html`<div class="sheet">No family data.</div>`;
    const f = this.family;
    const husband = f.husband;
    const wife    = f.wife;
    const children = f.children || [];

    // Couple name for the title
    const hName = husband ? bestOf(husband.name_assertions)?.name_as_written : null;
    const wName = wife ?    bestOf(wife.name_assertions)?.name_as_written : null;
    const title = [hName, wName].filter(Boolean).join(' & ') || 'Family Group Sheet';

    return html`
      <div class="sheet">
        <h1 class="title">${title}</h1>
        <div class="subtitle">Family Group Sheet</div>

        <div class="couple">
          ${this._personBlock(husband, 'Husband')}
          ${this._personBlock(wife, 'Wife')}
          ${f.marriage ? html`
            <div class="marriage">
              <span class="marriage-label">Married</span>
              ${formatDate(f.marriage)}${f.marriage.place_as_written ? ' • ' + f.marriage.place_as_written : ''}
              ${f.marriage.confidence != null
                ? html`<maxgen-confidence-chip compact .confidence=${f.marriage.confidence} style="margin-left:8px"></maxgen-confidence-chip>`
                : ''}
            </div>
          ` : ''}
        </div>

        <div class="children">
          <div class="children-header">
            <span>Children</span>
            <span class="children-count">${children.length} known</span>
          </div>
          ${children.length === 0
            ? html`<maxgen-empty message="No children recorded yet." cta="Add a child" href="#"></maxgen-empty>`
            : html`
              <ol class="child-list">
                ${children.map((c, i) => {
                  const cn = bestOf(c.name_assertions);
                  const cb = bestOf(c.birth_assertions);
                  const cd = bestOf(c.death_assertions);
                  const cdates = [formatDate(cb), formatDate(cd)].filter(Boolean).join(' – ');
                  return html`
                    <li class="child">
                      <span class="child-num">${i+1}.</span>
                      <maxgen-photo .person=${c} size="sm"></maxgen-photo>
                      <div class="child-body">
                        <div class="child-name">${cn?.name_as_written || 'Unknown'}</div>
                        ${cdates ? html`<div class="child-dates">${cdates}</div>` : ''}
                      </div>
                      ${cn?.confidence != null
                        ? html`<maxgen-confidence-chip compact .confidence=${cn.confidence}></maxgen-confidence-chip>`
                        : ''}
                    </li>
                  `;
                })}
              </ol>
            `}
        </div>
      </div>
    `;
  }
}
defineOnce('maxgen-family-group-sheet', MaxgenFamilyGroupSheet);
