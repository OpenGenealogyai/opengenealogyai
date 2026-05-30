// <maxgen-relationship-calc>
// "How is X related to Y?" Walks the pedigree to find a common ancestor and
// labels the relationship — composing confidence along the path (noisy-AND:
// confidence(path) = product of edge confidences). This is the probabilistic
// equivalent of Ancestry's relationship calculator: not just the relation
// label, but how confident we are.

import { html, css } from 'https://esm.sh/lit@3';
import { MaxgenElement, defineOnce, bestOf, pct, bandFor } from './_base.js';

// Standard genealogical relationship table from ancestor distances.
// dA = generations from person A up to common ancestor.
// dB = generations from person B up to common ancestor.
// Returns a human-readable label.
function labelFor(dA, dB) {
  // Convention: returns label such that "A is the <label> of B"
  // dA = generations from A UP to common ancestor (MRCA)
  // dB = generations from B UP to common ancestor (MRCA)
  if (dA === 0 && dB === 0) return 'the same person';
  // A is the MRCA → B is below A → A is B's ancestor (the labeled relation)
  if (dA === 0) return ancestorLabel(dB);
  // B is the MRCA → A is below B → A is B's descendant
  if (dB === 0) return descendantLabel(dA);
  // Sibling / nibling / pibling / cousin
  if (dA === 1 && dB === 1) return 'sibling';
  const minD = Math.min(dA, dB);
  const removal = Math.abs(dA - dB);
  if (minD === 1 && removal > 0) {
    // aunt/uncle / niece/nephew patterns
    const niblingPibling = (removal === 1) ? 'aunt/uncle' : `${ordinal(removal - 1)}-great aunt/uncle`;
    return (dA < dB) ? niblingPibling : niblingPibling.replace('aunt/uncle', 'niece/nephew');
  }
  // Cousin formula: nth cousin where n = minD - 1; removal R = |dA - dB|
  const n = minD - 1;
  const nLabel = (n === 1) ? 'first' : (n === 2) ? 'second' : (n === 3) ? 'third'
              : (n === 4) ? 'fourth' : (n === 5) ? 'fifth'
              : `${ordinal(n)}`;
  if (removal === 0) return `${nLabel} cousin`;
  const r = (removal === 1) ? 'once' : (removal === 2) ? 'twice' : `${removal} times`;
  return `${nLabel} cousin ${r} removed`;
}

function ancestorLabel(d) {
  if (d === 1) return 'parent';
  if (d === 2) return 'grandparent';
  if (d === 3) return 'great-grandparent';
  if (d === 4) return 'great-great-grandparent';
  // "Nth-great-grandparent" for d >= 5
  const greats = d - 2;
  return `${ordinal(greats - 1)}-great-grandparent`;
}

function descendantLabel(d) {
  if (d === 1) return 'child';
  if (d === 2) return 'grandchild';
  if (d === 3) return 'great-grandchild';
  if (d === 4) return 'great-great-grandchild';
  const greats = d - 2;
  return `${ordinal(greats - 1)}-great-grandchild`;
}

function ordinal(n) {
  const map = {1:'1st',2:'2nd',3:'3rd'};
  if (map[n]) return map[n];
  return `${n}th`;
}

class MaxgenRelationshipCalc extends MaxgenElement {
  static properties = {
    // pedigree: same shape as <maxgen-pedigree-chart>
    pedigree:  { type: Object },
    personA:   { type: String },  // person_id
    personB:   { type: String },  // person_id
  };
  constructor() { super(); this.pedigree = null; this.personA = ''; this.personB = ''; }

  static styles = [MaxgenElement.styles, css`
    :host { display: block; }
    .panel {
      background: white;
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 20px;
      box-shadow: var(--shadow-card);
    }
    h3 { margin: 0 0 12px; font-family: var(--font-body); font-size: var(--text-md); }
    .pickers {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      margin-bottom: 16px;
    }
    label { font-family: var(--font-ui); font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted); display: block; margin-bottom: 4px; }
    select {
      width: 100%;
      padding: 6px 10px;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      background: var(--paper);
      font-family: var(--font-ui);
      font-size: var(--text-sm);
      color: var(--ink);
    }
    .result {
      padding: 16px;
      background: var(--paper);
      border-radius: var(--radius);
      border-left: 4px solid var(--gold);
    }
    .verdict {
      font-family: var(--font-body);
      font-size: var(--text-lg);
      color: var(--ink);
      margin-bottom: 6px;
    }
    .verdict .rel { color: var(--gold-dark); font-weight: bold; }
    .pathline {
      font-family: var(--font-ui);
      font-size: var(--text-sm);
      color: var(--muted);
      margin: 6px 0;
    }
    .mrca {
      font-family: var(--font-ui);
      font-size: var(--text-sm);
      color: var(--ink);
      margin-top: 8px;
    }
    .mrca .name { font-weight: 600; font-family: var(--font-body); }
    ol.path { list-style: none; padding: 0; margin: 8px 0 0; font-family: var(--font-mono); font-size: var(--text-xs); color: var(--muted); }
    ol.path li { padding: 2px 0; }
    .none {
      color: var(--muted);
      font-style: italic;
      font-family: var(--font-ui);
      font-size: var(--text-sm);
    }
  `];

