#!/usr/bin/env python3
"""检查数据是否有变化，有变化才发送通知"""
import hashlib
import json
from pathlib import Path

DATA_FILE = Path("/Users/luxiangnan/edict/data/sentiment_pool.json")
LAST_HASH_FILE = Path("/Users/luxiangnan/edict/data/last_sent_hash.txt")

def has_new_data():
    """检查是否有新数据"""
    if not DATA_FILE.exists():
        return False, "no_data_file"
    
    try:
        current_data = DATA_FILE.read_text()
        current_hash = hashlib.md5(current_data.encode()).hexdigest()
        
        if not LAST_HASH_FILE.exists():
            LAST_HASH_FILE.write_text(current_hash)
            return True, "first_run"
        
        last_hash = LAST_HASH_FILE.read_text().strip()
        if current_hash != last_hash:
            LAST_HASH_FILE.write_text(current_hash)
            return True, "data_changed"
        
        return False, "no_change"
    except Exception as e:
        return False, str(e)

if __name__ == "__main__":
    changed, reason = has_new_data()
    print(f"has_new_data: {changed}, reason: {reason}")
