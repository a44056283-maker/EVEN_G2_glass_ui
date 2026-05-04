#!/usr/bin/env python3
"""
钦天监 · curl HTTP 客户端
统一使用 curl 发起 HTTP 请求（curl 在本机网络正常，urllib/requests 有 SSL 异常）
"""
import subprocess
import json
import time


PROXY = "http://127.0.0.1:5020"


def curl_get(url: str, timeout: int = 8, headers: dict = None, proxy: bool = False) -> str | None:
    """
    使用 curl GET，返回 str 或 None
    curl 在本机网络正常，urllib/requests 常挂起
    """
    h_args = []
    if headers:
        for k, v in headers.items():
            h_args += ["-H", f"{k}: {v}"]
    h_args += ["-H", "Accept: application/json, text/xml, */*"]

    cmd = ["curl", "-s", "--max-time", str(timeout), "-A", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"]
    if proxy:
        cmd += ["-x", PROXY]
    cmd += h_args + [url]

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 2)
        if r.returncode == 0 and r.stdout:
            return r.stdout
        return None
    except Exception:
        return None


def curl_json(url: str, timeout: int = 8, headers: dict = None, proxy: bool = False) -> dict | None:
    """curl GET 并尝试解析 JSON"""
    text = curl_get(url, timeout=timeout, headers=headers, proxy=proxy)
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def curl_retry(url: str, max_retries: int = 2, base_delay: float = 1.0, timeout: int = 8, proxy: bool = False) -> str | None:
    """curl GET，带重试（指数退避）"""
    import random
    for attempt in range(max_retries + 1):
        result = curl_get(url, timeout=timeout, proxy=proxy)
        if result is not None:
            return result
        if attempt < max_retries:
            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            time.sleep(delay)
    return None


if __name__ == "__main__":
    # 测试
    r = curl_get("https://api.alternative.me/fng/", timeout=5)
    print("FG:", json.loads(r).get("data", [{}])[0].get("value") if r else "FAIL")
