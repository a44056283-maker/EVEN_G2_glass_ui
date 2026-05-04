#!/usr/bin/env python3
"""
钦天监 · HTTP 请求工具箱
- 重试机制（指数退避）
- 速率限制（避免触发 RPM）
- 错误分类（可重试 vs 不可重试）
"""
import time
import random
import logging
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import ssl

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

logger = logging.getLogger("retry_utils")


# ── 速率限制器 ─────────────────────────────────────────
class RateLimiter:
    """简单令牌桶：两次请求间隔 min_interval 秒"""

    def __init__(self, min_interval: float = 1.0):
        self.min_interval = min_interval
        self._last_call = 0.0

    def wait(self):
        """等待足够时间（如果需要）"""
        elapsed = time.monotonic() - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.monotonic()


# ── 全局限速器 ─────────────────────────────────────────
# 默认：每秒最多 2 个请求（MiniMax RPM 安全线）
_global_limiter = RateLimiter(min_interval=0.5)


def set_global_rate(requests_per_second: float):
    global _global_limiter
    _global_limiter = RateLimiter(min_interval=1.0 / requests_per_second)


# ── 可重试错误判断 ─────────────────────────────────────
RETRYABLE_ERRORS = {
    "timeout",
    "timed out",
    "connection reset",
    "connection refused",
    "network",
    "temporarily",
    "unavailable",
    "429",
    "500",
    "502",
    "503",
    "504",
    "1002",  # MiniMax: 请求频率超限
    "1033",  # MiniMax: 系统错误
}


def is_retryable(error_msg: str) -> bool:
    """判断错误是否应该重试"""
    msg = error_msg.lower()
    for pattern in RETRYABLE_ERRORS:
        if pattern in msg:
            return True
    return False


# ── 带重试的 HTTP GET ──────────────────────────────────
def http_get_with_retry(
    url: str,
    headers: dict = None,
    timeout: float = 8.0,
    max_retries: int = 4,
    base_delay: float = 1.5,
    max_delay: float = 32.0,
    rate_limit: bool = True,
    headers_only: bool = False,
) -> str | None:
    """
    发送 GET 请求，失败时自动重试（指数退避）。
    
    参数:
        url: 目标 URL
        headers: 请求头
        timeout: 单次请求超时（秒）
        max_retries: 最大重试次数
        base_delay: 基础退避时间（秒）
        max_delay: 最大退避时间（秒）
        rate_limit: 是否启用全局速率限制
    
    返回:
        响应内容（str）或 None（全部失败）
    """
    if rate_limit:
        _global_limiter.wait()

    headers = headers or {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    for attempt in range(max_retries + 1):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout, context=CTX) as r:
                if headers_only:
                    # 只验证连接，不读body
                    return ""
                return r.read().decode("utf-8", errors="replace")

        except Exception as e:
            error_str = str(e).lower()
            is_last = attempt >= max_retries
            is_retryable_err = is_retryable(error_str)

            if is_last or not is_retryable_err:
                logger.warning(f"[HTTP] {url} 失败（不重试）: {e}")
                return None

            # 指数退避 + 抖动
            delay = min(base_delay * (2 ** attempt), max_delay)
            jitter = random.uniform(0, delay * 0.3)
            sleep_time = delay + jitter
            logger.debug(f"[HTTP] {url} 失败，{sleep_time:.1f}s后重试({attempt+1}/{max_retries}): {e}")
            time.sleep(sleep_time)

    return None


# ── 带重试的 HTTP POST ────────────────────────────────
def http_post_with_retry(
    url: str,
    data: bytes | dict,
    headers: dict = None,
    timeout: float = 10.0,
    max_retries: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 16.0,
    rate_limit: bool = True,
) -> str | None:
    """POST 请求，失败时自动重试（指数退避）。"""
    if rate_limit:
        _global_limiter.wait()

    if isinstance(data, dict):
        import json
        data = json.dumps(data).encode("utf-8")
        headers = headers or {}
        headers.setdefault("Content-Type", "application/json")

    headers = headers or {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    for attempt in range(max_retries + 1):
        try:
            req = Request(url, data=data, headers=headers, method="POST")
            with urlopen(req, timeout=timeout, context=CTX) as r:
                return r.read().decode("utf-8", errors="replace")

        except Exception as e:
            error_str = str(e).lower()
            is_last = attempt >= max_retries
            is_retryable_err = is_retryable(error_str)

            if is_last or not is_retryable_err:
                logger.warning(f"[HTTP] POST {url} 失败（不重试）: {e}")
                return None

            delay = min(base_delay * (2 ** attempt), max_delay)
            jitter = random.uniform(0, delay * 0.3)
            sleep_time = delay + jitter
            logger.debug(f"[HTTP] POST {url} 失败，{sleep_time:.1f}s后重试({attempt+1}/{max_retries}): {e}")
            time.sleep(sleep_time)

    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(message)s")

    # 测试
    resp = http_get_with_retry("https://httpbin.org/get", max_retries=2)
    print("GET OK" if resp else "GET FAIL")
