/**
 * The support-ticket domain, in one place, for every admin tickets surface.
 *
 * Status vocabulary mirrors `TicketStatus` in
 * `backend/app/modules/support/domain/models.py`.
 *
 * NOTE ON TRANSITIONS: unlike orders, the support backend has NO state
 * machine — `PATCH /admin/tickets/{id}` accepts any status change. The
 * table below is therefore UI POLICY, not a mirror: it encodes the
 * workflow an operator actually follows (open → in progress → waiting →
 * resolved → closed, with reopen paths) so a drag cannot jump a ticket
 * from «باز» to «بستهشده» by accident. The server would accept that jump;
 * the board refuses it as a guard rail, not as an authority. This is
 * deliberately NOT parity-tested against the backend (there is nothing to
 * mirror); the test suite pins the invariants that matter (every status
 * covered, closed only reopens to open, etc.).
 */

export const TICKET_STATUSES = [
  "open",
  "in_progress",
  "waiting",
  "resolved",
  "closed",
] as const;

export type TicketStatus = (typeof TICKET_STATUSES)[number];

export const TICKET_PRIORITIES = ["urgent", "high", "medium", "low"] as const;
export type TicketPriority = (typeof TICKET_PRIORITIES)[number];

/** Board columns, left-to-right in RTL rendering (first is rightmost). */
export const TICKET_BOARD_COLUMNS: TicketStatus[] = [
  "open",
  "in_progress",
  "waiting",
  "resolved",
  "closed",
];

/**
 * UI-policy transitions (see the file header — the backend accepts
 * anything, this is the workflow guard rail).
 */
export const TICKET_TRANSITIONS: Record<TicketStatus, readonly TicketStatus[]> = {
  open: ["in_progress", "waiting", "resolved", "closed"],
  in_progress: ["waiting", "resolved", "closed"],
  waiting: ["in_progress", "resolved", "closed"],
  resolved: ["in_progress", "closed"],
  closed: ["open"], // reopen
};

export function isTicketTransitionAllowed(from: TicketStatus, to: TicketStatus): boolean {
  return (TICKET_TRANSITIONS[from] ?? []).includes(to);
}

export function isTicketTerminal(status: TicketStatus): boolean {
  return TICKET_TRANSITIONS[status].length === 0;
}

// ── Presentation ───────────────────────────────────────────────────────────

export interface TicketStatusVisual {
  label: string;
  description: string;
  dot: string;
  chip: string;
  soft: string;
  solid: string;
}

export const TICKET_STATUS_VISUALS: Record<TicketStatus, TicketStatusVisual> = {
  open: {
    label: "باز",
    description: "دریافت شده، منتظر شروع بررسی",
    dot: "bg-sky-500",
    chip: "border-sky-300 bg-sky-100 text-sky-800 dark:border-sky-800 dark:bg-sky-950/70 dark:text-sky-300",
    soft: "bg-sky-500/5 dark:bg-sky-950/20",
    solid: "bg-sky-500 hover:bg-sky-600 text-white",
  },
  in_progress: {
    label: "در حال بررسی",
    description: "کارشناس در حال رسیدگی است",
    dot: "bg-indigo-500",
    chip: "border-indigo-300 bg-indigo-100 text-indigo-800 dark:border-indigo-800 dark:bg-indigo-950/70 dark:text-indigo-300",
    soft: "bg-indigo-500/5 dark:bg-indigo-950/20",
    solid: "bg-indigo-500 hover:bg-indigo-600 text-white",
  },
  waiting: {
    label: "در انتظار پاسخ کاربر",
    description: "پاسخ کارشناس ارسال شده، منتظر کاربر",
    dot: "bg-amber-500",
    chip: "border-amber-300 bg-amber-100 text-amber-800 dark:border-amber-800 dark:bg-amber-950/70 dark:text-amber-300",
    soft: "bg-amber-500/5 dark:bg-amber-950/20",
    solid: "bg-amber-500 hover:bg-amber-600 text-white",
  },
  resolved: {
    label: "حل‌شده",
    description: "مشکل رفع شده، منتظر تایید نهایی",
    dot: "bg-emerald-500",
    chip: "border-emerald-300 bg-emerald-100 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300",
    soft: "bg-emerald-500/5 dark:bg-emerald-950/20",
    solid: "bg-emerald-600 hover:bg-emerald-700 text-white",
  },
  closed: {
    label: "بسته‌شده",
    description: "پایان‌یافته — امکان پاسخ در گفتگو نیست",
    dot: "bg-slate-500",
    chip: "border-slate-300 bg-slate-100 text-slate-700 dark:border-slate-700 dark:bg-slate-900/70 dark:text-slate-300",
    soft: "bg-slate-500/5 dark:bg-slate-900/20",
    solid: "bg-slate-600 hover:bg-slate-700 text-white",
  },
};

