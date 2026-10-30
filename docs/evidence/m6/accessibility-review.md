# M6 accessibility review

The Chrome journey ran Axe WCAG 2 A/AA checks on the Assistant, Portfolio validation review,
Market result, and Goal result states. Final result: no critical or serious violations.

Verified behavior:

- the first keyboard Tab reaches “Skip to content,” and Enter moves focus to `main`;
- navigation exposes `aria-current` and remains operable in the 390 px drawer;
- Portfolio import opens as a named modal dialog, initially focuses its close control, closes with
  Escape, and restores focus to the Import Portfolio action;
- Portfolio deletion opens a named inline confirmation and moves focus to the destructive action;
  Cancel leaves the Portfolio and its displayed Snapshot unchanged;
- Portfolio save/delete completion uses an accessible status message that remains available for four
  seconds before automatic dismissal;
- the Assistant does not expose or load a Portfolio selector before a relevant routed response;
  the conditional selector has a programmatic label and descriptive text, names every saved
  Portfolio option, and labels the explicit multi-Portfolio scope as a separate comparison;
- opening the Session-clear confirmation moves keyboard focus to the archive action, while Cancel
  leaves the Active Session untouched; Archived Session deletion has its own focused destructive
  confirmation in History;
- inputs have programmatic labels and validation/status content uses live status or alert roles;
- chart containers have concise accessible names and every chart has a backend-matching table;
- tables use captions, column headers, and row headers;
- loading, empty, validation, success, warning, failure, stale, and unavailable language does not
  rely on color alone;
- reduced-motion preferences disable nonessential animation, and evidence charts disable animation
  so the values are immediately available.

The automated contrast defect found during implementation is recorded in `test-report.md`.
Manual review was performed on the five evidence screenshots. Screen-reader testing with named
assistive-technology/version and public-production browser/device coverage remain M8 work.
