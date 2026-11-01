# Endsley (1995): Toward a theory of situation awareness in dynamic systems
*Human Factors 37(1), 32-64. Paraphrased summary for display design.*

**Model.** Situation awareness (SA) is the reader's knowledge of a changing situation, in three levels:
1. **Perception (L1):** noticing the relevant elements and their state (e.g. a fault bit is set).
2. **Comprehension (L2):** what those elements mean together, against the reader's goals
   (e.g. MCU is hot *and* rising, so it's not a sensor glitch).
3. **Projection (L3):** where it is heading in the near future (e.g. it will reach the trip limit soon).

SA is separate from the decision and the action that follow. Good SA doesn't guarantee good
decisions, but poor SA makes them likely to go wrong.

**Limits that drive design.** Attention and working memory are scarce. Experts get around them with
mental models: they recognise patterns from a few critical cues. Displays that make readers compute
L2/L3 in their heads (compare a number to a remembered limit, estimate a slope) load working memory
exactly when it's scarce, under stress, when attention also narrows onto a few cues.

**Design implications we use:**
- Present information already integrated for L2/L3 (value *against its band*, trend *toward a limit*), not raw data.
- Organise by the reader's goals; keep what one goal needs together.
- Make the critical cues salient; reserve salience for them and avoid it for non-critical things.
- Always provide a **global overview** (the health row) next to detail, so narrowed attention still sees new problems.
- Filter out what serves no goal, but don't hide what is relevant behind navigation.
- Help projection with trends and limits, especially for less-experienced readers.
- Support parallel processing (e.g. visual display + voice on the radio).

**Errors to design against.** L1: the signal wasn't available or wasn't noticed (no panel, buried, same
colour as normal). L2: data seen but its meaning missed (no reference band). L3: no help seeing where it is going.
Use **goal-directed task analysis** to decide what goes on a display: for each goal, list L1, L2 and L3 requirements.
