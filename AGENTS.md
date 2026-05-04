# AGENTS.md - Tianlu G2 Ops Assistant

## Non-Negotiable Rules

1. Phone Web UI and G2 Glass UI are separate. Do not use HTML/CSS layout as the glasses UI.
2. G2 Glass UI must be rendered through Even Hub SDK containers via `GlassRenderer`.
3. The glasses display target is 576 x 288 px. Keep pages to 8-10 lines where possible.
4. Use TL OS futuristic HUD text style, but prioritize readability on real glasses.
5. R1 input must be debugged through envelope/type/source logs before relying on source filtering.
6. R1 camera control must use a pre-warmed phone camera stream. R1 must not trigger permission prompts.
7. G2 microphone main path is `bridge.audioControl(true)` -> `event.audioEvent.audioPcm` -> WebSocket -> backend ASR.
8. Browser `SpeechRecognition` / `webkitSpeechRecognition` cannot be the main voice path.
9. Frontend must only talk to the G2 Bridge/API backend. Never call OpenCLAW localhost from frontend code.
10. All API keys stay in backend environment variables. Never bundle secrets in frontend code.
11. Trading bot actions are read-only in v1. Do not implement real order placement, closing positions, leverage changes, strategy changes, or withdrawals.
12. ASR not configured must return a clear not-configured state. Do not fake real ASR unless mode is explicitly `mock-asr`.
13. `/ask` must return local fallback if OpenCLAW is disabled, unavailable, or times out.
14. Every phase must output changed files, tests performed, results, and remaining risks.

## Preferred Implementation Order

0. Repo audit
1. GlassRenderer
2. Input debug
3. R1 camera control
4. G2 mic probe
5. ASR adapter
6. `/ask` and trading fallback
7. Vision modes
8. Diagnostics and runbook
9. Tests and pack

## Current Repository Note

The execution manual names the backend `services/g2-bridge`; this repository currently uses `services/api-server` for the same bridge role.
