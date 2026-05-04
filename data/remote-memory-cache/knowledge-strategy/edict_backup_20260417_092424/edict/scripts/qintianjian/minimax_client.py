#!/usr/bin/env python3
"""
钦天监 · MiniMax 多 Key 客户端
- 支持多 API Key 轮换
- 内置速率限制
- 自动重试
- Key 失效自动跳过
"""
import json
import time
import random
import logging
import urllib.request
import ssl
import urllib.error

logger = logging.getLogger("minimax_client")

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

# ── MiniMax API Keys（从配置文件读取）─────────────────
# 可以配置多个 key，客户端会自动轮换，失效的 key 会被跳过
MINIMAX_KEYS = [
    # 主要 key（从 openclaw.json 读取）
    "sk-cp-ZVNA89EW0MzpJJudReGfd6Ofp-J3Z2Er76Dgt0vDEyhkMtDk-JUwD2t7PvaVbHY9HIm59DYtC3snIA5FJwWtYOoTZLXyxK_eoKBYo27U508Fp84p9QUhvo0",
]
# 当前使用的 key index
_key_index = 0
# 失效 key 集合（当前 session 内跳过）
_dead_keys = set()


def _load_keys_from_config():
    """从 openclaw.json 加载 MiniMax key"""
    try:
        import json as _json
        cfg = _json.load(open("/Users/luxiangnan/.openclaw/openclaw.json"))
        providers = cfg.get("models", {}).get("providers", {})
        for pid, pconf in providers.items():
            if "minimax" in pid.lower():
                key = pconf.get("apiKey", "")
                if key and key not in MINIMAX_KEYS:
                    MINIMAX_KEYS.append(key)
    except Exception:
        pass


_load_keys_from_config()


def _get_next_key() -> str | None:
    """获取下一个可用 key"""
    global _key_index
    attempts = 0
    while attempts < len(MINIMAX_KEYS):
        idx = _key_index % len(MINIMAX_KEYS)
        _key_index += 1
        if idx not in _dead_keys:
            return MINIMAX_KEYS[idx]
        attempts += 1
    return None


# ── 速率限制 ───────────────────────────────────────────
_last_call = 0.0
_min_interval = 0.8  # 两次请求至少间隔 0.8 秒


def _rate_limit():
    global _last_call
    elapsed = time.monotonic() - _last_call
    if elapsed < _min_interval:
        time.sleep(_min_interval - elapsed)
    _last_call = time.monotonic()


# ── MiniMax API 调用 ───────────────────────────────────
def call_minimax(
    messages: list,
    model: str = "MiniMax-M2.5-highspeed",
    max_tokens: int = 1000,
    temperature: float = 0.3,
    timeout: float = 30.0,
    max_retries: int = 3,
) -> dict | None:
    """
    调用 MiniMax Chat API，支持多 key 轮换和自动重试。
    
    返回: {"ok": True, "content": "..."} 或 {"ok": False, "error": "..."}
    """
    _rate_limit()

    url = "https://api.minimaxi.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer placeholder",  # 临时占位
    }

    for attempt in range(max_retries + 1):
        key = _get_next_key()
        if key is None:
            logger.warning("[MiniMax] 所有 API Key 均失效")
            return {"ok": False, "error": "all keys exhausted"}

        headers["Authorization"] = f"Bearer {key}"

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
                resp = json.loads(r.read().decode("utf-8"))

            if "error" in resp:
                err = resp["error"]
                err_msg = err.get("message", str(err))
                err_code = err.get("code", "")

                # Key 无效 / 未授权 → 跳过此 key
                if err_code in (1004, "invalid_api_key", "Unauthorized") or "key" in err_msg.lower():
                    logger.warning(f"[MiniMax] Key 失效，跳过: {err_msg[:60]}")
                    _dead_keys.add(MINIMAX_KEYS.index(key))
                    continue

                # 限流 → 重试
                if err_code == 1002 or "rate" in err_msg.lower() or "limit" in err_msg.lower():
                    if attempt < max_retries:
                        delay = 2 * (2 ** attempt) + random.uniform(0, 2)
                        logger.warning(f"[MiniMax] 限流，{delay:.1f}s后重试: {err_msg[:60]}")
                        time.sleep(delay)
                        continue

                return {"ok": False, "error": err_msg}

            # 成功
            content = resp["choices"][0]["message"]["content"]
            return {"ok": True, "content": content, "usage": resp.get("usage", {})}

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            try:
                err_json = json.loads(body)
                err_msg = err_json.get("error", {}).get("message", str(e))
            except Exception:
                err_msg = str(e)

            # 401/403 → key 无效
            if e.code in (401, 403):
                logger.warning(f"[MiniMax] Key 认证失败({e.code}): {err_msg[:60]}")
                _dead_keys.add(MINIMAX_KEYS.index(key))
                continue

            # 429 → 限流，等一下再试
            if e.code == 429:
                if attempt < max_retries:
                    delay = 4 * (2 ** attempt) + random.uniform(0, 3)
                    logger.warning(f"[MiniMax] 429限流，{delay:.1f}s后重试")
                    time.sleep(delay)
                    continue
                return {"ok": False, "error": f"rate limited after {max_retries} retries"}

            # 5xx → 服务端错误，重试
            if 500 <= e.code < 600:
                if attempt < max_retries:
                    delay = 1.5 * (2 ** attempt)
                    logger.warning(f"[MiniMax] 服务端错误({e.code})，{delay:.1f}s后重试")
                    time.sleep(delay)
                    continue
                return {"ok": False, "error": f"server error {e.code}"}

            return {"ok": False, "error": err_msg}

        except Exception as e:
            error_str = str(e).lower()
            if attempt < max_retries and any(
                kw in error_str for kw in ["timeout", "connection", "reset", "network"]
            ):
                delay = 1.5 * (2 ** attempt) + random.uniform(0, 1.5)
                logger.warning(f"[MiniMax] 网络错误，{delay:.1f}s后重试: {e}")
                time.sleep(delay)
                continue
            return {"ok": False, "error": str(e)}

    return {"ok": False, "error": "max retries exceeded"}


# ── 批量调用（带速率控制）───────────────────────────────
def batch_call_minimax(
    prompts: list,
    model: str = "MiniMax-M2.5-highspeed",
    delay_between: float = 2.0,
    max_retries: int = 3,
) -> list:
    """
    批量调用 MiniMax，每次调用间隔 delay_between 秒。
    返回结果列表。
    """
    results = []
    for i, prompt in enumerate(prompts):
        messages = [{"role": "user", "content": prompt}]
        result = call_minimax(messages, model=model, max_retries=max_retries)
        results.append(result)
        if i < len(prompts) - 1:
            time.sleep(delay_between)
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    r = call_minimax([{"role": "user", "content": "Say hello in 3 words"}], max_retries=2)
    print(r)
