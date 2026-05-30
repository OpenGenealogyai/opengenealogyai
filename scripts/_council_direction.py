"""Six-brain with Designer on the next-direction decision. Uses Flash if Pro is overloaded."""
import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\Users\stock\dev\opengenealogyai\scripts")
import brains
# Pro is overloaded today; use Flash for the strategist
brains.GEMINI_MODEL = "gemini-2.5-flash"
from brains import six_brain

question = """OpenGenealogyAI status as of 2026-05-17:

WHAT'S BUILT (12 of 13 tracker tasks DONE, 8 live demo pages with Garlon's real Maxwell ancestor data):
- Tier-0 differentiators: confidence chip/bar, 10-possibilities expander, conflict view, DNA noisy-OR boost
- Views: family group sheet, person profile (6 tabs incl Timeline), pedigree chart (5 gen + Scotland dead-end), fan chart, migration map (Scotland->AZ 14 pins), relationship calculator, merge UI, AI research assistant (real Claude API)
- Infrastructure: design tokens, ~17 Lit web components, real three/six-brain via brains.py, Postgres DDL deployed, MAXGEN v1.4 schemas, 62 fixtures validated
- Open-source docs: brand, microcopy, a11y, nav-IA, onboarding wireframe, confidence calibration, DNA architecture, schema changelog
- Verified live in Chrome

THE GAP — demo pages use HARDCODED JSON inside <script> tags in templates, NOT the real Postgres DB. Postgres tables exist (persons, dna_kits, etc.) but they're empty. No ingest agent yet.

OPTIONS:
A) Wire pedigree demo to Postgres (close the hardcoded-JSON gap; ingest FAG JSONs -> persons table -> /api/pedigree/<id> endpoint -> fetch in template)
B) GEDCOM import (turn GEDCOM 5.5.1 into MaxPerson + Postgres write, validation + transaction-gated)
C) Visual polish pass (pedigree node text truncation, expander hover states, mobile breakpoints, dark mode review, a11y audit)
D) Propose something different
"""
options = """A) Wire pedigree demo to Postgres
B) GEDCOM import
C) Visual polish pass
D) Different proposal
"""

t = time.time()
print("Running SIX-BRAIN with Designer (4 judges x 2 passes, Gemini Flash)...\n")
result = six_brain(question, options, designer=True)

print("=" * 80)
print("PASS 1 — Open Council")
print("=" * 80)
for name, text in result["pass1"].items():
    print(f"\n--- {name.upper()} ---")
    print(text)

print("\n" + "=" * 80)
print("PASS 2 — Adversarial")
print("=" * 80)
for name, text in result["pass2"].items():
    print(f"\n--- {name.upper()} ---")
    print(text)

print(f"\nTotal: {round(time.time()-t,1)}s")
