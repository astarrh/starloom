# Phase 02 — Culture and Naming Core

## Development Objectives
- Implement culture construction paths and drift mechanics.
- Implement naming orchestration that consumes weighted cultures consistently.
- Provide standalone deterministic name generation utility for runtime use.

## Milestone Alignment
- 3. Implement culture system (`create_culture()`, `create_culture_family()`, `generate_culture_family()`, Markov model, drift).
- 4. Implement naming engine with culture delegation and tests.
- 10. Implement `generate_name()` utility with tests.

## Expected Outcomes
- Culture objects and CultureSpec serialization path are consistent and tested.
- Name generation is deterministic when seeded and behaves clearly when unseeded.
- Naming APIs are ready for integration into world-generation stages.
