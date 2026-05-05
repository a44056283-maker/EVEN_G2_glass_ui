# Memory Restore + v0.5.12 Verification Report

Generated: 2026-05-05 15:30

## Restored Context

- Claude project memory restored from `~/.claude/projects/-Users-luxiangnan-Desktop-EVEN-G2---------/memory/`.
- Codex imported-session index restored from `~/.codex/session_index.jsonl` and `~/.codex/external_agent_session_imports.json`.
- Current project stage restored as:
  - `P0 CORE TRUE_DEVICE PASSED`
  - `P1-STABILIZE-001` in progress
  - Previous local work item: `P1-OPENCLAW-HISTORY-TRADING-PRICES-001`

## Local Work Continued

### OpenCLAW token precedence

File: `services/api-server/src/openclaw.ts`

- Keeps token selection as `OPENCLAW_GATEWAY_TOKEN ?? OPENCLAW_TOKEN`.
- This preserves the gateway-token first contract required for deployment.
- Treats gateway timeout / no-answer text as OpenCLAW unavailable instead of a valid answer.

File: `services/api-server/src/server.ts`

- `/openclaw/ask` now marks generic no-answer output as `provider: openclaw:unavailable`.
- This prevents the UI and test reports from treating a relay timeout as a successful OpenCLAW answer.

File: `scripts/gpt-advisor/test_openclaw_gateway.sh`

- Uses the same token precedence as the API server.
- Detects `200 OK` responses that still contain gateway relay timeout text and exits with code `2`.

### History fallback hardening

File: `apps/evenhub-plugin/src/history.ts`

- Keeps in-memory fallback history when `localStorage` write/read fails.
- Records last history error for UI display.
- Dispatches `g2vva:history-error` for diagnostics.
- Makes `clearHistory()` tolerant of `localStorage` failures.
- Renders error text through DOM `textContent` instead of `innerHTML`.

### Trading price display

File: `apps/evenhub-plugin/src/glass/glassScreens.ts`

- White-list price page uses fixed order:
  - BTC / ETH
  - SOL / BNB
  - DOGE
- Missing price displays as `--`.
- DOGE and prices under 1 use 4 decimals.

### Trading preset buttons

File: `apps/evenhub-plugin/src/main.ts`

- Phone preset buttons now fetch trading overview first when cache is empty.
- Glass trading menu is re-rendered after live white-list prices arrive.

## Verification

Commands:

```bash
npm --workspace apps/evenhub-plugin run typecheck
npm --workspace apps/evenhub-plugin run build
npm --workspace apps/evenhub-plugin run pack
```

Results:

- Typecheck: PASSED
- Build: PASSED
- Pack: PASSED
- API server typecheck: PASSED
- OpenCLAW auth probe: PASSED authentication, but agent relay still times out
- API server restarted through `launchctl kickstart -k gui/$(id -u)/com.tianlu.g2-vision-api`
- `/openclaw/ask` now returns `provider: openclaw:unavailable` for the current relay-timeout/no-answer condition.

## EHPK

- Version: `0.5.12`
- Size: `80119 bytes`
- SHA256: `3d7c2b76ea67109dbaa84a93f99f497ad3c8bd72a40028ffe39e6d178d6b0e41`
- Project path: `apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- Desktop backup: `/Users/luxiangnan/Desktop/g2-vision-voice-assistant-v0.5.12.ehpk`

## Remaining Manual Checks

1. Upload/install v0.5.12 EHPK on Even Hub.
2. Verify G2 white-list price page displays BTC/ETH/SOL/BNB/DOGE.
3. Verify phone trading preset buttons open the correct glass subpage after a fresh load.
4. Verify history still displays when WebView storage is unavailable or full.
5. Restart/verify the remote OpenCLAW gateway agent relay because `/v1/chat/completions` currently authenticates but returns `Gateway 暫時無法連線：The operation was aborted due to timeout`.
6. Test one real G2 OpenCLAW conversation path after relay restart.

## Notes

- `npm` was not available in the Codex shell path. A temporary official Node runtime was used only for verification and removed afterward.
- Existing P0 frozen flows were not intentionally changed.
