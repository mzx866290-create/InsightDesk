# Deck And Delivery Plan

## Scope

This document replaces the scattered PPT redesign notes with a single delivery-focused plan.

## Core Conclusion

The project should treat report/deck generation as a structured delivery pipeline, not as a one-shot markdown-to-ppt conversion flow.

## Recommended Model

Preferred pipeline:

1. source selection
2. deck planning
3. deck drafting
4. human review/edit
5. export rendering

## Why This Matters

If the system only emits markdown or directly renders slides from chat history:

- per-slide editing is weak
- evidence tracking is weak
- regeneration is too coarse
- export quality becomes fragile

## Current Good Foundation

The project already has:

- deck generation
- deck persistence
- deck editing UI
- `PPTX` export
- report preview path

That means the project is beyond the idea stage. The next step is refinement, not reinvention.

## Recommended Product Principles

- keep content generation and slide rendering separate
- make evidence references first-class
- support partial regeneration
- keep review status visible per slide

## Near-Term Plan

### Phase 1

- keep current deck structure
- strengthen source-grounded slide metadata
- improve editor review loop

### Phase 2

- improve single-slide regeneration
- improve evidence quality handling
- improve deck preview fidelity

### Phase 3

- consider a dedicated rendering/export service if fidelity becomes a bottleneck
- expand to richer export targets such as PDF or shareable web deck

## Engineering Direction

Focus areas:

- `deck_service.py`
- `frontend/src/components/reports/*`
- export contract stability
- evidence/source registry consistency

## Risks

- letting LLM output directly dictate slide layout
- skipping the review layer
- treating export as the main source of truth instead of the deck spec/state
