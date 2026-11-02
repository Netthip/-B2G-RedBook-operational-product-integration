# -*- coding: utf-8 -*-
"""กติกาจับคู่ตัวชี้วัด 8 สถานะ — **เทสต์เชิงลบ**: ข้อความคล้ายกันต้องไม่ถูกรวมอัตโนมัติ

🔴 คำสั่งกิ๊ฟ (9 ก.ย. 2569 · Gate 2 ข้อ 4) — *"Add negative tests proving similar
wording is not automatically merged"*

ข้อสังเกตทั้งหมดในไฟล์นี้สร้างจากข้อความสังเคราะห์โดยตรง (ไม่เปิด PDF)
"""
import pytest

from redbook.indicators import mapping as mp
from redbook.indicators import normalize as nz
from redbook.indicators.observe import manual_observation
from redbook.indicators.observe import Observation

DOC_OLD, DOC_NEW = "doc_old0000000000", "doc_new0000000000"


def obs(text: str, *, doc=DOC_OLD, page=1, line=0) -> Observation:
    o = manual_observation(doc, "sha", page=page, observed_text=text)
    # ให้ id ต่างกันแม้ข้อความซ้ำ (จำลองสองบรรทัดคนละที่)
    return Observation(**{**o.__dict__, "line_index": line,
                          "observation_id": f"obs_{doc[4:7]}_{page}_{line}_{abs(hash(text)) % 10**6}",
                          "location_confidence": "EXACT_BBOX"})


def by_status(cands, status):
    return [c for c in cands if c.proposed_status == status]


# ── สถานะที่เครื่องเสนอได้ ────────────────────────────────────────────────────

def test_exact_text_is_same_exact_and_not_human_required():
    t = "ตัวชี้วัดที่ 1 : ร้อยละของหน่วยงานที่ได้รับการอบรม เป้าหมาย ร้อยละ 80"
    c = mp.propose([obs(t)], [obs(t, doc=DOC_NEW)])
    assert [x.proposed_status for x in c] == [mp.SAME_EXACT]
    assert c[0].human_required is False


def test_spacing_punctuation_thai_digits_only_is_wording_variant():
    a = "ตัวชี้วัดที่ 2 : ร้อยละของบุคลากรที่ผ่านการประเมิน (ร้อยละ 90)"
    b = "ตัวชี้วัดที่ 2 : ร้อยละ ของบุคลากร ที่ผ่านการประเมิน ( ร้อยละ ๙๐ )"
    c = mp.propose([obs(a)], [obs(b, doc=DOC_NEW)])
    assert [x.proposed_status for x in c] == [mp.SAME_WORDING_VARIANT]
    # ข้อความต้นฉบับทั้งสองยังอยู่ครบ ไม่ถูกแทนด้วยรูปมาตรฐาน
    assert c[0].differences == ()


def test_rephrased_same_fields_is_proposed_but_human_required():
    a = "ตัวชี้วัดที่ 3 : จำนวนรายงานวิจัยที่เผยแพร่ ไม่น้อยกว่า 5 เรื่อง"
    b = "ตัวชี้วัดที่ 3 : จำนวนรายงานวิจัยที่ได้รับการเผยแพร่ ไม่น้อยกว่า 5 เรื่อง"
    c = mp.propose([obs(a)], [obs(b, doc=DOC_NEW)])
    assert [x.proposed_status for x in c] == [mp.SAME_CONCEPT_REPHRASED]
    assert c[0].human_required is True


# ── เทสต์เชิงลบ: คล้ายแต่ห้ามรวม ───────────────────────────────────────────

@pytest.mark.parametrize("a,b", [
    # ตัวเลขเป้าหมายต่าง
    ("ร้อยละของหน่วยงานที่ได้รับการอบรม ตัวชี้วัด ร้อยละ 80",
     "ร้อยละของหน่วยงานที่ได้รับการอบรม ตัวชี้วัด ร้อยละ 85"),
    # หน่วยต่าง
    ("ตัวชี้วัด : จำนวนผู้เข้ารับการอบรม 200 คน", "ตัวชี้วัด : จำนวนผู้เข้ารับการอบรม 200 ครั้ง"),
    # ตัวหารเปลี่ยน (ชื่อเหมือนเดิม)
    ("ตัวชี้วัด : ร้อยละของโครงการที่แล้วเสร็จ (นับจากโครงการทั้งหมด) ร้อยละ 85",
     "ตัวชี้วัด : ร้อยละของโครงการที่แล้วเสร็จ (นับจากโครงการที่ได้รับจัดสรร) ร้อยละ 85"),
    # รอบรายงานเปลี่ยน
    ("ตัวชี้วัด : จำนวนเรื่องร้องเรียนที่แก้ไข รายปี 10 เรื่อง",
     "ตัวชี้วัด : จำนวนเรื่องร้องเรียนที่แก้ไข รายไตรมาส 10 เรื่อง"),
])
def test_high_similarity_with_changed_definition_is_never_same(a, b):
    c = mp.propose([obs(a)], [obs(b, doc=DOC_NEW)])
    assert len(c) == 1
    assert c[0].proposed_status not in mp.SAME_FAMILY, c[0]
    assert c[0].proposed_status in (mp.DEFINITION_CHANGED, mp.AMBIGUOUS_REVIEW_REQUIRED)
    assert c[0].human_required is True
    # ความคล้ายเชิงอักขระสูงจริง — นี่คือเหตุผลที่เทสต์นี้มีความหมาย
    assert nz.dice(nz.trigrams(nz.normalize(a)), nz.trigrams(nz.normalize(b))) >= 0.75


