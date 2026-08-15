"""Duzenlenen Python dosyasini ANINDA derler.

CLAUDE.md tur sonunda `python -m compileall -q main.py app tests` istiyor.
Tur sonu cok gec: sozdizimi hatasi o ana kadar yapilan butun koşumları
bozabiliyor. Bu hook her Edit/Write sonrasi YALNIZ degisen dosyayi derler,
bu yuzden maliyeti milisaniyedir.

Basarisizlikta `decision: block` ile geri bildirim verilir; boylece hata
sessizce gecmez.
"""
import json
import os
import subprocess
import sys


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    response = payload.get("tool_response") or {}
    tool_input = payload.get("tool_input") or {}
    path = (response.get("filePath") or tool_input.get("file_path") or "")
    if not path.endswith(".py") or not os.path.isfile(path):
        return 0

    completed = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", path],
        capture_output=True, text=True)
    if completed.returncode == 0:
        return 0

    detail = (completed.stdout + completed.stderr).strip()[-1500:]
    json.dump({
        "decision": "block",
        "reason": f"`compileall` bu dosyada BASARISIZ:\n{path}\n\n{detail}",
    }, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
