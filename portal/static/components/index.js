// Single entry point. Loading this registers every <maxgen-*> component.
// Pages do: <script type="module" src="/static/components/index.js"></script>

import './_base.js';
import './confidence.js';
import './source.js';
import './states.js';
import './photo.js';
import './fact.js';
import './person-card.js';
import './family-group-sheet.js';

// Inform pages the component bundle is ready.
window.__maxgenReady = true;
window.dispatchEvent(new CustomEvent('maxgen-ready'));
