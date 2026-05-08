/* Ada — OpenGenealogyAI Genealogy Expert Chat Widget
   Self-contained. Mounts automatically on DOMContentLoaded.
   No external dependencies. */

(function () {
  'use strict';

  /* ── Config ─────────────────────────────────────── */
  const CHAT_API_URL = window.CHAT_API_URL || 'http://localhost:8081';
  const FREE_QUESTIONS = 2;       // questions before email gate
  const EMAIL_QUESTIONS = 3;      // extra questions after email

  /* ── Suggested questions ─────────────────────────── */
  const CHIPS = [
    'What sources are best for finding ancestors born in 1812 in Kentucky?',
    'Who was Abraham Lincoln\'s great-grandfather?',
    'How do I find German immigration records from the 1880s?',
    'What\'s the difference between a census and a vital record?',
    'Can you trace British royal ancestry back 500 years?',
  ];

  /* ── Session state ───────────────────────────────── */
  function getSessionId() {
    let id = sessionStorage.getItem('ada_session_id');
    if (!id) {
      id = typeof crypto !== 'undefined' && crypto.randomUUID
        ? crypto.randomUUID()
        : 'sess-' + Math.random().toString(36).slice(2) + Date.now();
      sessionStorage.setItem('ada_session_id', id);
    }
    return id;
  }

  function getQuestionNumber() {
    return parseInt(sessionStorage.getItem('ada_question_number') || '0', 10);
  }

  function incrementQuestion() {
    const n = getQuestionNumber() + 1;
    sessionStorage.setItem('ada_question_number', String(n));
    return n;
  }

  function getEmailUnlocked() {
    return sessionStorage.getItem('ada_email_unlocked') === '1';
  }

  function setEmailUnlocked(email) {
    sessionStorage.setItem('ada_email_unlocked', '1');
    sessionStorage.setItem('ada_user_email', email);
  }

  function getEmailQuestionsUsed() {
    return parseInt(sessionStorage.getItem('ada_email_q_used') || '0', 10);
  }

  function incrementEmailQuestion() {
    const n = getEmailQuestionsUsed() + 1;
    sessionStorage.setItem('ada_email_q_used', String(n));
    return n;
  }

  /* ── Counter display ─────────────────────────────── */
  function updateCounter(el) {
    const qn = getQuestionNumber();
    const emailUnlocked = getEmailUnlocked();

    if (emailUnlocked) {
      const emailUsed = getEmailQuestionsUsed();
      const remaining = EMAIL_QUESTIONS - emailUsed;
      if (remaining <= 0) {
        el.textContent = 'Free questions used — upgrade for unlimited access';
        el.className = 'ada-counter ada-counter-warn';
      } else {
        el.textContent = remaining === 1
          ? '1 free question remaining'
          : remaining + ' free questions remaining';
        el.className = remaining === 1
          ? 'ada-counter ada-counter-warn'
          : 'ada-counter';
      }
    } else {
      const remaining = FREE_QUESTIONS - qn;
      if (remaining <= 0) {
        el.textContent = 'Free questions used — enter email for more';
        el.className = 'ada-counter ada-counter-warn';
      } else {
        el.textContent = remaining === 1
          ? '1 free question remaining'
          : remaining + ' free questions remaining';
        el.className = remaining === 1
          ? 'ada-counter ada-counter-warn'
          : 'ada-counter';
      }
    }
  }

  /* ── Check gate status ───────────────────────────── */
  function isBlocked() {
    const qn = getQuestionNumber();
    const emailUnlocked = getEmailUnlocked();
    if (!emailUnlocked && qn >= FREE_QUESTIONS) return 'email';
    if (emailUnlocked && getEmailQuestionsUsed() >= EMAIL_QUESTIONS) return 'paywall';
    return false;
  }

  /* ── SVGs ─────────────────────────────────────────── */
  const SVG_CHAT = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`;

  const SVG_CLOSE = `<svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="4" y1="4" x2="14" y2="14"/><line x1="14" y1="4" x2="4" y2="14"/></svg>`;

  const SVG_SEND = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>`;

  // Simple woman silhouette SVG for Ada's avatar
  const SVG_AVATAR = `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
    <circle cx="12" cy="7" r="3.5"/>
    <path d="M5 20c0-4.5 3.1-7 7-7s7 2.5 7 7" stroke-width="0" fill-opacity="0.9"/>
    <ellipse cx="12" cy="6.5" rx="3.8" ry="1.2" opacity="0.5"/>
  </svg>`;

  /* ── Build DOM ───────────────────────────────────── */
  function buildWidget() {
    // Bubble
    const bubble = document.createElement('button');
    bubble.id = 'ada-bubble';
    bubble.setAttribute('aria-label', 'Chat with Ada, genealogy expert');
    bubble.innerHTML = SVG_CHAT;

    // Panel
    const panel = document.createElement('div');
    panel.id = 'ada-panel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', 'Ada — Genealogy Expert Chat');

    // Header
    const header = document.createElement('div');
    header.className = 'ada-header';
    header.innerHTML = `
      <div class="ada-avatar">${SVG_AVATAR}</div>
      <div class="ada-header-text">
        <div class="ada-name">Ada</div>
        <div class="ada-subtitle-row">
          <span class="ada-subtitle">Genealogy Expert</span>
          <span class="ada-online-dot" title="Online"></span>
        </div>
      </div>
      <button class="ada-close-btn" aria-label="Close chat">${SVG_CLOSE}</button>
    `;

    // Messages area
    const messages = document.createElement('div');
    messages.className = 'ada-messages';
    messages.id = 'ada-messages';

    // Counter
    const counter = document.createElement('div');
    counter.className = 'ada-counter';
    counter.id = 'ada-counter';

    // Input row
    const inputRow = document.createElement('div');
    inputRow.className = 'ada-input-row';
    inputRow.innerHTML = `
      <textarea class="ada-input" id="ada-input" placeholder="Ask Ada anything about genealogy…" rows="1" aria-label="Type your question"></textarea>
      <button class="ada-send-btn" id="ada-send" aria-label="Send">${SVG_SEND}</button>
    `;

    panel.appendChild(header);
    panel.appendChild(messages);
    panel.appendChild(counter);
    panel.appendChild(inputRow);

    document.body.appendChild(bubble);
    document.body.appendChild(panel);

    return { bubble, panel, messages, counter, inputRow };
  }

  /* ── Greeting card ───────────────────────────────── */
  function renderGreeting(messages) {
    const card = document.createElement('div');
    card.className = 'ada-greeting-card ada-msg ada-msg-ada';
    card.id = 'ada-greeting';
    card.innerHTML = `
      <p>Hi! I'm Ada, your genealogy research expert. I can help you trace your family history, find the right records, and answer questions about your ancestors.</p>
      <p>Try asking me:</p>
      <div class="ada-chips-label">Suggested questions</div>
      <div class="ada-chips" id="ada-chips">
        ${CHIPS.map(q => `<button class="ada-chip">${q}</button>`).join('')}
      </div>
    `;
    messages.appendChild(card);
  }

  /* ── Email gate card ─────────────────────────────── */
  function renderEmailGate(messages, onSubmit) {
    const card = document.createElement('div');
    card.className = 'ada-gate-card ada-msg ada-msg-ada';
    card.innerHTML = `
      <div class="ada-gate-title">🌳 You've used your ${FREE_QUESTIONS} free questions!</div>
      <p>Enter your email for ${EMAIL_QUESTIONS} more free questions — no credit card required.</p>
      <input class="ada-gate-input" type="email" placeholder="you@example.com" aria-label="Email address" />
      <button class="ada-gate-btn">Continue Free →</button>
      <div class="ada-gate-error">Please enter a valid email address.</div>
    `;

    const input = card.querySelector('.ada-gate-input');
    const btn = card.querySelector('.ada-gate-btn');
    const err = card.querySelector('.ada-gate-error');

    function trySubmit() {
      const email = input.value.trim();
      if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        err.style.display = 'block';
        return;
      }
      err.style.display = 'none';
      setEmailUnlocked(email);
      onSubmit(email, card);
    }

    btn.addEventListener('click', trySubmit);
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') trySubmit();
    });

    messages.appendChild(card);
    scrollToBottom(messages);
    input.focus();
  }

  /* ── Paywall card ────────────────────────────────── */
  function renderPaywall(messages) {
    const card = document.createElement('div');
    card.className = 'ada-paywall-card ada-msg ada-msg-ada';
    card.innerHTML = `
      <div class="ada-paywall-title">🔍 Ready to search 50 million records?</div>
      <p>Ada can search our full genealogy database for your specific ancestors with Research Actions.</p>
      <div class="ada-tier">Starter: 100 searches for $10</div>
      <a href="pricing.html" class="ada-paywall-link">View Pricing →</a>
    `;
    messages.appendChild(card);
    scrollToBottom(messages);
  }

  /* ── Message helpers ─────────────────────────────── */
  function addMessage(messages, text, sender) {
    const el = document.createElement('div');
    el.className = `ada-msg ada-msg-${sender}`;
    const bubble = document.createElement('div');
    bubble.className = 'ada-bubble-text';
    bubble.textContent = text;
    el.appendChild(bubble);
    messages.appendChild(el);
    scrollToBottom(messages);
    return el;
  }

  function addTypingIndicator(messages) {
    const el = document.createElement('div');
    el.className = 'ada-msg ada-typing';
    el.id = 'ada-typing-indicator';
    el.innerHTML = `<div class="ada-typing-dots"><span></span><span></span><span></span></div>`;
    messages.appendChild(el);
    scrollToBottom(messages);
    return el;
  }

  function removeTypingIndicator() {
    const el = document.getElementById('ada-typing-indicator');
    if (el) el.remove();
  }

  function scrollToBottom(messages) {
    messages.scrollTop = messages.scrollHeight;
  }

  /* ── API call ────────────────────────────────────── */
  function askAda(question, sessionId, questionNumber) {
    return fetch(CHAT_API_URL + '/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: question,
        session_id: sessionId,
        question_number: questionNumber,
      }),
    }).then(function (res) {
      if (!res.ok) throw new Error('Server returned ' + res.status);
      return res.json();
    });
  }

  /* ── Send flow ───────────────────────────────────── */
  function handleSend(question, state) {
    question = question.trim();
    if (!question) return;

    const { messages, counter, input, sendBtn } = state;

    // Hide greeting on first user message
    const greeting = document.getElementById('ada-greeting');
    if (greeting) greeting.remove();

    // Check gate BEFORE incrementing
    const gate = isBlocked();
    if (gate === 'email') {
      // Show gate card if not already shown
      if (!document.querySelector('.ada-gate-card')) {
        renderEmailGate(messages, function (email, card) {
          // Replace card with confirmation, then allow asking
          const p = document.createElement('div');
          p.className = 'ada-msg ada-msg-ada';
          const b = document.createElement('div');
          b.className = 'ada-bubble-text';
          b.textContent = 'Great! You now have ' + EMAIL_QUESTIONS + ' more free questions. Go ahead and ask!';
          p.appendChild(b);
          card.replaceWith(p);
          scrollToBottom(messages);
          updateCounter(counter);
          if (input) input.focus();
        });
      }
      return;
    }
    if (gate === 'paywall') {
      if (!document.querySelector('.ada-paywall-card')) {
        renderPaywall(messages);
      }
      return;
    }

    // Count the question
    const emailUnlocked = getEmailUnlocked();
    if (emailUnlocked) {
      incrementEmailQuestion();
    }
    const qNum = incrementQuestion();

    // Disable input while waiting
    if (input) input.value = '';
    if (sendBtn) sendBtn.disabled = true;

    addMessage(messages, question, 'user');
    updateCounter(counter);

    const typing = addTypingIndicator(messages);

    const sessionId = getSessionId();

    askAda(question, sessionId, qNum)
      .then(function (data) {
        removeTypingIndicator();
        const reply = (data && data.reply) ? data.reply : 'I couldn\'t reach the server right now. Please try again in a moment.';
        addMessage(messages, reply, 'ada');
      })
      .catch(function () {
        removeTypingIndicator();
        addMessage(messages, 'I\'m having trouble connecting to the server. Make sure the API server is running on port 8081.', 'ada');
      })
      .finally(function () {
        if (sendBtn) sendBtn.disabled = false;
        if (input) input.focus();
        updateCounter(counter);

        // Check if gates triggered after this question
        const newGate = isBlocked();
        if (newGate === 'email' && !document.querySelector('.ada-gate-card')) {
          renderEmailGate(messages, function (email, card) {
            const p = document.createElement('div');
            p.className = 'ada-msg ada-msg-ada';
            const b = document.createElement('div');
            b.className = 'ada-bubble-text';
            b.textContent = 'Great! You now have ' + EMAIL_QUESTIONS + ' more free questions. Go ahead and ask!';
            p.appendChild(b);
            card.replaceWith(p);
            scrollToBottom(messages);
            updateCounter(counter);
            if (input) input.focus();
          });
        } else if (newGate === 'paywall' && !document.querySelector('.ada-paywall-card')) {
          renderPaywall(messages);
        }
      });
  }

  /* ── Auto-resize textarea ────────────────────────── */
  function autoResize(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 80) + 'px';
  }

  /* ── Init ────────────────────────────────────────── */
  function init() {
    const { bubble, panel, messages, counter } = buildWidget();

    const input = document.getElementById('ada-input');
    const sendBtn = document.getElementById('ada-send');

    const state = { messages, counter, input, sendBtn };

    // Render initial greeting
    renderGreeting(messages);
    updateCounter(counter);

    // Chip clicks
    messages.addEventListener('click', function (e) {
      if (e.target && e.target.classList.contains('ada-chip')) {
        handleSend(e.target.textContent, state);
      }
    });

    // Open / close
    function openPanel() {
      panel.classList.add('ada-open');
      bubble.style.display = 'none';
      if (input) setTimeout(function () { input.focus(); }, 220);
    }

    function closePanel() {
      panel.classList.remove('ada-open');
      bubble.style.display = '';
    }

    bubble.addEventListener('click', openPanel);

    const closeBtn = panel.querySelector('.ada-close-btn');
    closeBtn.addEventListener('click', closePanel);

    // Close on Escape
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && panel.classList.contains('ada-open')) {
        closePanel();
      }
    });

    // Send on button click
    sendBtn.addEventListener('click', function () {
      handleSend(input.value, state);
    });

    // Send on Enter (Shift+Enter = newline)
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend(input.value, state);
      }
    });

    // Auto-resize
    input.addEventListener('input', function () {
      autoResize(input);
    });
  }

  /* ── Boot ────────────────────────────────────────── */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
