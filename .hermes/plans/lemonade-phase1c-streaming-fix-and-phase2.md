# Plan: lemonade phase1c streaming fix and phase2 control

## Goal
Fix visible progressive streaming in the conversation agent, then implement real Home Assistant control via LLM tools.

## Tasks
1. [in_progress] Inspect current conversation streaming implementation and compare against prior working agent streaming logic.
2. [pending] Patch conversation.py so SSE deltas are emitted progressively instead of buffered into near-final chunks.
3. [pending] Run smoke checks and review diff.
4. [pending] Investigate existing llm/tool integration surfaces in repo for HA control.
5. [pending] Implement minimal Phase 2 control path using HA ChatLog/LLM API tools.
6. [pending] Verify with smoke checks and git status.

## Notes
- User validated install/release path, reasoning cleanup, stability, and services.
- User reported streaming is not visibly progressive.
- Prefer minimal conservative changes over large refactors.
- Real HA control should use Home Assistant llm/chat_log tools, not legacy orphan MCP code unless required.
