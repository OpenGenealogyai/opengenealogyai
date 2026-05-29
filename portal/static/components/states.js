// <maxgen-empty>  •  <maxgen-skeleton>
// Empty states + loading placeholders. Per docs/microcopy.md: name the next
// step, never just "(none)".

import { html, css } from 'https://esm.sh/lit@3';
import { MaxgenElement, defineOnce } from './_base.js';

class MaxgenEmpty extends MaxgenElement {
  static properties = {
    message: { type: String },
    cta:     { type: String },
    href:    { type: String },
  };
  constructor() { super(); this.message = ''; this.cta = ''; this.href = ''; }
  static styles = [MaxgenElement.styles, css`
    :host { display: block; }
    .empty {
      padding: 16px 12px;
      text-align: center;
      font-family: var(--font-ui);
      font-size: var(--text-sm);
      color: var(--muted);
      border: 1px dashed var(--border, #ddd8cc);
      border-radius: var(--radius, 6px);
      background: rgba(212, 168, 67, 0.04);
    }
    .msg { margin-bottom: 8px; }
    a.cta {
      color: var(--gold-dark, #b8902d);
      text-decoration: none;
      font-weight: 600;
    }
    a.cta:hover { text-decoration: underline; }
    a.cta::after { content: ' →'; }
    /* CTA slot fallback */
    ::slotted(*) { font-weight: 600; }
  `];
  render() {
    return html`
      <div class="empty">
        <div class="msg">${this.message || 'Nothing here yet.'}</div>
        ${this.cta && this.href
          ? html`<a class="cta" href="${this.href}">${this.cta}</a>`
          : html`<slot></slot>`}
      </div>
    `;
  }
}
defineOnce('maxgen-empty', MaxgenEmpty);

class MaxgenSkeleton extends MaxgenElement {
  static properties = {
    w:     { type: String },  // any CSS width
    h:     { type: String },  // any CSS height
    shape: { type: String },  // 'line' (default) | 'circle' | 'rect'
  };
  constructor() { super(); this.w = '100%'; this.h = '1em'; this.shape = 'line'; }
  static styles = [MaxgenElement.styles, css`
    :host { display: inline-block; }
    .sk {
      display: inline-block;
      background: linear-gradient(90deg, #e9e3d7 0%, #f3eee2 50%, #e9e3d7 100%);
      background-size: 200% 100%;
      animation: shimmer 1.4s infinite;
      vertical-align: middle;
    }
    .line   { border-radius: 4px; }
    .rect   { border-radius: var(--radius, 6px); }
    .circle { border-radius: 50%; }
    @keyframes shimmer {
      0%   { background-position: 200% 0; }
      100% { background-position: -200% 0; }
    }
    @media (prefers-reduced-motion: reduce) {
      .sk { animation: none; background: #e9e3d7; }
    }
  `];
  render() {
    return html`<span class="sk ${this.shape}"
                      style="width:${this.w}; height:${this.h};"
                      aria-hidden="true"></span>`;
  }
}
defineOnce('maxgen-skeleton', MaxgenSkeleton);