def test_one_extra_word_is_not_silently_same():
    """'ผู้ป่วย' กับ 'ผู้ป่วยนอก' คล้ายเชิงอักขระมาก — เครื่องเสนอได้แค่สถานะที่ต้องให้คนยืนยัน"""
    a = "ตัวชี้วัด : จำนวนผู้ป่วยที่ได้รับบริการ 500 ราย"
    b = "ตัวชี้วัด : จำนวนผู้ป่วยนอกที่ได้รับบริการ 500 ราย"
    c = mp.propose([obs(a)], [obs(b, doc=DOC_NEW)])
    assert c[0].proposed_status not in (mp.SAME_EXACT, mp.SAME_WORDING_VARIANT)
    assert c[0].human_required is True


def test_duplicate_wording_in_one_document_is_ambiguous_not_same_exact():
    t = "ตัวชี้วัดที่ 7 : จำนวนกิจกรรมเผยแพร่ความรู้ 12 ครั้ง"
    c = mp.propose([obs(t, page=3)], [obs(t, doc=DOC_NEW, page=4), obs(t, doc=DOC_NEW, page=5, line=1)])
    assert {x.proposed_status for x in c} == {mp.AMBIGUOUS_REVIEW_REQUIRED}
    assert len(c) == 2 and all(x.human_required for x in c)
    assert all(x.alternatives for x in c)


def test_machine_never_proposes_related_not_equivalent():
    pairs = [
        ("ตัวชี้วัด : จำนวนผู้เข้ารับการอบรม 200 คน", "ตัวชี้วัด : จำนวนหลักสูตรอบรมที่เปิดสอน 4 หลักสูตร"),
        ("ตัวชี้วัด : ร้อยละของหน่วยงาน 80", "ตัวชี้วัด : ร้อยละของหน่วยงานที่ผ่านเกณฑ์ 80"),
    ]
    for a, b in pairs:
        for c in mp.propose([obs(a)], [obs(b, doc=DOC_NEW)]):
            assert c.proposed_status != mp.RELATED_NOT_EQUIVALENT
            assert c.proposed_status in mp.MACHINE_MAY_PROPOSE
    assert mp.RELATED_NOT_EQUIVALENT not in mp.MACHINE_MAY_PROPOSE


def test_human_required_set_is_exactly_3_4_5_8():
    assert mp.HUMAN_REQUIRED == {mp.SAME_CONCEPT_REPHRASED, mp.RELATED_NOT_EQUIVALENT,
                                 mp.DEFINITION_CHANGED, mp.AMBIGUOUS_REVIEW_REQUIRED}
    assert len(mp.STATUSES) == 8


def test_unmatched_are_accounted_as_removed_and_new():
    c = mp.propose([obs("ตัวชี้วัด : ร้อยละของข้อร้องเรียนที่ได้รับการแก้ไข 100")],
                   [obs("ตัวชี้วัด : จำนวนคู่มือที่จัดทำ 3 ฉบับ", doc=DOC_NEW)])
    assert sorted(x.proposed_status for x in c) == sorted([mp.REMOVED_INDICATOR, mp.NEW_INDICATOR])


def test_every_observation_is_accounted_and_order_does_not_matter():
    old = [obs("ตัวชี้วัด ก ร้อยละ 80"), obs("ตัวชี้วัด ข 5 เรื่อง", line=1),
           obs("ตัวชี้วัด ค 12 ครั้ง", line=2), obs("ตัวชี้วัด ง 100 คน", line=3)]
    new = [obs("ตัวชี้วัด ค 12 ครั้ง", doc=DOC_NEW), obs("ตัวชี้วัด ก ร้อยละ 80", doc=DOC_NEW, line=1),
           obs("ตัวชี้วัด จ 9 แห่ง", doc=DOC_NEW, line=2), obs("ตัวชี้วัด ข 5 เรื่อง", doc=DOC_NEW, line=3)]
    c1 = mp.propose(old, new)
    c2 = mp.propose(list(reversed(old)), list(reversed(new)))
    key = lambda cs: sorted((x.mapping_id, x.proposed_status) for x in cs)   # noqa: E731
    assert key(c1) == key(c2), "ผลต้องไม่ขึ้นกับลำดับที่อ่าน"
    assert mp.accounted(old, new, c1)["closed"] is True


def test_rules_hash_changes_when_threshold_changes():
    assert mp.Rules().rules_hash != mp.Rules(rephrase_min=0.9).rules_hash


def test_normalize_keeps_original_separate():
    raw = "ร้อยละ ของ  บุคลากร （๙๐）"
    assert nz.normalize(raw) != raw
    assert nz.numeric_tokens(raw) == ("90",)