export interface TicketPriorityVisual {
  label: string;
  chip: string;
  dot: string;
}

export const TICKET_PRIORITY_VISUALS: Record<TicketPriority, TicketPriorityVisual> = {
  urgent: {
    label: "فوری",
    chip: "border-rose-300 bg-rose-100 text-rose-800 dark:border-rose-800 dark:bg-rose-950/70 dark:text-rose-300",
    dot: "bg-rose-500",
  },
  high: {
    label: "بالا",
    chip: "border-orange-300 bg-orange-100 text-orange-800 dark:border-orange-800 dark:bg-orange-950/70 dark:text-orange-300",
    dot: "bg-orange-500",
  },
  medium: {
    label: "متوسط",
    chip: "border-border bg-muted text-muted-foreground",
    dot: "bg-slate-400",
  },
  low: {
    label: "پایین",
    chip: "border-border bg-muted text-muted-foreground",
    dot: "bg-slate-300",
  },
};

/**
 * The single "advance" step offered on a card button, per column. Mirrors
 * the main forward path of TICKET_TRANSITIONS (branching moves — waiting ↔
 * in_progress, reopen — happen via drag or the drawer).
 */
export const TICKET_NEXT_STEP: Partial<Record<TicketStatus, TicketStatus>> = {
  open: "in_progress",
  in_progress: "waiting",
  waiting: "resolved",
  resolved: "closed",
  closed: "open", // reopen
};

export function ticketAdvanceLabel(from: TicketStatus): string | null {
  const next = TICKET_NEXT_STEP[from];
  if (!next) return null;
  const labels: Record<TicketStatus, string> = {
    open: "بازگشایی",
    in_progress: "شروع بررسی",
    waiting: "انتظار پاسخ کاربر",
    resolved: "ثبت حل‌شدن",
    closed: "بستن تیکت",
  };
  return labels[next];
}

/** Tickets whose SLA clock is running: not resolved and not closed. */
export function isTicketActive(status: TicketStatus): boolean {
  return status !== "resolved" && status !== "closed";
}

/**
 * Hours a ticket has sat since its LAST update, floored. `updated_at`
 * changes on every message and status change, so this is "time since the
 * ball last moved" — the right staleness clock for a conversation.
 */
export function hoursSinceUpdate(updatedAt: string): number {
  const t = new Date(updatedAt).getTime();
  if (Number.isNaN(t)) return 0;
  return Math.max(0, Math.floor((Date.now() - t) / 3_600_000));
}

/** Stale = active ticket untouched for 48h+. */
export const TICKET_STALE_AFTER_HOURS = 48;

export function isTicketStale(status: TicketStatus, updatedAt: string): boolean {
  if (!isTicketActive(status)) return false;
  return hoursSinceUpdate(updatedAt) >= TICKET_STALE_AFTER_HOURS;
}

/** Persian relative time for the card footer. */
export function formatTicketRelativeTime(
  iso: string,
  toPersianDigits: (v: string | number) => string,
): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "نامشخص";
  const diffMin = Math.floor((Date.now() - t) / 60_000);
  if (diffMin < 1) return "چند لحظه پیش";
  if (diffMin < 60) return `${toPersianDigits(diffMin)} دقیقه پیش`;
  const hours = Math.floor(diffMin / 60);
  if (hours < 24) return `${toPersianDigits(hours)} ساعت پیش`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "دیروز";
  if (days < 30) return `${toPersianDigits(days)} روز پیش`;
  return new Date(iso).toLocaleDateString("fa-IR");
}
