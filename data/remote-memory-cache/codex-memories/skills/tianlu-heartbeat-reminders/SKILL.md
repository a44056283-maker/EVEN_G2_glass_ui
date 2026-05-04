---
name: tianlu-heartbeat-reminders
description: Handle recurring `workspace-tianlu` reminder runs when the cues are `HEARTBEAT.md`, `HEARTBEAT_OK`, `pending_approvals.json`, `aggregator.py`, `news_crawler.py`, or `trade_journal.py`.
argument-hint: "[workspace-cwd] [command]"
disable-model-invocation: true
user-invocable: false
allowed-tools:
  - Bash
  - Read
  - Grep
---

# tianlu-heartbeat-reminders

## When to use

Use this for `/Users/luxiangnan/.openclaw/workspace-tianlu` internal heartbeat/reminder runs that need to:
1. restore local reminder policy from `HEARTBEAT.md`
2. check whether approvals are pending
3. run a named scheduled script such as `aggregator.py`, `news_crawler.py`, or `trade_journal.py`
4. confirm the dated memory log was updated
5. return `HEARTBEAT_OK` only when the policy says nothing needs attention

Do not use this for:
- interactive user-facing reminder delivery
- debugging the underlying crawler or journal code in depth
- workflows outside `workspace-tianlu` with different reminder policy files

## Inputs / context to gather

1. Confirm the workspace root, using `$ARGUMENTS[0]` if provided; otherwise use `/Users/luxiangnan/.openclaw/workspace-tianlu`.
2. Read `HEARTBEAT.md` first.
3. Check the current dated memory file `memory/YYYY-MM-DD.md`.
4. Identify the scheduled command to run from `$ARGUMENTS[1]` or the task instructions.

## Procedure

1. Restore reminder policy.
   - Read `HEARTBEAT.md`.
   - Confirm whether the policy says routine reminders stay internal and whether the no-action reply should be `HEARTBEAT_OK`.
2. Check approvals before doing anything else.
   - Inspect `pending_approvals.json` or the task’s stated approvals source.
   - If pending work exists, do not use the routine-success path.
3. Run the scheduled script directly.
   - Common proven commands:
   - `/opt/homebrew/bin/python3 aggregator.py && /opt/homebrew/bin/python3 ../monitor_sentiment.py`
   - `/opt/homebrew/bin/python3 /Users/luxiangnan/edict/scripts/qintianjian/news_crawler.py`
   - `/opt/homebrew/bin/python3 /Users/luxiangnan/freqtrade_console/trade_journal.py`
4. Verify the real outputs.
   - Confirm the dated memory file `memory/YYYY-MM-DD.md` was updated.
   - For aggregator runs, also confirm `/Users/luxiangnan/.sentiment_latest.json` exists or refreshed when that output is expected.
5. Finish according to policy.
   - If approvals are still clear and the reminder required no user delivery, keep it internal and use `HEARTBEAT_OK` when the policy requires it.

## Efficiency plan

1. Start with `HEARTBEAT.md` and approvals state; those decide whether the run is routine.
2. Do not re-derive the command set if the reminder already names the script.
3. For repetitive runs, stop once you have policy confirmation, command completion, and proof of the dated-memory update.

## Pitfalls and fixes

- Symptom: `aggregator.py` shows a traceback around `market_crawler.py:248`.
  - Likely cause: known intermittent market-crawler failure.
  - Fix: verify whether `/Users/luxiangnan/.sentiment_latest.json` and the dated memory log still updated before escalating.
- Symptom: a reminder is about to be surfaced to the user even though nothing is pending.
  - Likely cause: `HEARTBEAT.md` policy was not restored first.
  - Fix: re-read `HEARTBEAT.md` and keep the run internal unless the reminder explicitly requires user delivery.
- Symptom: the scheduled command ran but there is no dated memory entry.
  - Likely cause: the bookkeeping step was skipped.
  - Fix: update `memory/YYYY-MM-DD.md` before closing the run.

## Verification checklist

- `HEARTBEAT.md` was read before treating the run as routine.
- Approval state was checked.
- The named scheduled command actually ran.
- `memory/YYYY-MM-DD.md` was updated when the workflow expected it.
- For aggregator runs, `/Users/luxiangnan/.sentiment_latest.json` was checked when relevant.
- `HEARTBEAT_OK` was used only when the policy said no attention was needed.
