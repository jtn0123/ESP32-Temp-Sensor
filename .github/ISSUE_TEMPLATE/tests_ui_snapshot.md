---
name: Tests — UI snapshot
about: Golden PNG/MD5 compare for typical values
labels: tests
---

### Goal
Ensure UI regressions are caught via deterministic image hash compare.

### Tasks
- Keep `scripts/mock_display.py` and tests in sync with layout.
- Update `tests/golden_default.md5` only when intentional visual changes occur.

### Acceptance Criteria
- `pytest -q` passes locally and in CI.

