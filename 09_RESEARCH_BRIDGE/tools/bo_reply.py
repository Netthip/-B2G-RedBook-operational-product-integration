"""ให้ Bo (OpenAI) ตอบคอมเมนต์ที่ส่งถึง Bo — รันใน GitHub Actions.

env ที่ต้องมี: OPENAI_API_KEY · GH_TOKEN · GITHUB_REPOSITORY · ISSUE_NUMBER
env เลือกได้:  COMMENT_ID (คอมเมนต์ที่ปลุก) · BO_MODEL (ค่าเริ่มต้น gpt-5)
"""
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from comment_lint import lint  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "09_RESEARCH_BRIDGE"
REPO = os.environ["GITHUB_REPOSITORY"]
ISSUE = os.environ["ISSUE_NUMBER"]
MODEL = os.environ.get("BO_MODEL") or "gpt-5"
MARKER = "<!-- bo-bot -->"
MAX_BOT_REPLIES_PER_DAY = 6      # กันคุยวนไม่รู้จบ — เกินแล้วส่งลูกให้กิ๊ฟ
RECENT_COMMENTS = 12
PER_COMMENT_CHARS = 4000
LINKED_FILE_CHARS = 30000
WAIT_LABELS = {"Giho": "รอ:จีโฮ", "Gift": "รอ:กิ๊ฟ", "Bo": "รอ:โบ"}


