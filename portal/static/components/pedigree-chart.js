// <maxgen-pedigree-chart>
// Subject left, ancestors branch right. 4-5 generations visible.
// Uncertain ancestors render the possibility-expander inline.
// Pan + zoom canvas.

import { html, css, svg } from 'https://esm.sh/lit@3';
import { MaxgenElement, defineOnce, bestOf, formatDate } from './_base.js';

class MaxgenPedigreeChart extends MaxgenElement {
  static properties = {
    // Pedigree as a recursive structure:
    // {person, father?, mother?, fatherPossibilities?, motherPossibilities?}
    pedigree:    { type: Object },
    generations: { type: Number },  // depth to render (default 4)
  };

  constructor() {
    super();
    this.pedigree = null;
    this.generations = 4;
    this._zoom = 1;
    this._pan = { x: 0, y: 0 };
    this._dragging = false;
    this._dragStart = null;
  }

  static styles = [MaxgenElement.styles, css`
    :host { display: block; }
    .chart {
      position: relative;
      width: 100%;
      height: 600px;
      background: var(--paper, #f7f4ee);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      overflow: hidden;
      box-shadow: var(--shadow-card);
      user-select: none;
      cursor: grab;
    }
    .chart.dragging { cursor: grabbing; }
    .canvas {
      position: absolute; top: 0; left: 0;
      transform-origin: 0 0;
      will-change: transform;
    }
    .node {
      position: absolute;
      background: white;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 6px 10px;
      box-shadow: var(--shadow-card);
      display: flex;
      align-items: center;
      gap: 8px;
      width: 220px;
      box-sizing: border-box;
      transition: box-shadow var(--dur-fast) var(--ease-out);
    }
    .node:hover { box-shadow: var(--shadow-pop); }
    .node.uncertain {
      background: rgba(212, 168, 67, 0.06);
      border-style: dashed;
      border-color: var(--gold-dark);
    }
    .node .nbody { min-width: 0; flex: 1; }
    .node .nname {
      font-family: var(--font-body);
      font-weight: bold;
      font-size: var(--text-sm);
      color: var(--ink);
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .node .ndates {
      font-family: var(--font-ui);
      font-size: var(--text-xs);
      color: var(--muted);
      font-variant-numeric: tabular-nums;
    }
    .node a { text-decoration: none; color: inherit; }

    .edges { position: absolute; top: 0; left: 0; pointer-events: none; }

    .toolbar {
      position: absolute; right: 12px; top: 12px;
      display: flex; gap: 6px;
      background: white;
      border: 1px solid var(--border);
      border-radius: var(--radius-pill);
      padding: 4px;
      box-shadow: var(--shadow-card);
      z-index: 10;
    }
    .toolbar button {
      background: transparent;
      border: none;
      padding: 4px 10px;
      cursor: pointer;
      font-family: var(--font-ui);
      font-size: var(--text-sm);
      color: var(--ink);
      border-radius: var(--radius-pill);
    }
    .toolbar button:hover { background: var(--paper); }

    .legend {
      position: absolute; left: 12px; bottom: 12px;
      background: white;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 6px 10px;
      font-family: var(--font-ui);
      font-size: var(--text-xs);
      color: var(--muted);
      box-shadow: var(--shadow-card);
      z-index: 10;
    }
  `];

  // ── Layout algorithm ────────────────────────────────────────────────
  // We render N generations. Generation 0 = subject (1 node).
  // Generation k has 2^k slots. Total nodes = 2^N - 1.
  // For 4 generations: 1 + 2 + 4 + 8 = 15 nodes.

  _layout() {
    const gens = this.generations || 4;
    const nodes = [];   // {x, y, person, isPossibility, gen, slot}
    const edges = [];   // {x1, y1, x2, y2}

    const nodeWidth = 220;
    const nodeHeight = 56;
    const xGap = 60;
    const yGap = 18;

    const xPerGen = nodeWidth + xGap;
    const totalSlots = Math.pow(2, gens - 1);
    const yPerSlot = nodeHeight + yGap;
    const totalHeight = totalSlots * yPerSlot;

    // Recursive walk — depth-first, computes y as midpoint of subtree
    const walk = (pedNode, gen, ySlotStart, ySlotEnd) => {
      const slotMid = (ySlotStart + ySlotEnd) / 2;
      const x = gen * xPerGen + 20;
      const y = slotMid * yPerSlot;

      const person = pedNode?.person;
      const possibilities = gen > 0 && !person
        ? (pedNode?.parentSide === 'father' ? pedNode?.parentPossibilities : pedNode?.parentPossibilities)
        : null;

      const node = { x, y, person, possibilities, gen };
      nodes.push(node);

      if (gen < gens - 1) {
        const half = (ySlotEnd - ySlotStart) / 2;
        const fatherSubtree = pedNode?.father;
        const motherSubtree = pedNode?.mother;

        // Father (top half)
        const fEnd = ySlotStart + half;
        const fNode = walk(
          fatherSubtree || (pedNode?.fatherPossibilities ? { parentPossibilities: pedNode.fatherPossibilities, parentSide: 'father' } : {}),
          gen + 1, ySlotStart, fEnd
        );
        edges.push({ x1: x + nodeWidth, y1: y + nodeHeight/2, x2: fNode.x, y2: fNode.y + nodeHeight/2 });

        // Mother (bottom half)
        const mStart = ySlotStart + half;
        const mNode = walk(
          motherSubtree || (pedNode?.motherPossibilities ? { parentPossibilities: pedNode.motherPossibilities, parentSide: 'mother' } : {}),
          gen + 1, mStart, ySlotEnd
        );
        edges.push({ x1: x + nodeWidth, y1: y + nodeHeight/2, x2: mNode.x, y2: mNode.y + nodeHeight/2 });
      }
      return node;
    };

    if (this.pedigree) {
      walk(this.pedigree, 0, 0, totalSlots);
    }

    const totalWidth = gens * xPerGen + 20;
    return { nodes, edges, totalWidth, totalHeight, nodeWidth, nodeHeight };
  }

