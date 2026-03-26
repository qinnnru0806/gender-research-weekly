#!/usr/bin/env python3
"""
test_api.py — 最小 API 診斷腳本
把錯誤訊息寫入檔案，完全繞過 stdout 編碼問題
"""
import os
import sys

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["LANG"] = "en_US.UTF-8"

import anthropic

api_key = os.environ.get("ANTHROPIC_API_KEY", "")
print(f"API key starts with: {api_key[:12]}...")
print(f"API key length: {len(api_key)}")

client = anthropic.Anthropic(api_key=api_key)

try:
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=10,
        messages=[{"role": "user", "content": "Hi"}]
    )
    print("SUCCESS! API works.")
    print(f"Response: {resp.content[0].text}")
except Exception as e:
    # 寫到檔案，繞過 stdout 編碼問題
    error_msg = repr(e)
    with open("api_error.txt", "w", encoding="utf-8") as f:
        f.write(f"Exception type: {type(e).__name__}\n")
        f.write(f"Exception repr: {error_msg}\n")
        f.write(f"Exception str:  {str(e)}\n")
    
    # 用 ASCII safe 方式印摘要
    safe_msg = error_msg.encode("ascii", errors="replace").decode("ascii")
    print(f"FAILED: {safe_msg}")
    print("Full error saved to api_error.txt")
    sys.exit(1)
