<script lang="ts">
  // ป้าย "ชุดพัฒนา" เล็ก ๆ แทนบรรทัดยาวท้ายหน้า (Bo D1 6462103585 · กิ๊ฟ 28 ต.ค.) — กดเพื่ออ่านรายละเอียดจากเซิร์ฟเวอร์
  let { text = "" }: { text?: string } = $props();
</script>

<details class="dev">
  <summary>ชุดพัฒนา</summary>
  <p>{text || "ระบบอยู่ระหว่างพัฒนา"} · ผลยังไม่ใช่การตรวจรับจนกว่าผู้ตรวจจะยืนยัน</p>
</details>

<style>
  .dev { position: relative; font-size: .82em; }
  summary { list-style: none; cursor: pointer; padding: 2px 10px; border-radius: 999px; border: 1px solid #d0d5dd; background: #fff;
    color: #475467; font-weight: 600; }
  summary::-webkit-details-marker { display: none; }
  .dev[open] summary { border-color: #98a2b3; }
  p { position: absolute; right: 0; top: calc(100% + 6px); z-index: 20; width: min(360px, 80vw); margin: 0; padding: 10px 12px;
    border-radius: 10px; background: #fff; border: 1px solid var(--line); box-shadow: var(--shadow); color: #344054; font-weight: 400; }
</style>
