// Single entry point. Loading this registers every <maxgen-*> component.
// Pages do: <script type="module" src="/static/components/index.js"></script>

import './_base.js';
import './confidence.js';
import './source.js';
import './states.js';
import './photo.js';
import './fact.js';
import './person-card.js';
import './possibility-expander.js';
import './conflict-view.js';
import './family-group-sheet.js';
import './external-search.js';
import './person-profile.js';
import './pedigree-chart.js';
import './fan-chart.js';
import './dna-evidence.js';
import './timeline.js';
import './relationship-calc.js';
import './merge-ui.js';
import './migration-map.js';
import './ai-assistant.js';
import './brand.js';

// Inform pages the component bundle is ready.
window.__maxgenReady = true;
window.dispatchEvent(new CustomEvent('maxgen-ready'));
