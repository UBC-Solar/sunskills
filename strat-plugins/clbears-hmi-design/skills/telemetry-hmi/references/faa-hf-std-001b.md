# FAA HF-STD-001B (2016): Human Factors Design Standard
*U.S. DOT / FAA Human Factors Branch, 753 pp. Paraphrased: only the requirements we apply.*

**Colour (5.6.6.2)**
- Use colour conservatively and consistently, and redundantly with another code. Don't rely on it for small items.
- Reserved meanings: red = failure/no-go; flashing red = emergency needing immediate action; yellow =
  caution/marginal; green = within tolerance; white = neutral alternative states; blue = advisory only.
- Keep to about **4 colours per screen** and 7 across related screens. One meaning per colour.
- Avoid red/green as the only distinction; avoid saturated blue for text on dark backgrounds; keep good contrast.
- *Our resolution of FAA vs PAS on green:* normal is neutral grey (PAS). Green is not needed to say "OK";
  blue marks active/advisory states, which FAA allows.

**Graphs (5.6.3.3)**
- Label every axis with its quantity and unit; numbered ticks; at most ~12 major divisions; one scale per axis.
- Identify each curve (legend or label); highlight the critical one; code non-data curves distinctly.
- Trend displays should make trend rate stable and flag non-representative data.

**Dynamic update (5.6.5)**
- Alphanumerics that must be read reliably: update no more than once a second (sunlink refresh = 1 s).
- Rate of change / gross values: 2-5 Hz is fine.

**Flash coding (5.6.6.11)**
- Only for urgent attention; small area; 2-5 Hz. (Our dashboards don't flash.)

**Alarms (5.5.1)**
- Unambiguous, with the cause clear; indicate priority and degree; prioritise presentation;
  alarm only in the modes where the condition is a fault; let users look up the alarm logic
  (we put thresholds and their firmware source in panel descriptions).

**General (4.x)**
- Simplicity, consistency and standardisation across subsystems: the same layout and conventions on every board.