  // Flatten the pedigree into {person_id -> {person, parents:[{id, conf}]}}
  _flatten() {
    const map = {};
    const walk = (ped) => {
      if (!ped?.person) return;
      const p = ped.person;
      map[p.person_id] = map[p.person_id] || { person: p, parents: [] };
      if (ped.father?.person) {
        map[p.person_id].parents.push({ id: ped.father.person.person_id, conf: 0.9, role: 'father' });
        walk(ped.father);
      }
      if (ped.mother?.person) {
        map[p.person_id].parents.push({ id: ped.mother.person.person_id, conf: 0.9, role: 'mother' });
        walk(ped.mother);
      }
    };
    walk(this.pedigree);
    return map;
  }

  // Ancestors of a person — BFS up the tree, returns Map<id, {generations, pathConfidence, path}>
  _ancestors(start, map) {
    const out = new Map();
    out.set(start, { gen: 0, conf: 1.0, path: [start] });
    const queue = [start];
    while (queue.length) {
      const cur = queue.shift();
      const node = out.get(cur);
      const entry = map[cur];
      if (!entry) continue;
      for (const p of entry.parents) {
        if (out.has(p.id)) continue;
        out.set(p.id, {
          gen: node.gen + 1,
          conf: node.conf * (p.conf ?? 0.9),
          path: [...node.path, p.id]
        });
        queue.push(p.id);
      }
    }
    return out;
  }

  _calc() {
    if (!this.personA || !this.personB || !this.pedigree) return null;
    const map = this._flatten();
    const aA = this._ancestors(this.personA, map);
    const aB = this._ancestors(this.personB, map);

    // Find shared ancestors, pick the one with smallest combined generations
    let best = null;
    aA.forEach((v, id) => {
      if (aB.has(id)) {
        const other = aB.get(id);
        const score = v.gen + other.gen;
        const combined = v.conf * other.conf;
        if (!best || score < best.score || (score === best.score && combined > best.confidence)) {
          best = { mrcaId: id, dA: v.gen, dB: other.gen, score, pathA: v.path, pathB: other.path, confidence: combined };
        }
      }
    });
    if (!best) return null;
    const mrcaPerson = map[best.mrcaId]?.person;
    const aPerson = map[this.personA]?.person;
    const bPerson = map[this.personB]?.person;
    return { ...best, mrcaPerson, aPerson, bPerson };
  }

  _people() {
    // Flatten pedigree to a sorted list for the dropdowns
    const map = this._flatten();
    return Object.values(map)
      .map(e => ({
        id: e.person.person_id,
        name: bestOf(e.person.name_assertions)?.name_as_written || e.person.person_id,
        birth: bestOf(e.person.birth_assertions)?.year_min
      }))
      .sort((a, b) => (a.birth || 9999) - (b.birth || 9999));
  }

  render() {
    const people = this._people();
    const result = this._calc();

    return html`
      <div class="panel">
        <h3>How are these two people related?</h3>
        <div class="pickers">
          <div>
            <label for="a">Person A</label>
            <select id="a" @change=${(e) => { this.personA = e.target.value; this.requestUpdate(); }}>
              <option value="">Choose a person…</option>
              ${people.map(p => html`<option value="${p.id}" ?selected=${this.personA === p.id}>${p.name}${p.birth ? ` (${p.birth})` : ''}</option>`)}
            </select>
          </div>
          <div>
            <label for="b">Person B</label>
            <select id="b" @change=${(e) => { this.personB = e.target.value; this.requestUpdate(); }}>
              <option value="">Choose a person…</option>
              ${people.map(p => html`<option value="${p.id}" ?selected=${this.personB === p.id}>${p.name}${p.birth ? ` (${p.birth})` : ''}</option>`)}
            </select>
          </div>
        </div>

        ${(!this.personA || !this.personB) ? html`
          <div class="result none">Pick two people to compute their relationship.</div>
        ` : result ? html`
          <div class="result">
            <div class="verdict">
              <strong>${bestOf(result.aPerson?.name_assertions)?.name_as_written}</strong>
              is the
              <span class="rel">${labelFor(result.dA, result.dB)}</span>
              of
              <strong>${bestOf(result.bPerson?.name_assertions)?.name_as_written}</strong>.
            </div>
            <div class="pathline">
              Distance: ${result.dA} generation${result.dA === 1 ? '' : 's'} up from A,
              ${result.dB} generation${result.dB === 1 ? '' : 's'} up from B.
            </div>
            <div class="mrca">
              Most-recent common ancestor:
              <span class="name">${bestOf(result.mrcaPerson?.name_assertions)?.name_as_written}</span>
            </div>
            <div style="margin-top:10px; display:flex; align-items:center; gap:8px; font-family:var(--font-ui); font-size: var(--text-sm);">
              Confidence in this relationship:
              <maxgen-confidence-chip .confidence=${result.confidence}></maxgen-confidence-chip>
              <span style="color:var(--muted)">
                = ${result.pathA.length - 1} parent-edges × ${result.pathB.length - 1} parent-edges, multiplied
              </span>
            </div>
          </div>
        ` : html`
          <div class="result none">No common ancestor found in the loaded pedigree.</div>
        `}
      </div>
    `;
  }
}
defineOnce('maxgen-relationship-calc', MaxgenRelationshipCalc);