  _renderNode(n, nodeWidth, nodeHeight) {
    const person = n.person;
    const style = `left:${n.x}px; top:${n.y}px; width:${nodeWidth}px; height:${nodeHeight}px;`;

    if (person) {
      const name = bestOf(person.name_assertions)?.name_as_written || 'Unknown';
      const birth = bestOf(person.birth_assertions);
      const death = bestOf(person.death_assertions);
      const dates = [formatDate(birth), formatDate(death)].filter(Boolean).join(' – ');
      const conf = person.composite_confidence || bestOf(person.name_assertions)?.confidence;
      const href = person.person_id ? `/dev/person?id=${person.person_id}` : '#';
      return html`
        <div class="node" style="${style}">
          <maxgen-photo .person=${person} size="sm"></maxgen-photo>
          <div class="nbody">
            <a href="${href}"><div class="nname">${name}</div></a>
            <div class="ndates">${dates}</div>
          </div>
          ${conf != null ? html`<maxgen-confidence-chip compact .confidence=${conf}></maxgen-confidence-chip>` : ''}
        </div>
      `;
    }

    // Possibility node — unknown ancestor
    const possibilities = n.possibilities;
    if (possibilities && possibilities.length) {
      return html`
        <div class="node uncertain" style="${style}">
          <div class="nbody" style="text-align:left;">
            <maxgen-possibility-expander
              label="Unknown"
              .candidates=${possibilities}
              compact>
            </maxgen-possibility-expander>
          </div>
        </div>
      `;
    }

    // Truly empty slot
    return html`
      <div class="node uncertain" style="${style}; opacity: 0.5; text-align:center;">
        <div class="nbody"><div class="ndates">Unknown</div></div>
      </div>
    `;
  }

  _renderEdges(edges) {
    return svg`
      ${edges.map(e => svg`
        <path
          d="M${e.x1},${e.y1} C${e.x1 + 30},${e.y1} ${e.x2 - 30},${e.y2} ${e.x2},${e.y2}"
          stroke="var(--gold-dark)"
          stroke-width="1.5"
          fill="none"
          opacity="0.5"/>
      `)}
    `;
  }

  // ── Pan + zoom handlers ─────────────────────────────────────────────
  _onPointerDown(e) {
    this._dragging = true;
    this._dragStart = { x: e.clientX - this._pan.x, y: e.clientY - this._pan.y };
    this.requestUpdate();
  }
  _onPointerMove(e) {
    if (!this._dragging) return;
    this._pan = { x: e.clientX - this._dragStart.x, y: e.clientY - this._dragStart.y };
    this.requestUpdate();
  }
  _onPointerUp() { this._dragging = false; this.requestUpdate(); }
  _zoomIn() { this._zoom = Math.min(2, this._zoom + 0.1); this.requestUpdate(); }
  _zoomOut() { this._zoom = Math.max(0.4, this._zoom - 0.1); this.requestUpdate(); }
  _reset() { this._zoom = 1; this._pan = { x: 0, y: 0 }; this.requestUpdate(); }

  render() {
    const layout = this._layout();
    const transform = `translate(${this._pan.x}px, ${this._pan.y}px) scale(${this._zoom})`;
    return html`
      <div class="chart ${this._dragging ? 'dragging' : ''}"
           @pointerdown=${this._onPointerDown}
           @pointermove=${this._onPointerMove}
           @pointerup=${this._onPointerUp}
           @pointerleave=${this._onPointerUp}>
        <div class="toolbar">
          <button @click=${this._zoomOut} aria-label="Zoom out">−</button>
          <button @click=${this._reset} aria-label="Reset view">⊙</button>
          <button @click=${this._zoomIn} aria-label="Zoom in">+</button>
        </div>
        <div class="canvas"
             style="transform:${transform}; width:${layout.totalWidth}px; height:${layout.totalHeight}px;">
          <svg class="edges"
               width="${layout.totalWidth}"
               height="${layout.totalHeight}"
               viewBox="0 0 ${layout.totalWidth} ${layout.totalHeight}">
            ${this._renderEdges(layout.edges)}
          </svg>
          ${layout.nodes.map(n => this._renderNode(n, layout.nodeWidth, layout.nodeHeight))}
        </div>
        <div class="legend">
          Drag to pan · buttons to zoom · click name to open profile
        </div>
      </div>
    `;
  }
}
defineOnce('maxgen-pedigree-chart', MaxgenPedigreeChart);