def gh_api(path: str, method: str = "GET", body: dict | None = None):
    cmd = ["gh", "api", "-X", method, path]
    inp = None
    if body is not None:
        cmd += ["--input", "-"]
        inp = json.dumps(body)
    out = subprocess.run(cmd, input=inp, capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(out.stdout) if out.stdout.strip() else None


def gh_comments() -> list[dict]:
    out = subprocess.run(["gh", "api", "--paginate", "--slurp", f"repos/{REPO}/issues/{ISSUE}/comments"],
                         capture_output=True, text=True, encoding="utf-8", check=True)
    return [c for page in json.loads(out.stdout) for c in page]


def set_waiting(who: str) -> None:
    issue = gh_api(f"repos/{REPO}/issues/{ISSUE}")
    for lab in issue["labels"]:
        if lab["name"].startswith("รอ:") and lab["name"] != WAIT_LABELS[who]:
            subprocess.run(["gh", "api", "-X", "DELETE",
                            f"repos/{REPO}/issues/{ISSUE}/labels/{lab['name']}"], capture_output=True)
    gh_api(f"repos/{REPO}/issues/{ISSUE}/labels", "POST", {"labels": [WAIT_LABELS[who]]})


def post(body: str) -> None:
    gh_api(f"repos/{REPO}/issues/{ISSUE}/comments", "POST", {"body": body})


def linked_files(text: str) -> str:
    """เปิดไฟล์ในรีโพนี้ที่คอมเมนต์ลิงก์ถึง (เฉพาะไฟล์ข้อความในรีโพ public นี้)."""
    paths = set(re.findall(rf"github\.com/{re.escape(REPO)}/blob/[^/\s]+/([^\s)#?]+)", text))
    paths |= set(re.findall(r"`((?:0\d|1\d|docs)_?[^`\s]*\.(?:md|csv|py|json|ya?ml))`", text))
    out, used = [], 0
    for rel in sorted(paths):
        p = (ROOT / rel).resolve()
        if ROOT not in p.parents or not p.is_file():
            continue
        body = p.read_text(encoding="utf-8", errors="replace")[: LINKED_FILE_CHARS - used]
        used += len(body)
        out.append(f"--- FILE {rel} (current main) ---\n{body}")
        if used >= LINKED_FILE_CHARS:
            break
    return "\n\n".join(out)


def ask_openai(system: str, user: str) -> str:
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps({"model": MODEL, "messages": [
            {"role": "system", "content": system}, {"role": "user", "content": user}]}).encode(),
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)["choices"][0]["message"]["content"].strip()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    comments = gh_comments()
    trigger_id = os.environ.get("COMMENT_ID") or ""
    trigger = next((c for c in comments if str(c["id"]) == trigger_id), comments[-1] if comments else None)
    # workflow กรองหยาบจากทั้งคอมเมนต์ — ที่นี่ตรวจละเอียดว่า "→ Bo" อยู่ในบรรทัดแรกจริง
    if trigger_id and "→ Bo" not in trigger["body"].splitlines()[0]:
        print("บรรทัดแรกไม่ได้ส่งถึง Bo — ข้าม")
        return 0
    if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("DRY_RUN"):
        print("ยังไม่ได้ตั้ง secret OPENAI_API_KEY — ข้าม")
        return 0

    since = datetime.now(timezone.utc) - timedelta(days=1)
    recent_bot = [c for c in comments if MARKER in c["body"]
                  and datetime.fromisoformat(c["created_at"].replace("Z", "+00:00")) > since]
    if len(recent_bot) >= MAX_BOT_REPLIES_PER_DAY:
        post(f"**[ACK]** Bo → Gift · ตอบอัตโนมัติครบ {MAX_BOT_REPLIES_PER_DAY} ครั้งใน 24 ชม. แล้ว "
             f"— หยุดไว้ให้กิ๊ฟดูก่อน\n\n{MARKER}")
        set_waiting("Gift")
        return 0

    issue = gh_api(f"repos/{REPO}/issues/{ISSUE}")

    history = "\n\n".join(
        f"=== comment {c['id']} · {c['user']['login']} · {c['created_at']} ===\n{c['body'][:PER_COMMENT_CHARS]}"
        for c in comments[-RECENT_COMMENTS:])
    system = (BRIDGE / "BO_AGENT_BRIEF.md").read_text(encoding="utf-8") + "\n\n" + \
        (BRIDGE / "COMMENT_PROTOCOL.md").read_text(encoding="utf-8")
    user = (f"ISSUE #{ISSUE}: {issue['title']}\n\n--- ISSUE BODY ---\n{issue['body'] or ''}\n\n"
            f"--- LAST {RECENT_COMMENTS} COMMENTS (oldest first) ---\n{history}\n\n"
            f"--- FILES LINKED FROM THE TRIGGERING COMMENT ---\n"
            f"{linked_files(trigger['body']) if trigger else '(none)'}\n\n"
            f"Reply as Bo to comment {trigger['id'] if trigger else '(issue body)'}.")

    if os.environ.get("DRY_RUN"):
        print(f"DRY_RUN · trigger {trigger and trigger['id']} · prompt {len(system) + len(user):,} ตัวอักษร")
        print(linked_files(trigger["body"])[:300] if trigger else "")
        return 0
    reply = ask_openai(system, user)
    errors, _ = lint(reply)
    if not re.match(r"^\*\*\[[A-Z-]+\]\*\*\s+Bo\s*→", reply):
        errors.append("บรรทัดแรกต้องเป็น **[ชนิด]** Bo → ...")
    if errors:
        reply = ask_openai(system, user + "\n\nYour previous draft broke the format:\n- "
                           + "\n- ".join(errors) + f"\n\nPrevious draft:\n{reply}\n\nRewrite it.")
        errors, _ = lint(reply)

    note = f"\n\n<sub>🤖 Bo ตอบอัตโนมัติ · {MODEL} · เห็นเฉพาะรีโพ public นี้ · ไม่ใช่คำตัดสินของกิ๊ฟ"
    note += " · ⚠ รูปแบบยังไม่ผ่าน comment_lint" if errors else ""
    post(reply + note + f"</sub>\n{MARKER}")

    head = reply.split("\n", 1)[0]
    who = "Gift" if ("ASK-GIFT" in head or "→ Gift" in head or errors) else "Giho"
    set_waiting(who)
    print(f"posted · waiting on {who} · lint errors: {errors or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
