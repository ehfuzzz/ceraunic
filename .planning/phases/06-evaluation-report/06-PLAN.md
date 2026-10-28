---
phase: 06-evaluation-report
plan: 01-03 (single worker run)
type: execute
depends_on: ["02","03","04","05"]
files_modified: [reports/EVALUATION.md, reports/eval-06/*, reports/figures/*, scripts/build_report.py, Makefile]
---
<objective>EVAL-07: one reproducible report answering every item in the brief's Evaluation section, from the four phase results, with the pre-registration ledger, deviations, caveats, and what the numbers mean for the product; `make report` rebuilds every table from results.json files; PDF export via pandoc if available else HTML.</objective>
<context>@.planning/PROJECT.md (the brief's Evaluation paragraph is the checklist) @reports/eval-01/{PREREG,RESULTS}.md + results.json @reports/eval-03/… @reports/eval-04-05/… @reports/eval-06/… (Phase 5 writes to eval-06/ — keep) @prior/hl-mm-ins/reports/ins1/README.md, ins2/README.md (the baseline to compare) @AGENTS.md</context>
<tasks>
<task type="auto"><name>Task 1: skeleton + prereg ledger</name><files>reports/EVALUATION.md, scripts/build_report.py</files><action>Sections: 1 Question and setup; 2 Data (from DATA.md); 3 Pre-registration ledger (every rule, its timestamp, pass/fail, deviations); 4 Station hedge quality; 5 Geography basis; 6 Residual designs; 7 Netting and pool capital; 8 Learning a business's sensitivity; 9 Costs, liquidity, revisions, capital (the brief's list, one table each); 10 What it means for the product; 11 Caveats; Appendix figures. build_report.py fills tables from results.json files via templates.</action><verify>`make report` produces EVALUATION.md + figures/.</verify><done>Skeleton fills.</done></task>
<task type="auto"><name>Task 2: prose + figures</name><files>reports/EVALUATION.md</files><action>Plain-words findings per section with the CIs; comparison to ins1/ins2; every number traceable to a results.json key.</action><verify>no number in prose lacks a source key (keep a hidden map in the script).</verify><done>Draft.</done></task>
<task type="auto"><name>Task 3: fresh-eyes review + fixes + export</name><files>reports/EVALUATION.md, reports/EVALUATION.pdf|html</files><action>Re-read against the brief's Evaluation paragraph line by line; list gaps honestly in §11; export.</action><verify>every sentence of the brief's Evaluation paragraph maps to a section.</verify><done>Report.</done></task>
</tasks>
<output>`.planning/phases/06-evaluation-report/06-SUMMARY.md` (≤ 40 lines).</output>
