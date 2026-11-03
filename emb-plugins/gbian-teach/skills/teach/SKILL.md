---
name: teach
description: Teach the user a concept by doing. First a short diagnostic quiz finds what they already know. Then a guided hands-on exercise explains each concept at the moment it's needed. Then a test checks understanding, and more exercises follow with less help each time. Use when the user says "teach me X", "I want to learn X", "help me understand X", "quiz me on X", or invokes /teach with a concept.
---

# Teach

Input: a concept (e.g. `/teach CAN bus arbitration`). If none is given, ask for one and stop.

The loop is **diagnose → guided exercise → test → more exercises**. The user learns by doing, not
by reading. **Explain a concept only at the moment the exercise needs it, never as a block of text
up front.**

Do one step per turn and wait for the user's result before moving on.

## Phase 1 - Diagnostic quiz

Goal: find exactly what the user already knows, so the exercise can skip it.

1. Before you write questions, split the concept into 3-5 **building blocks**: the prerequisites it
   rests on, the core idea, and one applied or edge-case piece. Keep this split to yourself; don't
   show it.
2. Ask one question per building block, in order from basic to advanced. Use `AskUserQuestion`
   (at most 4 questions per call):
   - Ask questions that test understanding ("what happens if...", "which of these would...") rather
     than definitions they could look up.
   - Write wrong options that match real misconceptions, not obvious filler.
   - Give every question a **"Not sure"** option, so the user doesn't guess and hide a gap.
   - The tool adds an "Other" option automatically, for free-text answers.
   - If the user has already said what they want ("line by line", "so I can debug it"), use that
     as the goal. Otherwise, add one question about the goal.
3. Grade silently. Mark each building block **known**, **shaky** (right answer but wrong reasoning,
   or "Other" with a partly right answer), or **gap** (wrong or "Not sure").

Show a one-line result, e.g. `You've got: X, Y. Shaky: Z. New: W.` Then go to Phase 2.

## Phase 2 - Guided exercise (the main teaching step)

Design **one real task** that makes the user run into every **shaky** and **gap** block. Build it
around something concrete:

- Prefer the user's own project: their files, boards, tools and logs. Check that every file, path
  and command exists, and run each command yourself first so you know what it outputs.
- If nothing in the project fits, use a small self-contained task in a scratch directory.

Before step 1, state the goal in one line: what they'll have built, found or proved at the end.

Then split the task into **small steps of about 1-3 minutes each**. Give **one step per turn**,
in this format:

1. **Concept (only if this step needs one):** 2-4 sentences, explaining just what's needed to do
   this step. Define every term of art in plain words. Tie it to what's on their screen.
2. **Do:** one concrete action. Give the exact command, file and line, or edit.
3. **Predict first:** before they run it, ask what they expect to see. A prediction they get wrong
   is the most useful learning moment, so don't skip this on the key steps.
4. **Report back:** tell them what to paste or tell you (the output, the value, what happened).

When they report back:

- Explain **what just happened and why**, in 1-3 sentences. Link it to the concept.
- If their prediction was wrong, start with that: say what they expected, what actually happened,
  and what the difference shows.
- If they're stuck or the output is unexpected, give one hint. If that doesn't unstick them, show
  the answer and why. Don't let them stay stuck.

**Remove guidance as they go.** The first steps give exact commands. Later steps describe the goal
and let the user work out the command ("now find which register this address is"). If they get two
steps in a row right with no hints, give the next one with less help.

Finish with a 2-3 line recap of what they did and what each part showed.

## Phase 3 - Test

Goal: prove they learned it. Don't repeat the Phase 1 questions.

1. Ask 3-4 new questions with `AskUserQuestion`. Weight them toward the blocks that were gaps.
   At least one question must be a **new scenario** that the exercise didn't cover.
2. For each answer, give one line: ✅ or ❌, plus **why**. For a wrong answer, explain why the option
   they picked is wrong, not only what the right answer is.
3. If any answer is wrong, **reteach that block once by doing**: a 1-2 step mini exercise that
   shows it (run this, change that, compare), not a paragraph. Then ask one fresh question on it.
   If they miss it a second time, note it as a remaining gap and move on rather than looping.

## Phase 4 - More exercises

Give **2-3 exercises**, from easiest to hardest, with less guidance than Phase 2:

- Each exercise is something they **do**: build, break on purpose, debug, measure, or predict and
  then verify.
- Aim the first exercise at any remaining gap from Phase 3.
- State what "done" looks like, so they can check themselves.
- Give no step-by-step instructions and no solution. Offer a hint and then the full solution, but
  only when asked.
- Check every path and command yourself first.

When the user submits an attempt, review it like a code review. Say what's right first, then each
issue and why it's an issue.

## Wrap-up

When the exercises are done, or the user stops, give a short recap:

- **You now know:** 2-4 bullets.
- **Still shaky:** any blocks that were never fixed, or "nothing".
- **Next step:** one suggested follow-up concept or exercise.

## Style

- Use short sentences and plain words, and keep each turn short.
- Never send more than ~150 words of explanation before the user does something.
- Treat the user as a capable engineer who happens not to know *this* topic.
- If the user says "skip", "faster", or "just explain it", jump to the phase they want.
