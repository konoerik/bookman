Take stock of where the project is and whether it's still pointed at the right thing.

1. Read docs/CONTEXT.md, docs/PLAN.md (## Active and ## Done), and the ## Quick Reference section of docs/ARCHITECTURE.md.

2. In 2–3 sentences, summarize: what the project set out to do, and what it has actually been doing lately. Be factual, not evaluative.

3. Then ask these three questions together — don't wait for answers one at a time:

   - **Right problem?** Is what we're building still solving the problem we originally set out to solve?
   - **Off track?** Is there anything we've spent real time on that, in hindsight, wasn't the point?
   - **Avoiding something?** Is there something we keep not doing that is probably the actual next thing?

4. After I respond, do one of the following based on what I say:

   - **If the direction has shifted unintentionally:** Help me refocus. Update docs/PLAN.md ## Active to reflect the real next thing, and update docs/CONTEXT.md **Next action** to match.

   - **If the direction has shifted intentionally (a pivot):** Treat it as a decision. Run /log to record it as an ADR, then update docs/CONTEXT.md to reflect the new direction.

   - **If we're on track:** Say so clearly, in one sentence. No need to change anything.

Keep the tone curious, not corrective. This is a gut-check, not a postmortem.
