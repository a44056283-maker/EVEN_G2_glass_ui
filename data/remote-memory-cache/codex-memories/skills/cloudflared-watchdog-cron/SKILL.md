---
name: cloudflared-watchdog-cron
description: Run and verify the workspace-tianlu watchdog cron when a task mentions `cloudflared-watchdog.sh`, heartbeat巡检, or “只在异常时打扰”.
argument-hint: "[workspace-cwd]"
user-invocable: false
allowed-tools:
  - Bash
  - Read
  - Grep
---

# cloudflared-watchdog-cron

## When to use

Use this for `/Users/luxiangnan/.openclaw/workspace-tianlu` heartbeat or cron-style checks that need to execute `/Users/luxiangnan/edict/scripts/cloudflared-watchdog.sh`, verify the result, and record it in the daily memory file.

Do not use this for:
- unrelated network debugging that already has a failing symptom to investigate
- code edits to the watchdog script
- environments where the script path or daily-memory layout differs materially

## Inputs / context to gather

1. Confirm the working directory is the workspace root, or use `$ARGUMENTS` as the workspace path.
2. Read `SOUL.md`, `USER.md`, and the current `memory/YYYY-MM-DD.md` when available.
3. Confirm the active daily log target in `memory/YYYY-MM-DD.md`.
   - Older runs used `## Cloudflared Watchdog`.
   - The latest same-day rows may instead live under `## 工部`.

## Procedure

1. Restore workspace context.
   - Read `SOUL.md`, `USER.md`, and the current daily memory file before running the watchdog.
2. Run the exact watchdog command.
   - `bash /Users/luxiangnan/edict/scripts/cloudflared-watchdog.sh`
   - If you need an explicit success capture, use `bash /Users/luxiangnan/edict/scripts/cloudflared-watchdog.sh; printf '\nEXIT_CODE=%s\n' "$?"`
3. Verify the normal-success shape.
   - Expect `EXIT_CODE=0`
   - Expect the short line `[看门狗] 检查完成. 近1h断线次数: 0`
   - Also run `launchctl print gui/$(id -u)/com.cloudflare.cloudflared` and expect `state = running`; in this workflow, the script result and the LaunchAgent state are both part of the default proof set.
4. Update the daily memory file when the workflow expects it.
   - Append or prepend a timestamped line under the active watchdog section in `memory/YYYY-MM-DD.md`
   - Include the script path, exit code, and one-hour disconnect count
   - If `rg` is unavailable in this shell, use `grep -n -E 'Cloudflared Watchdog|工部|HH:MM 定时看门狗' memory/YYYY-MM-DD.md` to confirm the new line
   - Do not rely on file `mtime` alone; confirm the exact timestamped row was written with `grep` or a narrow `sed` window.
5. Report back concisely.
   - For healthy runs, stay brief
   - Preserve the workspace naming rule from `SOUL.md`: call the father “爸” or “父亲”, never “大哥”
6. If stronger proof is needed, deepen past the default checks.
   - Recount the last-hour disconnects from `/Users/luxiangnan/Library/Logs/com.cloudflare.cloudflared.err.log`
   - Use this instead of assuming extra watchdog state files should exist.

## Efficiency plan

1. Use the exact known script path instead of rediscovering an entrypoint.
2. For routine checks, stop once you have the exit code, the short watchdog line, the `launchctl` state, and the memory append.
3. Follow the process rule “只在异常时打扰”: do not expand into extra investigation unless the watchdog is abnormal.

## Pitfalls and fixes

- Symptom: watchdog reports disconnects or exits non-zero.
  - Likely cause: real connectivity or daemon issue.
  - Fix: switch from routine logging to investigation immediately; do not write a normal-success summary.
- Symptom: the script exits `0` but the daemon state is uncertain.
  - Likely cause: stdout only proves the wrapper completed.
  - Fix: require `launchctl print gui/$(id -u)/com.cloudflare.cloudflared` in the default proof set before closing the run.
- Symptom: the run succeeded but there is no entry in `memory/YYYY-MM-DD.md`.
  - Likely cause: the bookkeeping step was skipped.
  - Fix: patch the active watchdog section immediately after the command result is known; if the row is not where expected, check both `## 工部` and `## Cloudflared Watchdog`.
- Symptom: `memory/YYYY-MM-DD.md` mtime changed but the expected watchdog row is still missing.
  - Likely cause: another edit touched the file or the append landed somewhere unexpected.
  - Fix: verify the exact `HH:MM 定时看门狗` line with `grep`/`sed`; do not treat mtime alone as proof.
- Symptom: `/tmp/cloudflared-watchdog.state` is missing during a healthy run.
  - Likely cause: that state file is only written on alert-threshold runs.
  - Fix: use the script output plus `launchctl` state and the daily-memory row as the proof set.
- Symptom: a quick Python one-liner against `/metrics` throws `SyntaxError` even though the endpoint is healthy.
  - Likely cause: raw metrics text was piped into `python -` as source code.
  - Fix: fetch `http://127.0.0.1:20241/metrics` inside Python with `urllib.request`, or inspect the raw body directly instead of piping it into Python source.
- Symptom: `zsh:1: command not found: rg` while locating or verifying the daily log entry.
  - Likely cause: this shell does not have ripgrep installed.
  - Fix: switch directly to `grep -n -E` for section lookup and line verification.
- Symptom: reply wording drifts in this workspace.
  - Likely cause: `SOUL.md` naming rule was not restored first.
  - Fix: reload local context and preserve “爸” / “父亲”, never “大哥”.

## Verification checklist

- The command used `/Users/luxiangnan/edict/scripts/cloudflared-watchdog.sh`.
- Exit code was `0` for a healthy run.
- Output included `近1h断线次数: 0` for a healthy run.
- `launchctl print gui/$(id -u)/com.cloudflare.cloudflared` showed `state = running`.
- `memory/YYYY-MM-DD.md` was updated under the active watchdog section when required.
- The exact timestamped watchdog row is present, not just a changed file mtime.
- The final report stayed concise unless an anomaly required escalation.
