thread_id: 019dddf6-6d59-7bf2-9584-872b52ddef26
updated_at: 2026-04-30T12:34:27+00:00
rollout_path: /Users/luxiangnan/.codex/sessions/2026/04/30/rollout-2026-04-30T18-36-47-019dddf6-6d59-7bf2-9584-872b52ddef26.jsonl
cwd: /Users/luxiangnan/.openclaw/workspace-tianlu

# OpenClaw / Even G2 glasses access was restored in part, but the Even AI request path still needed model-route correction

Rollout context: workspace `/Users/luxiangnan/.openclaw/workspace-tianlu`; the user’s Even G2 glasses could not reach OpenClaw / OpenClaw reply delivery was failing. The conversation mixed public route health checks, OpenClaw gateway config, OcuClaw Even AI config, and diagnosing a failing eye-glasses request path.

## Task 1: Restore Even G2 / OpenClaw reachability and fix the glasses reply chain

Outcome: partial

Preference signals:

- The user first asked, “能修复一下吗？我这会儿眼镜访问不到open claw了。” -> future runs should treat this as a request to actively repair the live path, not just explain it.
- When the agent paused after a config change/restart attempt, the user interrupted with “你怎么了？” -> future runs should give short status updates quickly when a long restart or verification is in progress, because the user notices silence and wants confirmation.
- The user later pasted the key external evidence: domain, tunnel, `/health`, `/status`, `/api/health` all OK, plus one failure example from glasses, and asked “18点26分就是我发出的对话，但是眼镜没有收到。” -> future runs should prioritize the real glasses-to-agent delivery chain over generic local health checks.
- The user’s later message “⚡ Gateway 暫時無法連線：The operation was aborted due to timeout” indicates they care about end-user visible timeout symptoms and want that exact failure removed, not only background service health.

Key steps:

- Verified the public path first: `https://even2026.tianlu2026.org` returned `{"status":"ok","agent":"G2 Bridge","version":"5.0.0","gateway":true,"telegram":false}` and `/health` was healthy.
- Found the local OpenClaw gateway config was still loopback-bound: `openclaw gateway status` reported `Gateway: bind=loopback (127.0.0.1), port=18789` and `Loopback-only gateway; only local clients can connect.`
- Wrote `plugins.entries.device-pair.config.publicUrl=https://even2026.tianlu2026.org` into `~/.openclaw/openclaw.json`, but the broader problem remained because the gateway / app-server route still needed restart and the Even AI path had its own settings store.
- Confirmed the OcuClaw plugin was enabled and Even AI was on, but `openclaw.json` alone was not enough to fix the request path.
- Discovered a second config source: `~/.openclaw/even-ai-settings.json` contained `routingMode: "background"`, `defaultModel: "minimax2-7/MiniMax-M2.7-highspeed"`, `defaultThinking: "xhigh"`, and `listenEnabled: true`.
- The public G2 response path initially produced `500 internal error` upstream after the token was accepted; later log inspection showed the actual failure was a lane error: `Error: codex app-server startup aborted`, and a later run hit `unexpected status 404 Not Found: 404 page not found, url: https://api.minimaxi.com/v1/responses`.
- This tied the glasses failure to the Even AI route being sent to the wrong model/API, not the domain, tunnel, or raw gateway reachability.
- Edited `~/.openclaw/even-ai-settings.json` to switch `defaultModel` to `openai-codex/gpt-5.5` and `defaultThinking` to `medium` to move the route off the failing MiniMax endpoint and reduce latency risk.

Failures and how to do differently:

- A local POST to `http://127.0.0.1:18789/v1/chat/completions` kept returning `{"error":{"message":"Unauthorized","type":"unauthorized"}}` even after the token length was corrected, which showed that the local gateway path was not the right final validation target for the glasses flow.
- The rollout had multiple aborted restarts / partial command executions due to user interruption. Future runs should do one config change, one restart, one verification sequence, then report immediately before launching more long-lived checks.
- The first apparent root cause (“token length”) was incomplete. The more durable root cause was the `even-ai-settings.json` model routing default to MiniMax, which produced the 404 at `https://api.minimaxi.com/v1/responses`.
- `openclaw gateway restart` sometimes left the process alive but still serving the old settings or a loopback-bound service state; verify via `openclaw gateway status` and the actual public POST path, not just process existence.

Reusable knowledge:

- For this environment, public route health can be good while glasses replies still fail because the Even AI settings store is separate from `openclaw.json`.
- `~/.openclaw/even-ai-settings.json` is a real runtime input for OcuClaw Even AI routing; if glasses replies fail with model/API errors, inspect this file.
- The error `unexpected status 404 Not Found: 404 page not found, url: https://api.minimaxi.com/v1/responses` is a strong signal that the Even AI request was routed to the wrong provider/API, not merely that a token is wrong.
- `openclaw gateway status` is useful for determining whether the service is still loopback-only and whether the gateway is actually live.
- `openclaw gateway status` and public curl checks can both be green while the upstream model route is still broken; keep those as separate verification layers.

References:

- `openclaw gateway status` initially reported: `Gateway: bind=loopback (127.0.0.1), port=18789`; `Loopback-only gateway; only local clients can connect.`
- Public health response: `{"status":"ok","agent":"G2 Bridge","version":"5.0.0","gateway":true,"telegram":false}`
- Public Even AI failure response after token was accepted: `{"id":"g2-1777552386815",..."message":{"role":"assistant","content":"⚡ Gateway 暫時無法連線：Gateway 500: {\"error\":{\"message\":\"internal error\",\"type\":\"api_error\"}}"}}`
- Log line tying the failure to the wrong provider: `unexpected status 404 Not Found: 404 page not found, url: https://api.minimaxi.com/v1/responses`
- Log line tying the glasses session to a startup failure: `lane task error: lane=session:agent:main:openai-user:g2-glasses ... Error: codex app-server startup aborted`
- `~/.openclaw/even-ai-settings.json` before edit contained: `routingMode: "background"`, `defaultModel: "minimax2-7/MiniMax-M2.7-highspeed"`, `defaultThinking: "xhigh"`, `listenEnabled: true`
- Final edit applied: changed `defaultModel` to `openai-codex/gpt-5.5` and `defaultThinking` to `medium` in `~/.openclaw/even-ai-settings.json`
