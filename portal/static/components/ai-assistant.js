// <maxgen-ai-assistant>
// Chat component that asks questions about the user's tree.
// Backend: /api/ai-assistant — passes a tree-context JSON to Claude.

import { html, css } from 'https://esm.sh/lit@3';
import { MaxgenElement, defineOnce } from './_base.js';

class MaxgenAiAssistant extends MaxgenElement {
  static properties = {
    treeContext: { type: Object },
    messages:    { type: Array },
    busy:        { type: Boolean },
  };
  constructor() {
    super();
    this.treeContext = null;
    this.messages = [
      { role: 'assistant',
        content: "I'm the OpenGenealogyAI research assistant. I can answer questions about your tree — anything from \"Who was William Bailey Maxwell's father?\" to \"What's known about the Mormon Battalion service?\". I'll be honest about what's confident vs uncertain. What would you like to know?" }
    ];
    this.busy = false;
  }

  static styles = [MaxgenElement.styles, css`
    :host { display: block; }
    .panel {
      background: white;
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      box-shadow: var(--shadow-card);
      display: flex;
      flex-direction: column;
      height: 600px;
      max-height: 80vh;
      overflow: hidden;
    }
    .header {
      padding: 12px 16px;
      background: var(--ink);
      color: var(--paper);
      font-family: var(--font-body);
      font-size: var(--text-md);
      display: flex; align-items: center; gap: 8px;
    }
    .header .pulse {
      width: 8px; height: 8px; border-radius: 50%;
      background: var(--gold);
      box-shadow: 0 0 8px var(--gold);
      animation: pulse 2s ease-in-out infinite;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.4; }
    }
    .messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      background: var(--paper);
    }
    .msg {
      max-width: 85%;
      padding: 10px 14px;
      border-radius: var(--radius-lg);
      font-family: var(--font-body);
      font-size: var(--text-base);
      line-height: 1.5;
      white-space: pre-wrap;
    }
    .msg.user {
      align-self: flex-end;
      background: var(--gold);
      color: var(--ink);
      font-family: var(--font-ui);
      font-size: var(--text-sm);
    }
    .msg.assistant {
      align-self: flex-start;
      background: white;
      color: var(--ink);
      border: 1px solid var(--border);
    }
    .msg.error {
      align-self: stretch;
      background: var(--error-bg);
      border: 1px solid var(--error);
      color: var(--error);
      font-family: var(--font-ui);
      font-size: var(--text-sm);
    }
    .input-row {
      display: flex; gap: 8px;
      padding: 12px;
      border-top: 1px solid var(--border);
      background: white;
    }
    .input-row textarea {
      flex: 1;
      padding: 8px 12px;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      font-family: var(--font-body);
      font-size: var(--text-sm);
      resize: none;
      min-height: 36px;
      max-height: 100px;
    }
    .input-row textarea:focus { outline: 2px solid var(--gold); border-color: var(--gold); }
    .input-row button {
      padding: 8px 18px;
      background: var(--gold);
      color: var(--ink);
      border: none;
      border-radius: var(--radius);
      font-family: var(--font-ui);
      font-weight: 600;
      cursor: pointer;
    }
    .input-row button:disabled { opacity: 0.5; cursor: not-allowed; }
    .input-row button:hover:not(:disabled) { background: var(--gold-dark); color: var(--paper); }
    .typing {
      align-self: flex-start;
      font-family: var(--font-ui);
      font-size: var(--text-xs);
      color: var(--muted);
      font-style: italic;
      padding: 4px 8px;
    }
    .typing .dot {
      display: inline-block;
      animation: bounce 1.4s infinite;
    }
    .typing .dot:nth-child(2) { animation-delay: 0.2s; }
    .typing .dot:nth-child(3) { animation-delay: 0.4s; }
    @keyframes bounce { 0%, 60%, 100% { opacity: 0.3; } 30% { opacity: 1; } }
    .suggestions {
      display: flex; flex-wrap: wrap; gap: 6px;
      padding: 8px 12px;
      border-top: 1px solid var(--border);
      background: var(--paper);
    }
    .suggestions .sg {
      padding: 4px 10px;
      background: white;
      border: 1px solid var(--border);
      border-radius: var(--radius-pill);
      font-family: var(--font-ui);
      font-size: var(--text-xs);
      color: var(--muted);
      cursor: pointer;
    }
    .suggestions .sg:hover { color: var(--ink); border-color: var(--gold-dark); }
  `];

  _scrollToBottom() {
    requestAnimationFrame(() => {
      const m = this.shadowRoot.querySelector('.messages');
      if (m) m.scrollTop = m.scrollHeight;
    });
  }

  async _send(text) {
    if (!text || this.busy) return;
    this.messages = [...this.messages, { role: 'user', content: text }];
    this.busy = true;
    this._scrollToBottom();

    try {
      const res = await fetch('/api/ai-assistant', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          messages: this.messages,
          tree_context: this.treeContext || {}
        })
      });
      const data = await res.json();
      if (data.error) {
        this.messages = [...this.messages, { role: 'error', content: `Couldn't reach the assistant — ${data.error}${data.detail ? ': ' + data.detail : ''}` }];
      } else {
        this.messages = [...this.messages, { role: 'assistant', content: data.reply }];
      }
    } catch (e) {
      this.messages = [...this.messages, { role: 'error', content: `Network error: ${e.message}` }];
    }
    this.busy = false;
    this._scrollToBottom();
  }

  _onSubmit(e) {
    e.preventDefault();
    const input = this.shadowRoot.querySelector('textarea');
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    this._send(text);
  }
  _onKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this._onSubmit(e); }
  }
  _clickSuggestion(t) {
    const input = this.shadowRoot.querySelector('textarea');
    input.value = t;
    this._onSubmit({ preventDefault: () => {} });
  }

  render() {
    const suggestions = [
      "Who was William Bailey Maxwell's father?",
      "Tell me about the Mormon Battalion service",
      "What's the most uncertain fact in this tree?",
      "What should I research next?",
      "How can I find William Maxwell 1740's parents?",
    ];
    return html`
      <div class="panel">
        <div class="header">
          <span class="pulse"></span>
          AI research assistant
          <span style="font-family: var(--font-ui); font-size: var(--text-xs); color: rgba(255,255,255,0.6); margin-left: auto;">
            ${this.treeContext?.person_count || 0} people loaded
          </span>
        </div>

        <div class="messages">
          ${this.messages.map(m => html`
            <div class="msg ${m.role}">${m.content}</div>
          `)}
          ${this.busy ? html`
            <div class="typing">
              Researching <span class="dot">.</span><span class="dot">.</span><span class="dot">.</span>
            </div>
          ` : ''}
        </div>

        <div class="suggestions">
          ${suggestions.map(s => html`
            <span class="sg" @click=${() => this._clickSuggestion(s)}>${s}</span>
          `)}
        </div>

        <form class="input-row" @submit=${this._onSubmit}>
          <textarea
            placeholder="Ask anything about the loaded tree…"
            @keydown=${this._onKey}
            ?disabled=${this.busy}></textarea>
          <button type="submit" ?disabled=${this.busy}>Ask</button>
        </form>
      </div>
    `;
  }
}
defineOnce('maxgen-ai-assistant', MaxgenAiAssistant);
