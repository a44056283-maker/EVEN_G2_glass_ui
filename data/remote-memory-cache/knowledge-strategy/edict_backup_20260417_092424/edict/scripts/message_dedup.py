#!/usr/bin/env python3
"""消息去重机制 - 避免重复发送相同内容"""
import hashlib
import json
from pathlib import Path
from datetime import datetime, timedelta

CACHE_FILE = Path("/Users/luxiangnan/edict/data/message_cache.json")
CACHE_DURATION = timedelta(minutes=30)  # 30分钟内相同消息不重复发送

def should_send(key: str, content: str = "") -> bool:
    """检查是否应该发送消息"""
    if not CACHE_FILE.exists():
        CACHE_FILE.write_text("{}")
    
    try:
        cache = json.loads(CACHE_FILE.read_text())
        now = datetime.now()
        
        # 检查是否在缓存时间内
        if key in cache:
            last_sent = datetime.fromisoformat(cache[key]["time"])
            if now - last_sent < CACHE_DURATION:
                # 内容相同则不发送
                if content and cache[key].get("content") == hashlib.md5(content.encode()).hexdigest():
                    return False
        
        # 更新缓存
        cache[key] = {
            "time": now.isoformat(),
            "content": hashlib.md5(content.encode()).hexdigest() if content else ""
        }
        CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False))
        return True
    except Exception:
        return True

if __name__ == "__main__":
    import sys
    key = sys.argv[1] if len(sys.argv) > 1 else "test"
    content = sys.argv[2] if len(sys.argv) > 2 else ""
    result = should_send(key, content)
    print(f"should_send({key}): {result}")
