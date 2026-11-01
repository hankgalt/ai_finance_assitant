# M7 accessibility and redaction review

## Accessibility

- Every graph has an adjacent ordered event list containing event number, type, node, status, and
  measured duration or unavailable state.
- Every graph node includes its exact persisted timeline positions. Only consecutive positions are
  collapsed into a range, and an adjacent note explains that parallel branches may interleave.
- Timeline entries are native buttons and expose the selected entry through `aria-current`.
- The Run selector is a labeled native `select`; reconnect is a labeled native button.
- Headings and labeled regions preserve a navigable hierarchy independent of the canvas.
- The success/partial/failure Chrome journey reported zero serious or critical Axe violations.
- React Flow panning/zoom controls are supplemental; no required detail is available only through
  canvas interaction.

## Redaction

- The browser fixture supplies a recognizable `request_message`; Playwright asserts that it is not
  rendered anywhere in Inspector.
- No component reads or displays a final response body, hidden reasoning, raw input, credential,
  request header, or arbitrary tool payload.
- Detail sections consume the typed privacy-filtered RunEvent contract. `safe_metadata` keys are
  shown, but non-scalar structured values are not expanded.
- Synthetic evidence is identified from recorded fixture/provider metadata and labeled before the
  graph and details.
- Trace identifiers are opaque correlation values. Inspector does not use them to query LangSmith
  or another external system.
