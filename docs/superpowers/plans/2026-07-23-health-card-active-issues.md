# Health Dashboard Per-Card Active Issues Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show each Health Dashboard card’s existing `health_issues` in an Active Issues panel on that card (Tempe-style), hidden when Monitor is off.

**Architecture:** Pure JS render helper inside `DASHBOARD_HTML` that reads `card.health_issues` and injects a bordered Active Issues block in `renderCard`. Reuse existing issue severity CSS classes. No new SSH/API. Version **1.6.61**.

**Tech Stack:** Embedded Health Dashboard HTML/JS in `health_server.py`, pytest string contracts.

**Spec:** `docs/superpowers/specs/2026-07-23-health-card-active-issues-design.md`

## Global Constraints

- **Worktree:** `.worktrees/health-card-active-issues` on `feature/health-card-active-issues` from `feature/contingency-groups` tip (`APP_VERSION=1.6.60`, includes active-issues design commit)
- Data: existing `health_issues` only — no new CLI
- Hide panel when Monitor off; empty → “No active issues.”
- Keep fleet `#issues-panel` unchanged
- Bump `APP_VERSION` to **1.6.61**
- Commit at each task’s commit step
- Run from: `cd C:\Users\BrianColley\LaunchPad\.worktrees\health-card-active-issues`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/health_server.py` | CSS + `cardActiveIssuesHtml(card)` + `renderCard` integration |
| `launchpad/config.py` | `1.6.61` |
| `tests/test_health_dashboard_active_issues.py` | Contract tests on `DASHBOARD_HTML` |

---

### Task 0: Confirm baseline

**Files:** none

- [ ] **Step 1: Create worktree**

```powershell
cd C:\Users\BrianColley\LaunchPad
git fetch origin
git worktree add .worktrees/health-card-active-issues -b feature/health-card-active-issues feature/contingency-groups
cd .worktrees/health-card-active-issues
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-23-health-card-active-issues-design.md
Test-Path docs\superpowers\plans\2026-07-23-health-card-active-issues.md
```

Expected: `1.6.60` (or tip), both paths `True` after plan committed on tip.

- [ ] **Step 2: No feature commit**

---

### Task 1: Per-card Active Issues panel in Dashboard HTML

**Files:**
- Modify: `launchpad/health_server.py` (`DASHBOARD_HTML` CSS + JS)
- Create: `tests/test_health_dashboard_active_issues.py`

**Interfaces:**
- Produces:
  - CSS for `.card-active-issues` (orange title, bordered box; reuse `.issue.critical` / `.issue.warn`)
  - JS `cardActiveIssuesHtml(card)`:
    - if `!isMonitorOn(card.id)` → `""`
    - else if no issues → panel with “No active issues.”
    - else → panel listing sorted issues (critical first) with category + escaped message (no server name repeat)
  - `renderCard` inserts `${cardActiveIssuesHtml(card)}` after metrics (before paused-note / updated)

- [ ] **Step 1: Failing contract tests**

```python
from launchpad.health_server import DASHBOARD_HTML


def test_dashboard_has_card_active_issues_markup():
    html = DASHBOARD_HTML
    for text in (
        "Active Issues",
        "card-active-issues",
        "cardActiveIssuesHtml",
        "No active issues.",
        "health_issues",
    ):
        assert text in html
```

- [ ] **Step 2: Run — expect FAIL**

```powershell
cd C:\Users\BrianColley\LaunchPad\.worktrees\health-card-active-issues
python -m pytest tests/test_health_dashboard_active_issues.py -v
```

- [ ] **Step 3: Implement**

Add CSS near existing `.issues-panel` styles:

```css
.card-active-issues {
  margin-top: 12px;
  border: 1px solid rgba(255, 107, 0, 0.45);
  border-radius: 12px;
  padding: 12px 14px;
  background: #121821;
}
.card-active-issues h3 {
  margin: 0 0 10px;
  color: var(--accent);
  font-size: 1rem;
}
.card-active-issues .issue-list { margin: 0; }
.card-active-issues .issues-ok { font-size: 0.9rem; }
```

Add JS before `renderCard`:

```javascript
function cardActiveIssuesHtml(card) {
  if (!isMonitorOn(card.id)) return "";
  const issues = Array.isArray(card.health_issues) ? card.health_issues.slice() : [];
  const rank = { critical: 0, warn: 1 };
  issues.sort(
    (a, b) =>
      (rank[a.severity] ?? 9) - (rank[b.severity] ?? 9) ||
      String(a.category || "").localeCompare(String(b.category || "")) ||
      String(a.message || "").localeCompare(String(b.message || ""))
  );
  let body;
  if (!issues.length) {
    body = '<p class="issues-ok">No active issues.</p>';
  } else {
    body =
      '<div class="issue-list">' +
      issues
        .map((issue) => {
          const sev = escapeHtml(issue.severity || "warn");
          const cat = escapeHtml(issue.category || "");
          const msg = escapeHtml(issue.message || "");
          return `<div class="issue ${sev}"><span>${cat ? cat + " · " : ""}${msg}</span></div>`;
        })
        .join("") +
      "</div>";
  }
  return `<div class="card-active-issues"><h3>Active Issues</h3>${body}</div>`;
}
```

In `renderCard`, after `<div class="metrics">…</div>` insert `${cardActiveIssuesHtml(card)}`.

Do **not** change fleet `renderIssues` / `#issues-panel`.

- [ ] **Step 4: PASS + commit**

```powershell
python -m pytest tests/test_health_dashboard_active_issues.py -q
git add launchpad/health_server.py tests/test_health_dashboard_active_issues.py
git commit -m "Show Active Issues panel on each Health Dashboard card."
```

---

### Task 2: Version bump 1.6.61

**Files:**
- Modify: `launchpad/config.py`

- [ ] **Step 1:** `APP_VERSION = "1.6.61"`

- [ ] **Step 2: Smoke**

```powershell
python -c "from launchpad.config import APP_VERSION; from launchpad.health_server import DASHBOARD_HTML; assert APP_VERSION=='1.6.61'; assert 'card-active-issues' in DASHBOARD_HTML; print('ok')"
python -m pytest tests/test_health_dashboard_active_issues.py -q
```

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py
git commit -m "Bump version to 1.6.61 for per-card Active Issues."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Per-card Active Issues UI from `health_issues` | 1 |
| Hide when Monitor off; empty copy; fleet unchanged | 1 |
| Version 1.6.61 | 2 |

## Self-review notes

- Escape all issue fields with `escapeHtml`.
- Do not invent new analyzers or presets.
- Fleet panel must remain.
