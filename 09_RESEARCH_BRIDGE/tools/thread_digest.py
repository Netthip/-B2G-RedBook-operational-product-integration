"""สรุปทุกใบที่เปิดอยู่: ป้าย รอ: และคอมเมนต์ล่าสุดแค่บรรทัดชนิด + สรุป.

ใช้:  python thread_digest.py [จำนวนคอมเมนต์ล่าสุดต่อใบ=3]
ต้องมี gh ที่ login แล้ว
"""
import json
import os
import re
import subprocess
import sys

HEADER_RE = re.compile(r"^\*\*\[([A-Z-]+)\]\*\*\s*(.*)$", re.M)
SUMMARY_RE = re.compile(r"\*\*สรุป:\*\*\s*(.+)")


def gh(*args: str):
    out = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(out.stdout)


def one_line(body: str) -> str:
    head = HEADER_RE.search(body)
    summ = SUMMARY_RE.search(body)
    if head:
        line = f"[{head[1]}] {head[2].strip()}"
        return f"{line} — {summ[1].strip()}" if summ else line
    first = next((l.strip("# ").strip() for l in body.splitlines() if l.strip()), "")
    return f"(ไม่ตามโครง · {len(body):,} ตัวอักษร) {first[:90]}"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    global REPO
    REPO = os.environ.get("GITHUB_REPOSITORY") or gh("repo", "view", "--json", "nameWithOwner")["nameWithOwner"]
    last_n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    issues = gh("issue", "list", "-R", REPO, "--state", "open", "--limit", "50",
                "--json", "number,title,labels,comments")
    for it in sorted(issues, key=lambda i: i["number"]):
        waiting = [l["name"] for l in it["labels"] if l["name"].startswith("รอ:")]
        tag = waiting[0] if len(waiting) == 1 else ("⚠ ไม่มีป้าย รอ:" if not waiting else f"⚠ ป้ายซ้อน {waiting}")
        comments = it["comments"]
        print(f"\n#{it['number']}  {tag}  ·  {len(comments)} คอมเมนต์\n    {it['title']}")
        if len(comments) > 25:
            print("    ⚠ เกิน 25 คอมเมนต์ — ถึงเวลาตัดรอบ")
        for c in comments[-last_n:]:
            print(f"    {c['createdAt'][:10]} {c['author']['login']}: {one_line(c['body'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
