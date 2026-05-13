#!/usr/bin/env python3
"""Test Chinese font embedding in PDF via Chrome headless."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from geoplus.paths import pdf_dir

html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
  * { font-family: "STHeiti", "Heiti SC", "Hiragino Sans GB", "Arial Unicode MS", sans-serif; }
  body { font-size: 18px; line-height: 2; padding: 40px; }
  h1 { font-size: 24px; border-bottom: 2px solid #ccc; }
</style>
</head>
<body>
  <h1>中文 PDF 渲染测试</h1>
  <p>如果这段中文能正常显示，说明字体可以嵌入 PDF。</p>
  <p>GEO+ 文档优化系统 — 测试报告 2026-05-11</p>
  <p>引用次数占比从 13.6% 提升至 57.8%。</p>
  <hr>
  <p>English fallback test: This should always render.</p>
</body>
</html>"""

tmpdir = tempfile.mkdtemp()
html_path = os.path.join(tmpdir, "test.html")
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

chrome_paths = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]

for cp in chrome_paths:
    if os.path.exists(cp):
        out_pdf = str(pdf_dir() / "font-test.pdf")
        cmd = [
            cp, "--headless", "--disable-gpu",
            f"--print-to-pdf={out_pdf}",
            "--no-pdf-header-footer", html_path,
        ]
        env = os.environ.copy()
        env["LANG"] = "zh_CN.UTF-8"
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
        if os.path.exists(out_pdf) and os.path.getsize(out_pdf) > 1000:
            print(f"SUCCESS: PDF at {out_pdf} ({os.path.getsize(out_pdf)} bytes)")
            # Check if PDF contains Chinese text
            with open(out_pdf, "rb") as f:
                data = f.read()
            has_cjk = any(b"\xe4\xb8" in data or b"\xe6\x96" in data or b"\xe6\x9c" in data for _ in [1])
            print(f"  CJK bytes in PDF: {'YES' if has_cjk else 'NO (FONT EMBEDDING FAILED)'}")
            sys.exit(0)
        else:
            print(f"Chrome ran but PDF too small/not created. Exit: {result.returncode}")
            stderr = result.stderr
            for line in stderr.split("\n"):
                if any(k in line.lower() for k in ["font", "error", "fail", "missing"]):
                    print(f"  [{line.strip()}]")
            sys.exit(1)

print("No Chrome/Chromium/Edge found. Install Chrome to test.")
sys.exit(1)
