---
name: external-signals-cron-verify
description: Run and verify the workspace-tianlu P2 external-signals cron workflow when a task mentions `external_signals_fetcher.py`, `外部信号自动获取(P2)`, Gate fallback, or `external_signals.json`.
argument-hint: "[workspace-cwd]"
user-invocable: false
allowed-tools:
  - Bash
  - Read
  - Grep
---

# external-signals-cron-verify

## When to use

Use this for `/Users/luxiangnan/.openclaw/workspace-tianlu` cron-style runs that need to execute or verify `Knowledge/external_signals/external_signals_fetcher.py`.

Do not use this for:
- unrelated cron tasks
- code edits to the fetcher itself
- environments where the workspace path or output path differs materially

## Inputs / context to gather

1. Confirm the working directory is the workspace root, or use `$ARGUMENTS` as the workspace path.
2. Check whether `SOUL.md`, `USER.md`, and `memory/YYYY-MM-DD.md` exist in the workspace and read them first when available.
3. Confirm the output target is `Knowledge/external_signals/external_signals.json`.

## Procedure

1. Restore workspace context.
   - Read `SOUL.md`, `USER.md`, and the current `memory/YYYY-MM-DD.md` before running the cron task.
2. Run the fetcher from the workspace root.
   - `python3 Knowledge/external_signals/external_signals_fetcher.py`
3. Verify persisted output instead of trusting exit code alone.
   - Fast path: `python3 Knowledge/external_signals/external_signals_fetcher.py --status`
   - Compact schema gate: `jq -e '.fetch_time and .funding_rate and .long_short_ratio and .fear_greed and (.alerts | type == "array")' Knowledge/external_signals/external_signals.json >/dev/null`
   - Strong proof: `python3 -m json.tool Knowledge/external_signals/external_signals.json >/dev/null`
   - Targeted field proof: `jq '.funding_rate, .long_short_ratio, .fear_greed, .alerts' Knowledge/external_signals/external_signals.json`
   - File freshness: `stat -f '%Sm %z %N' -t '%Y-%m-%d %H:%M:%S %Z' Knowledge/external_signals/external_signals.json`
4. Check saved source tags per signal, not as one binary status.
   - Inspect `funding_rate.exchange`, `long_short_ratio.exchange`, and any `source_note` fallback markers in the saved JSON.
   - Treat full Gate fallback, partial Binance recovery, and full Binance success as distinct outcomes.
5. Update the daily memory file when the workflow expects it.
   - Append the result to `memory/YYYY-MM-DD.md`.
   - Do not assume the fetcher auto-appended the log; verify the section after the JSON checks and patch it manually if needed.
   - In the common `## 外部信号` layout, prepend the newest line so the latest proof stays at the top.
6. Report back concisely.
   - Include `Binance` status, whether `Gate` fallback worked, `alerts`, and file freshness.

## Efficiency plan

1. Start with `--status` if the task is verification-only and does not require a fresh fetch.
2. Use `jq` plus `stat` as the default proof pair; do not reopen large files or over-explore the code unless verification fails.
3. If you only need to prove the persisted artifact is structurally complete, prefer `--status` + the `jq -e` schema gate + `stat` before reaching for longer `jq` dumps.
4. Stop once you have:
   - confirmed the output file exists and refreshed
   - confirmed fallback markers or primary-source values
   - recorded the daily memory update when applicable

## Pitfalls and fixes

- Symptom: `No route to host` from Binance.
  - Likely cause: environment/network reachability issue.
  - Fix: treat it as non-blocking if Gate fallback populated `external_signals.json`.
- Symptom: one signal comes from `binance` but another still comes from `gate`.
  - Likely cause: upstream recovery is partial; the fetcher does not have one shared reachability state for all fields.
  - Fix: report the saved per-field `exchange` values independently and make the daily-memory note explicit about which field recovered and which still used fallback.
- Symptom: a `jq` probe for `fear_greed_index` or `market_sentiment` comes back missing.
  - Likely cause: the persisted file's real top-level keys are `alerts`, `fear_greed`, `fetch_time`, `funding_rate`, and `long_short_ratio`.
  - Fix: inspect `fear_greed` and the actual top-level keys before deciding the JSON shape is wrong or the fetch failed.
- Symptom: a broad mixed `jq` pipeline errors even though the saved file is valid.
  - Likely cause: the probe mixed `keys` with field reads or included old paths like `fear_greed_index`.
  - Fix: use `--status` first, then inspect `jq 'keys'` or targeted real paths such as `.funding_rate`, `.long_short_ratio`, `.fear_greed`, and `.alerts`.
- Symptom: exit code `0` but uncertain whether output refreshed.
  - Likely cause: console success text without a persistence check.
  - Fix: inspect `external_signals.json` with `jq` and confirm mtime/size with `stat`.
- Symptom: `external_signals.json` refreshed but the daily memory file has no new line.
  - Likely cause: this fetcher run did not auto-append the cron result.
  - Fix: treat JSON verification and memory writeback as separate gates; patch `memory/YYYY-MM-DD.md` manually and verify the new line landed in the expected section.
- Symptom: values look stale.
  - Likely cause: read happened before the file rewrite completed or the wrong file path was checked.
  - Fix: re-check the workspace root, rerun `--status`, and verify `Knowledge/external_signals/external_signals.json`.
- Symptom: a combined zsh command stops before the follow-up validation runs.
  - Likely cause: `status` is a read-only variable name in zsh.
  - Fix: use `exit_code` or another non-reserved variable name when capturing the fetcher result before `ls`, `python3 -m json.tool`, or `jq`.

## Verification checklist

- `Knowledge/external_signals/external_signals.json` exists.
- `jq` shows `funding_rate`, `long_short_ratio`, `fear_greed`, and `alerts`.
- `funding_rate.exchange` and `long_short_ratio.exchange` were checked explicitly, along with any `source_note` fallback markers.
- File mtime/size reflect the latest run.
- If Binance failed for a field, the saved JSON shows the matching Gate fallback markers for that field.
- The daily memory file was updated when the cron workflow requires it.
- If the memory section exists, the newest cron line is visible in the expected section after the run.
