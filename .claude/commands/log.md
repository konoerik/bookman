Record an architectural decision in docs/ARCHITECTURE.md under ## Decisions (ADRs).

First, read docs/ARCHITECTURE.md to find the next ADR number.

Then ask me:
1. What is the decision? (title)
2. What was the context or problem?
3. What alternatives were considered?
4. What are the consequences or trade-offs?

Append to docs/ARCHITECTURE.md ## Decisions using this format:

### ADR-N: <Title>
**Date:** YYYY-MM-DD
**Context:** <Why this decision was needed>
**Decision:** <What was decided>
**Alternatives considered:** <What else was evaluated>
**Consequences:** <Trade-offs, follow-up work, or constraints introduced>

Also update docs/CONTEXT.md **Last session** to mention the decision was recorded.

If this decision involves a staged process with meaningful transitions (e.g. stub → critiqued → tested → implemented, or explore → keep/discard), ask whether to diagram it. If yes, append a Mermaid `stateDiagram-v2` block to docs/ARCHITECTURE.md `## Detail` capturing the stages and transitions.
