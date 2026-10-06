# MANIFEST — entry_gate_01 (#5 · ด่านทางเข้าการประเมิน)

**ป้าย:** หลักฐานกลไก · **ข้อมูลสังเคราะห์ล้วน** · ไม่ใช่ผลประเมิน · ไม่มีเฉลยจริง

| ชั้น | ค่า |
|---|---|
| commit ระบบ | `47bb3df` (branch `eval/5-entry-gate` แตกจาก `t1b/fy2570-mvp` @ `06f8e64` · repo private · **ยังไม่ push**) |
| รุ่นส่วนประกอบ | `t1b-eval-entry-gate-0.1.0` · `t1b-posture-0.2.0` · `t1b-scoring-3layer-0.2.0` |
| SHA-256 ตารางท่าที | `5173d822b7a47d6cac69f7e039d3f7ccaa143b020ff625e0764e236bdbc24189` |
| คำสั่ง | `python scripts/t1b_entry_gate_evidence.py --out <โฟลเดอร์นี้>` · `pytest tests/test_t1b_eval_entry_gate.py tests/test_t1b_posture_table.py tests/test_t1b_scoring_conservation.py -v` |
| เวลา | 2026-10-07 (เวลาในไฟล์ JSON ตรึงเป็น `2026-10-07T00:00:00Z` เพื่อให้แฮชซ้ำได้) |
| สภาพแวดล้อม | Python 3.12.9 · Windows 11 |
| ชุดเต็ม | 1266 passed + 4 skipped (เครื่องผู้พัฒนา · **ไม่มี CI**) |

## ไฟล์

| ไฟล์ | กรณี | SHA-256 |
|---|---|---|
| `01_pass.json` | PASS → เรียก score() | `2ffe3cf106f07bf4d33a9d33a6a1234cd65fbb997aeeda82583d0479994c798b` |
| `02_block_undeclared_type.json` | BLOCKED · UNDECLARED_TYPE | `fc1d94ef744312c7b087cd1e27968e7327c6027668cfee8a9eadaea8d0948f53` |
| `03_block_stratum_mismatch.json` | BLOCKED · STRATUM_MISMATCH | `6da17ae08062027116b5ae04bf38bcbb560e9e85025e2a497d88ce37a372f5c2` |
| `04_block_negative_control.json` | BLOCKED · NEGATIVE_CONTROL_MISUSE | `ea90d6195fef7d02b1dbd04d06039577d46e4af4161480734043eb52816047ab` |
| `05_block_posture_version_drift.json` | BLOCKED · POSTURE_VERSION_DRIFT | `120037c0cc65d02c87f06d9680605025765f9835b91c401c91f088e85c5bde65` |
| `pytest_gate_posture_scoring.txt` | ผลเทสต์ 78 ข้อ (path ถูกกลบ) | `b8097171db1bc00ffda0a942752c805e99e1cbac8feb8ab89a6ff2e82d46643b` |
