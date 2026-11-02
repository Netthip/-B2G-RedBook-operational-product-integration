// ข้อความแจ้งสั้น ๆ มุมจอ (บันทึกแล้ว / ผิดพลาด) — ไม่บังงาน หายเอง
export interface ToastAction { label: string; run: () => void }
export const toasts = $state<{ id: number; text: string; bad: boolean; action?: ToastAction }[]>([]);
let n = 0;
export function dismiss(id: number) {
  const i = toasts.findIndex((t) => t.id === id);
  if (i >= 0) toasts.splice(i, 1);
}
/** ข้อความแจ้ง — action = ปุ่มเดียวในข้อความ (เช่น "ยกเลิก") · มีปุ่มแล้วแสดงนานขึ้น */
export function toast(text: string, bad = false, action?: ToastAction) {
  const id = ++n;
  toasts.push({ id, text, bad, action });
  setTimeout(() => dismiss(id), bad ? 6000 : action ? 5000 : 2200);
}
