# Architecture

## Layers
1. Desktop UI
2. Brain Runtime
3. AI Provider Adapter
4. Planner / Context / Memory / Personality
5. Tool Router
6. Permission Engine
7. Local Agent Runtime
8. Verifier
9. Event Bus
10. Persistence

## Execution priority
API > CLI > Browser automation > GUI automation > Computer Use.

## Core loop
User → Context → Cloud LLM → structured tool call → validation → permission → executor → verifier → result → LLM → response.

Cloud LLM is not an executor.
