# Final Review: Host Power A–F Prechecks

**Range:** `e8655f0..5c1e03f` (8 commits)
**Reviewer:** Senior Code Review (automated)
**Verification:** Read design spec, plan, and full diff. Ran the seven affected test files locally (51 passed) to confirm the "known findings" and check one unverified ordering concern; did not run the full suite or mutate git.

## Strengths

- **Spec fidelity is high.** The catalog (`host_power_precheck_catalog`), preset insertion order, label-match rule (`Precheck - A` vs `Precheck - AA`), mutate-guard regex, and API contracts (no `confirm`, invalid letter → 400, empty selection → `ok:false` + warnings, no SSH) all match the design doc's normative tables and behavior section exactly.
- **Mutate-guard is correctly defense-in-depth.** `precheck_command_is_mutating` is checked before `run_command` is ever invoked, and a dedicated test (`test_run_precheck_rejects_mutating_without_calling_runner`) proves `run_command` is never called for a poisoned override — this is the single most safety-critical behavior in the feature and it's solid.
- **Good reuse over duplication.** `host_power_precheck` in `health_server.py` reuses `_host_power_selection` (which itself reuses `coerce_card_ids`), `_host_power_card_payload`, and `_snap_run_command` rather than re-implementing selection/coercion logic. `precheck_letter_from_label` is exported once from `host_power_ops.py` and imported by `hadoop_linux_promote.py` rather than duplicated, per the plan's explicit preference.
- **Regression discipline.** `extract_power_steps` and the Preview/Run confirm path are untouched; the plan's instruction to avoid duplicating an existing confirm test was honored (searched the diff — no duplicate `test_host_power_run_still_requires_confirm`/`test_host_power_run_requires_confirm`).
- **UI fix shows real review responsiveness.** The task-5 report documents catching its own bug (an HTML-comment hack for `data-letter` test markers with an empty `#prechecks` div) and correcting it to real static buttons with event delegation, in a follow-up commit before merge.
- All 51 tests across the seven touched/added test files pass locally.

## Issues

### Critical
None found.

### Important

1. **Promote-path command ordering silently diverges from the fresh-preset order.** `_merge_hadoop_linux_presets` (`launchpad/hadoop_linux_promote.py:51-69`) builds `additions` as `[missing Power lines] + [missing Precheck lines]`, so a partially-configured card that's missing both groups gets Power lines appended **before** Precheck lines — the opposite of `HADOOP_LINUX_COMMANDS` in `storage_presets.py:139-155`, which the design explicitly requires to have Precheck before Power. Verified live:
   ```
   Health - Uptime|uptime
   Power - Stop YARN NodeManager|...
   Power - Stop HDFS DataNode|...
   Power - OS Shutdown|...
   Precheck - A ...
   ...
   ```
   This is not functionally harmful today (Preview still filters by `Power -` prefix regardless of position, and `resolve_precheck_command` doesn't care about order), but it means the on-card command list looks inconsistent between a freshly-created `hadoop_linux` card and one that was promoted/merged, and no test guards this ordering for the merge path (only the fresh-preset path is asserted in `test_hadoop_linux_presets_include_precheck_a_through_f_before_power`). Low risk to fix (swap the two `additions.extend(...)` calls), but worth doing before this drifts further as promote logic grows.

### Minor

2. **`ensure_hadoop_linux_cards` docstring is stale/incomplete** (`launchpad/hadoop_linux_promote.py:72-80`). It still describes only "Power - presets merged in" / "missing Power - commands get those presets appended" with no mention that it now also merges missing `Precheck -` A–F lines. Matches the known finding from task review; purely documentation, no behavior risk.
3. **`test_host_power_precheck_runs_without_confirm` exercises `HealthServer.host_power_precheck` directly, not the `POST /api/host-power/precheck` route** (`tests/test_host_power_api.py:~211-227`). The 400-invalid-letter and empty-selection cases are covered at the route/API level elsewhere, but there is no test that drives a *successful* precheck through `do_POST` end-to-end (JSON parsing → `card_ids` → `letter` → response body shape). The route glue is simple and low-risk, but it's the one path in Task 4 that never got a true black-box HTTP-level happy-path test.
4. **Append-vs-replace log behavior has no automated coverage**, browser or otherwise — acknowledged directly in `task-5-report.md`'s Concerns section. `appendLog`/`writeLog` are only proven correct by code reading, not by a DOM/JS test. Given this is pure client-side string concatenation with no server round-trip risk, this is acceptable to ship without blocking, but should not be treated as "tested."
5. **`tests/test_system_connectivity_version.py::test_app_version_16133`** still has its original (stale) name pinned to `"1.6.133"`-style naming while asserting `"1.6.143"`. Purely cosmetic — matches the known finding — but will keep confusing anyone grepping test names against actual version bumps unless renamed in a future pass.
6. **Module docstring for `host_power_ops.py`** ("Host Power preview and run helpers...") wasn't extended to mention prechecks even though the module now owns half the precheck feature (catalog, resolve, guard, run). Same class of drift as #2.

## Recommendations

- Before or shortly after merge, swap the two `additions.extend(...)` calls in `_merge_hadoop_linux_presets` so Precheck lines precede Power lines on the merge path too, matching the fresh-preset order, and add an order assertion to `test_ensure_hadoop_linux_cards_appends_missing_prechecks` to lock it in.
- Update the `ensure_hadoop_linux_cards` and `host_power_ops.py` docstrings to mention Precheck A–F merge/ownership (5-minute doc fix).
- Add one focused `_post("/api/host-power/precheck", {...})` happy-path test to close the API/route coverage gap noted in Minor #3.
- None of the above need to block merge; they're good fast-follow cleanup, ideally same week.

## Assessment

**Ready to merge?** With fixes (none blocking; recommend at least the ordering fix in `_merge_hadoop_linux_presets` before merge since it's a one-line swap, the rest can follow shortly after)

**Reasoning:** All spec-mandated safety and API behavior (mutate-guard, no-confirm, 400 on bad letter, per-host failure isolation, append-not-replace log) is implemented correctly and passes its 51 tests, with no critical or important user-facing defects; the one real bug found (Power-before-Precheck ordering on the promote/merge path) is cosmetic and untested rather than unsafe, and the remaining findings are documentation/test-coverage gaps that don't threaten correctness.

## Final fix (Important #1)

**Date:** 2026-08-07  
**Change:** Swapped `_merge_hadoop_linux_presets` to append missing Precheck A–F lines before Power lines; updated `ensure_hadoop_linux_cards` docstring; added `test_ensure_hadoop_linux_cards_merge_appends_precheck_before_power`.  
**Tests:** `python -m pytest tests/test_hadoop_linux_promote.py -q` → **8 passed** in 0.55s  
**Commit message:** Append Host Power prechecks before Power when promoting.
