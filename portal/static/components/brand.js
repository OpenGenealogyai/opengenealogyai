// <maxgen-logo> + <maxgen-header>
// Brand identity made into reusable components.
// Brand spec: docs/brand.md
//
// Logo: serif "OpenGenealogyAI" wordmark with a gold confidence-arc curving
// over the O. The arc thickness varies along its length — thick where the
// confidence is high, thin where it tapers off — the standard's promise
// made visible.

import { html, css, svg } from 'https://esm.sh/lit@3';
import { MaxgenElement, defineOnce } from './_base.js';

class MaxgenLogo extends MaxgenElement {
  static properties = {
    variant: { type: String },   // 'horizontal' | 'compact' | 'mark-only'
    invert:  { type: Boolean },  // light text on dark
  };
  constructor() {
    super();
    this.variant = 'horizontal';
    this.invert = false;
  }
  static styles = [MaxgenElement.styles, css`
    :host { display: inline-block; line-height: 0; }
    .wrap {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      font-family: var(--font-body, Georgia, serif);
      color: var(--ink);
      text-decoration: none;
    }
    .wrap.invert { color: var(--paper); }
    .mark {
      flex-shrink: 0;
    }
    .wordmark {
      font-weight: bold;
      letter-spacing: 0.01em;
      line-height: 1.1;
    }
    .wordmark .name { display: block; font-size: 1.15rem; }
    .wordmark .tag {
      display: block;
      font-family: var(--font-ui);
      font-size: 0.68rem;
      font-weight: 600;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: var(--gold-dark);
      margin-top: 2px;
    }
    .invert .tag { color: var(--gold); }
    /* compact = mark + short name */
    .compact .wordmark .name { font-size: 1rem; }
    .compact .wordmark .tag { display: none; }
  `];

  _renderMark(sz = 36) {
    // The logo mark: a gold arc + a stylized O (the standard's "first ancestor" suggestion)
    const c = sz / 2;
    return svg`
      <svg class="mark" width="${sz}" height="${sz}" viewBox="0 0 36 36" aria-hidden="true">
        <defs>
          <linearGradient id="maxgenArc" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stop-color="#d4a843"/>
            <stop offset="55%" stop-color="#c19233"/>
            <stop offset="100%" stop-color="#a17822"/>
          </linearGradient>
        </defs>
        <!-- inner serif "O" suggestion -->
        <circle cx="18" cy="20" r="10"
                fill="none"
                stroke="${this.invert ? '#f7f4ee' : '#1a1209'}"
                stroke-width="2.2"/>
        <!-- the confidence-arc, thickness tapers along its length -->
        <path d="M 4 14 Q 18 -2 32 14"
              fill="none"
              stroke="url(#maxgenArc)"
              stroke-width="3.4"
              stroke-linecap="round"/>
        <!-- a small gold node at the arc's peak — confidence anchor -->
        <circle cx="18" cy="5" r="2.2" fill="#d4a843"/>
      </svg>
    `;
  }

  render() {
    const wcls = `wrap ${this.invert ? 'invert' : ''} ${this.variant === 'compact' ? 'compact' : ''}`;
    if (this.variant === 'mark-only') {
      return html`<a class="${wcls}" href="/">${this._renderMark(40)}</a>`;
    }
    return html`
      <a class="${wcls}" href="/">
        ${this._renderMark(this.variant === 'compact' ? 30 : 40)}
        <span class="wordmark">
          <span class="name">OpenGenealogy<span style="color: var(--gold-dark);">AI</span></span>
          <span class="tag">Find ancestors. Honestly.</span>
        </span>
      </a>
    `;
  }
}
defineOnce('maxgen-logo', MaxgenLogo);


class MaxgenHeader extends MaxgenElement {
  static properties = {
    pageTitle: { type: String, attribute: 'page-title' },
    crumb:     { type: String },
  };
  constructor() { super(); this.pageTitle = ''; this.crumb = ''; }

  static styles = [MaxgenElement.styles, css`
    :host { display: block; }
    .bar {
      background: linear-gradient(180deg, #1a1209 0%, #2a1d10 100%);
      color: var(--paper);
      padding: 0;
      border-bottom: 2px solid var(--gold);
    }
    .row {
      display: flex; align-items: center; gap: 20px;
      max-width: 1400px; margin: 0 auto;
      padding: 12px 24px;
    }
    .pageinfo {
      display: flex; flex-direction: column;
      margin-left: auto;
      text-align: right;
    }
    .crumb {
      font-family: var(--font-ui);
      font-size: var(--text-xs);
      color: var(--gold);
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }
    .title {
      font-family: var(--font-body);
      font-size: var(--text-md);
      color: var(--paper);
    }
    nav {
      display: flex; gap: 4px;
      max-width: 1400px; margin: 0 auto;
      padding: 0 24px 8px;
      flex-wrap: wrap;
    }
    nav a {
      padding: 4px 10px;
      border-radius: var(--radius-pill, 999px);
      font-family: var(--font-ui);
      font-size: var(--text-xs);
      color: rgba(247, 244, 238, 0.7);
      text-decoration: none;
      transition: background 0.15s;
    }
    nav a:hover { background: rgba(212, 168, 67, 0.18); color: var(--paper); }
    nav a.active {
      background: var(--gold);
      color: var(--ink);
      font-weight: 600;
    }
    @media (max-width: 700px) {
      .row { flex-direction: column; align-items: flex-start; }
      .pageinfo { margin-left: 0; text-align: left; }
    }
  `];

  _nav() {
    const routes = [
      ['/',                          'Home'],
      ['/dev/pedigree',              'Pedigree'],
      ['/dev/family-group-sheet',    'Group sheet'],
      ['/dev/person',                'Profile'],
      ['/dev/fan',                   'Fan chart'],
      ['/dev/map',                   'Migration'],
      ['/dev/tools',                 'Tools'],
      ['/dev/ai',                    'AI assistant'],
      ['/dev/components',            'Components'],
    ];
    const here = this.crumb || (window.location ? window.location.pathname : '');
    return routes.map(([href, label]) => html`
      <a href="${href}" class="${here === href ? 'active' : ''}">${label}</a>
    `);
  }

  render() {
    return html`
      <header class="bar">
        <div class="row">
          <maxgen-logo invert></maxgen-logo>
          <div class="pageinfo">
            <span class="crumb">OpenGenealogyAI</span>
            <span class="title">${this.pageTitle || 'Live demo'}</span>
          </div>
        </div>
        <nav>${this._nav()}</nav>
      </header>
    `;
  }
}
defineOnce('maxgen-header', MaxgenHeader);
