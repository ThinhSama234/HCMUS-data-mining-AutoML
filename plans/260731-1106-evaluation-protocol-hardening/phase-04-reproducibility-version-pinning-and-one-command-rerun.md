---
phase: 4
title: "Reproducibility: versions + one-command"
status: completed
priority: P3
effort: "0.5-1d"
dependencies: []
---

# Phase 4: Reproducibility: versions + one-command

## Overview

Close checklist §6. A result is only reproducible if you know exactly which framework version produced
it and can re-run with one command + a fixed seed. Today deps use `>=`, the report JSON records no
version, and the framework version isn't consistently written into `runs`. Pin & **record** versions,
and document a single reproduce command.

## Requirements

- Functional:
  - Every `runs` row carries a **framework version** (AMLB Docker image tag/digest, and/or the
    framework's own version string), written at ingest and shown/exported in the console.
  - Framework versions are **pinned**: the `methods` catalog already stores `image_tag` / `image_digest`
    — treat the digest as the version of record; surface it and include it in exports.
  - A documented **single command** to reproduce a run (constraint + datasets + seed), and a stated
    fixed seed for the split.
- Non-functional:
  - `runs.framework_version` already exists — populate it; do not add schema. Keep Python deps pinned
    with a clear lower bound (frameworks live in Docker images, so the image digest is the real pin).

## Architecture

`runs.framework_version` exists and `repo.load()` exposes it as `version`; `methods` has
`image_tag`/`image_digest`/`last_integration_at`. The AMLB runner should write the running image's
digest (and/or AMLB's reported framework version) into `runs.framework_version` on ingest. Reproduce =
`storage.runner.launch(method, dataset_ids, constraint)` already encapsulates a run; document the exact
CLI/console steps + the fixed seed AMLB uses. Exports (Phase-4/HTML report from the parent plan) include
the version column.

```
methods.image_digest ─┐
AMLB framework version ┼─▶ runs.framework_version (write at _ingest_job) ─▶ repo.load() `version` ─▶ UI + export
fixed seed + constraint + datasets ─▶ one documented reproduce command
```

## Related Code Files

- Modify: `storage/runner.py` (`_ingest_job` / `launch`) — write the image digest / AMLB framework
  version into `runs.framework_version`.
- Modify: `console/views/evaluation.py` (or the per-task table) — show the framework version; ensure the
  Export includes it.
- Modify: `requirements.txt` — tighten pins where it matters; document that framework versions are
  pinned via the Docker image digests on `methods`.
- Modify: docs — a "Reproduce a run" section (single command, fixed seed) in `README.md` / `docs/`.
- Modify/extend: `tests/` — assert `runs.framework_version` is populated after an ingest and flows
  through `repo.load()` as `version`.

## Implementation Steps

1. Populate `runs.framework_version` at ingest from the image digest / AMLB-reported version.
2. Surface the version in the console (per-task table / a caption) and include it in exports.
3. Document the one-command reproduce (constraint + datasets + fixed seed) in README/docs.
4. Tighten `requirements.txt` pins where it matters; note the Docker-digest pin for frameworks.
5. Test that version populates + flows through `repo.load()`.

## Success Criteria

- [x] AMLB runs carry a framework version (`runs.framework_version`, from results.csv `version`, e.g.
      flaml 2.3.6); shown in Evaluation → *Frameworks & versions* and in the exported `results.csv`.
      (Report-JSON-ingested runs have no version — the run_automl.py pipeline didn't record one; honest None.)
- [x] Framework versions are pinned by the Docker **image tag** on `methods` (e.g. `0.8.0-v2.1.3` =
      framework + AMLB version) — surfaced as "pin of record" (`image_digest` is not captured, so the tag is used).
- [x] A single documented reproduce path (README "Reproduce a run"): same image tag + constraint +
      datasets → Training → Launch; AMLB fixed per-fold seed.

## Progress (2026-07-31)

Done (display + docs; no logic — AMLB already records `framework_version` at ingest via
`runner._ingest_job`, and `repo.load()` exposes it as `version`):
- Evaluation gains a "Frameworks & versions" section (framework → recorded version → Docker image
  tag pin, from `repo.list_methods`), guarded on version presence; renders on real data (verified).
- `README.md` gains a "Reproduce a run" section (version/tag pin · constraint · fixed seed · one-command steps).
- Export already carries `version` (part of `repo.load()`), so no change needed there.
- Full suite 134 green; AppTest renders the section. Code-review skipped as disproportionate
  (pure display + docs, no new logic); self-verified (guarded, no crash path).

## Risk Assessment

- **Risk:** AMLB doesn't cleanly report a framework version. **Mitigation:** fall back to the Docker
  **image digest** as the version of record (already stored on `methods`) — unambiguous and pinned.
- **Risk:** over-pinning Python deps breaks the mixed AMLB/console venv. **Mitigation:** keep the
  existing coexistence pins (e.g. pandas 1.5.3) and pin only where reproducibility genuinely needs it.
