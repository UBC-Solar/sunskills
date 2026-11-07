# Hollifield & Perez (PAS, 2012): High Performance HMI
*White paper "High Performance Graphics to Maximize Operator Effectiveness", v2.0. Paraphrased.*

**Problem.** Typical control graphics are schematic pictures covered in numbers (data, not information),
use bright colour for normal states, have few trends and no hierarchy. Operators then "run by alarm".

**Principles.**
- *Information is data in context.* Show measurements as analog indicators or trends with the **normal
  range, alarm ranges and trip/interlock points drawn in**, so "is it OK?" takes one glance, not a lookup.
- *Colour:* grey background, low-contrast normal states; bright colour only for abnormal situations;
  alarm colours used **only** for alarms. **Colour is never the only cue** (colour-vision deficiency):
  pair it with shape, text or brightness (e.g. RUNNING/STOPPED words, brighter = on).
- *Alarms:* redundantly coded by priority (colour + shape + text), a separate indicator next to the value;
  flashing only while unacknowledged.
- *Trends* embedded in the display (not trend-on-demand), with desirable ranges marked; usually
  ≤ 3-4 traces. Exception: many identical units on one trend so the odd one out stands out.
- *Pointers beat bars* (a bar near zero disappears; a pointer is still visible).
- *No* 3D, animation (spinning pumps), colour-coded pipes or big unit callouts.
- *Display hierarchy:* L1 overview of the whole span of control (KPIs, no control actions), L2 unit
  control, L3 unit detail, L4 diagnostics. Consistent navigation between them.
- *Abnormal-situation graphics* for specific procedures help more than general screens.

**Evidence.** EPRI simulator test with experienced power-plant operators: HP graphics improved detection
of abnormal situations (often before alarms), diagnosis and response. Operators who had used HP graphics
then found many faults in their old ones; operators who hadn't saw nothing wrong. A lack of complaints
doesn't mean a good HMI.

**Work process:** philosophy/style guide, benchmark existing displays, define goals, task analysis,
design, deploy/train, maintain.
