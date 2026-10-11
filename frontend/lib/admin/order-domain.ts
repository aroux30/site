/**
 * The order domain, in one place, for every admin orders surface.
 *
 * Why this file exists: the two old pages (`/admin/orders` table and
 * `/admin/kanban` board) each carried their own copy of the status list,
 * Persian labels, colors, and transition knowledge — and the copies had
 * already drifted apart. The kanban's column set was missing several
 * statuses entirely, so an order in one of those states was INVISIBLE on
 * the board (not in any column) while still counting in its header totals.
 *
 * `ORDER_STATUS_TRANSITIONS` below is a hand-mirrored copy of the backend
 * state machine (`backend/app/modules/orders/application/order_service.py`
 * `_VALID_TRANSITIONS`). It is not the enforcement point — the server
 * rejects illegal transitions with `INVALID_STATUS_TRANSITION` regardless —
 * it exists so the UI can disable/refuse a drop before firing a request
 * that is guaranteed to fail. `tests/order-status-parity.test.ts` reads the
 * Python file from disk and fails when the two tables drift.
 */

/**
 * Every backend OrderStatus value, snake_case, in pipeline order.
 *
 * Seven statuses since 2026-10-11: the previous twelve modelled a physical
 * store. This is a DIGITAL store, so the packaging and delivery stages are
 * gone. What remains is the payment axis — `waiting_payment_gateway` (abandoned by
 * the customer, expires to `canceled` on a timer) and `waiting_payment_card` (an
 * operator's job, never expires) — plus the linear `pending → processing →
 * completed` chain and the two terminal exits, `canceled` and `refunded`.
 *
 * Note the database stores the enum NAMES (WAITING_PAYMENT_GATEWAY, …) while the
 * API speaks values (waiting_payment_gateway, …). This file is value-space, which
 * is what every response body carries.
 */
export const ORDER_STATUSES = [
  "waiting_payment_gateway",
  "waiting_payment_card",
  "pending",
  "processing",
  "completed",
  "canceled",
  "refunded",
] as const;

export type OrderStatus = (typeof ORDER_STATUSES)[number];

/**
 * The fulfillment pipeline, left-to-right in RTL rendering (first column is
 * the rightmost).
 *
 * Owner decision (2026-10-11, revised): SEVEN columns — each status is its
 * own lane. The operator sees every stage of the pipeline at a glance:
 * payment waiting (gateway / card-to-card), pending, processing, completed,
 * canceled and refunded. The settings popover lets the operator toggle any
 * column off (persisted in localStorage).
 */
export const BOARD_COLUMNS: OrderStatus[] = [
  "waiting_payment_gateway",
  "waiting_payment_card",
  "pending",
  "processing",
  "completed",
  "canceled",
  "refunded",
];

/**
 * Every status that may be shown as its OWN board column, in board order.
 *
 * This is the customization palette the settings popover offers. Each status
 * is its own lane — no grouping.
 */
export const CUSTOMIZABLE_COLUMNS: OrderStatus[] = [
  "waiting_payment_gateway",
  "waiting_payment_card",
  "pending",
  "processing",
  "completed",
  "canceled",
  "refunded",
];

/**
 * Which backend statuses feed each board column.
 *
 * Owner decision (2026-10-11, revised): each status is its OWN column — no
 * grouping. The operator asked to see every status separately on the board,
 * so `waiting_payment_gateway` has its own lane, `waiting_payment_card` has
 * its own lane, and so on.
 *
 * `Partial` on purpose: a status that is not a board column has NO lane, and
 * saying so with `undefined` beats the old pattern of self-entries
 * (`pending: ["pending"]`) that existed only to satisfy the `Record` type —
 * cruft that made "is this a lane?" unanswerable from the data.
 */
export const COLUMN_BACKEND_STATUSES: Partial<
  Record<OrderStatus, readonly OrderStatus[]>
> = {
  waiting_payment_gateway: ["waiting_payment_gateway"],
  waiting_payment_card: ["waiting_payment_card"],
  pending: ["pending"],
  processing: ["processing"],
  completed: ["completed"],
  canceled: ["canceled"],
  refunded: ["refunded"],
};

/**
 * The board column a status lives in, or null when it has no column.
 * Derived (not hand-written) so a lane edit cannot leave this stale.
 */
export const STATUS_TO_COLUMN: Partial<Record<OrderStatus, OrderStatus>> =
  Object.fromEntries(
    BOARD_COLUMNS.flatMap((column) =>
      (COLUMN_BACKEND_STATUSES[column] ?? []).map((member) => [member, column] as const),
    ),
  );

/**
 * The fulfillment chain, in the exact order the backend machine requires.
 *
 * The two payment-waiting buckets both open the chain and both step into
 * `pending`, so `nextInPipeline` moves them there — one legal transition,
 * which is what the advance button and the drag must ask for.
 */
export const PIPELINE_ORDER: readonly OrderStatus[] = [
  "waiting_payment_gateway",
  "waiting_payment_card",
  "pending",
  "processing",
  "completed",
];

/**
 * The one legal next stage, or null when there is none.
 *
 * NOT `PIPELINE_ORDER[index + 1]`: the chain BRANCHES at the start — both
 * waiting_payment_gateway and waiting_payment_card step into `pending` — so index+1 would
 * make waiting_payment_gateway advance to waiting_payment_card, a transition the backend
 * rejects with INVALID_STATUS_TRANSITION. Instead this walks forward through
 * the pipeline and returns the first stage the state machine actually
 * allows, skipping the exit branches (canceled/refunded are not in
 * `PIPELINE_ORDER` and are never returned here — exits are not advances).
 */
export function nextInPipeline(status: OrderStatus): OrderStatus | null {
  const currentIndex = PIPELINE_ORDER.indexOf(status);
  if (currentIndex < 0) return null;
  for (let i = currentIndex + 1; i < PIPELINE_ORDER.length; i++) {
    const candidate = PIPELINE_ORDER[i];
    if (candidate && isTransitionAllowed(status, candidate)) return candidate;
  }
  return null;
}

/**
 * Which status a drop onto this lane actually sets. It is the first lane
 * member reachable from `from` in ONE legal transition — never the lane's
 * first member unconditionally, because that could ask for an illegal jump.
 * Returns null when the drop must be refused.
 *
 * With each status as its own column, the lane has exactly one member.
 * Self-match (the card's current status equals the lane's status) is skipped
 * so that a drop onto the same column returns null (no-op).
 */
export function resolveDropTarget(
  from: OrderStatus,
  lane: OrderStatus,
): OrderStatus | null {
  for (const member of COLUMN_BACKEND_STATUSES[lane] ?? []) {
    if (member === from) continue; // already in this lane; look further
    if (isTransitionAllowed(from, member)) return member;
  }
  return null;
}

/**
 * Statuses with no board column. They are not hidden — `OrdersBoard` renders a
 * footer strip with each one's live count that deep-links to the list view
 * filtered to it, so shrinking the board can never make an order unreachable.
 */
export const OFF_BOARD_STATUSES: OrderStatus[] = ORDER_STATUSES.filter(
  (s) => STATUS_TO_COLUMN[s] === undefined,
);

// ── Column customization ───────────────────────────────────────────────────

/** localStorage key for the operator's column selection. */
export const BOARD_COLUMNS_STORAGE_KEY = "admin.orders.boardColumns";

/**
 * Read the saved column selection, or `null` when there is none.
 *
 * Untrusted input: localStorage is a string the operator (or another script,
 * or an older build) wrote, so it is parsed defensively. Anything that is not
 * an array of known, customizable columns is treated as "no preference" and
 * falls back to the default — a corrupted key must never empty the board.
 *
 * An empty array IS a legitimate stored value (the operator turned every
 * column off), but the board cannot render with no columns at all, so an
 * empty selection falls back to the defaults too. The board is the default
 * surface; the list view still holds every order.
 */
export function readStoredColumns(
  storage: Pick<Storage, "getItem"> | null | undefined = safeLocalStorage(),
): OrderStatus[] | null {
  const raw = storage?.getItem(BOARD_COLUMNS_STORAGE_KEY);
  if (!raw) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null; // not JSON — no usable preference
  }
  if (!Array.isArray(parsed)) return null;
  const valid = parsed.filter((c): c is OrderStatus =>
    (CUSTOMIZABLE_COLUMNS as readonly string[]).includes(c as string),
  );
  if (valid.length === 0) return null;
  // Dedupe and restore board order, so a hand-edited key cannot produce two
  // «completed» columns or put «لغو شده» to the left of «در حال پردازش».
  const chosen = new Set(valid);
  return CUSTOMIZABLE_COLUMNS.filter((c) => chosen.has(c));
}

/** Persist a column selection. Silently no-ops without a storage (SSR/blocked). */
export function writeStoredColumns(
  columns: readonly OrderStatus[],
  storage: Pick<Storage, "setItem"> | null | undefined = safeLocalStorage(),
): void {
  try {
    storage?.setItem(BOARD_COLUMNS_STORAGE_KEY, JSON.stringify(columns));
  } catch {
    // Quota or a private-mode refusal: the board still works this session,
    // it just will not remember. Never let a failed write break the toggle.
  }
}

/** localStorage is absent during SSR and throws in some sandboxed iframes. */
function safeLocalStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null; // blocked by privacy settings
  }
}

/**
 * The board column a status lives in, given the operator's column selection.
 *
 * `STATUS_TO_COLUMN` is the DEFAULT wiring; this is the same derivation over
 * whatever columns are actually on screen, so enabling «بازگشت وجه» makes
 * `refunded` reachable without hand-editing a second table.
 */
export function statusToColumnFor(
  status: OrderStatus,
  columns: readonly OrderStatus[],
): OrderStatus | undefined {
  for (const column of columns) {
    if ((COLUMN_BACKEND_STATUSES[column] ?? []).includes(status)) return column;
  }
  return undefined;
}

/**
 * Allowed transitions, mirrored from `_VALID_TRANSITIONS` in the backend
 * order service. Terminal statuses map to an empty list.
 */
export const ORDER_STATUS_TRANSITIONS: Record<OrderStatus, readonly OrderStatus[]> = {
  waiting_payment_gateway: ["pending", "canceled", "refunded"],
  waiting_payment_card: ["pending", "canceled", "refunded"],
  pending: ["processing", "canceled", "refunded"],
  processing: ["completed", "canceled", "refunded"],
  completed: [],
  canceled: [],
  refunded: [],
};

export function isTransitionAllowed(from: OrderStatus, to: OrderStatus): boolean {
  return (ORDER_STATUS_TRANSITIONS[from] ?? []).includes(to);
}

/** True when a drag between these two columns must be refused client-side. */
export function isTerminal(status: OrderStatus): boolean {
  return ORDER_STATUS_TRANSITIONS[status].length === 0;
}

/**
 * Which statuses the customer may cancel from (mirrors `_CUSTOMER_CANCELABLE`).
 *
 * Both payment-waiting buckets and `pending` — once an operator is working
 * the order (`processing`) it is no longer the customer's to cancel.
 */
export const CUSTOMER_CANCELABLE: readonly OrderStatus[] = [
  "waiting_payment_gateway",
  "waiting_payment_card",
  "pending",
];

// ── Presentation ───────────────────────────────────────────────────────────

export interface StatusVisual {
  /** Persian label shown everywhere. */
  label: string;
  /** One-line explanation, used in column headers and selects. */
  description: string;
  /**
   * Theme token per status. `dot` colors the status dot/indicator,
   * `chip` the full badge classes, `soft` a muted row/column tint, and
   * `solid` the filled action button (kanban card advance button).
   */
  dot: string;
  chip: string;
  soft: string;
  solid: string;
}

/**
 * One visual vocabulary for all seven statuses. Colors follow the journey:
 * amber (waiting on the customer) → violet (waiting on an admin) →
 * indigo (in progress) → teal (done) → rose/slate (exceptions).
 */
export const STATUS_VISUALS: Record<OrderStatus, StatusVisual> = {
  waiting_payment_gateway: {
    label: "در انتظار تایید پرداخت",
    description: "ارسال شده به درگاه، منتظر بازگشت پرداخت",
    dot: "bg-amber-500",
    chip: "border-amber-300 bg-amber-100 text-amber-800 dark:border-amber-800 dark:bg-amber-950/70 dark:text-amber-300",
    soft: "bg-amber-500/5 dark:bg-amber-950/20",
    solid: "bg-amber-500 hover:bg-amber-600 text-white",
  },
  waiting_payment_card: {
    label: "در انتظار تایید کارت به کارت",
    description: "رسید کارت به کارت بارگذاری شده، منتظر بررسی مدیر",
    dot: "bg-violet-500",
    chip: "border-violet-300 bg-violet-100 text-violet-800 dark:border-violet-800 dark:bg-violet-950/70 dark:text-violet-300",
    soft: "bg-violet-500/5 dark:bg-violet-950/20",
    solid: "bg-violet-500 hover:bg-violet-600 text-white",
  },
  pending: {
    label: "در حال انجام",
    description: "پرداخت تایید شده، آماده پردازش",
    dot: "bg-blue-500",
    chip: "border-blue-300 bg-blue-100 text-blue-800 dark:border-blue-800 dark:bg-blue-950/70 dark:text-blue-300",
    soft: "bg-blue-500/5 dark:bg-blue-950/20",
    solid: "bg-blue-500 hover:bg-blue-600 text-white",
  },
  processing: {
    label: "در حال پردازش",
    description: "در حال بررسی و انجام سفارش",
    dot: "bg-indigo-500",
    chip: "border-indigo-300 bg-indigo-100 text-indigo-800 dark:border-indigo-800 dark:bg-indigo-950/70 dark:text-indigo-300",
    soft: "bg-indigo-500/5 dark:bg-indigo-950/20",
    solid: "bg-indigo-500 hover:bg-indigo-600 text-white",
  },
  completed: {
    label: "تکمیل شده",
    description: "چرخه سفارش با موفقیت بسته شد",
    dot: "bg-teal-600",
    chip: "border-teal-300 bg-teal-100 text-teal-800 dark:border-teal-800 dark:bg-teal-950/70 dark:text-teal-300",
    soft: "bg-teal-500/5 dark:bg-teal-950/20",
    solid: "bg-teal-600 hover:bg-teal-700 text-white",
  },
  canceled: {
    label: "لغو شده",
    description: "لغو شده؛ سفارش بسته شد",
    dot: "bg-rose-600",
    chip: "border-rose-300 bg-rose-100 text-rose-800 dark:border-rose-800 dark:bg-rose-950/70 dark:text-rose-300",
    soft: "bg-rose-500/5 dark:bg-rose-950/20",
    solid: "bg-rose-600 hover:bg-rose-700 text-white",
  },
  refunded: {
    label: "بازگشت وجه",
    description: "وجه سفارش به مشتری بازگردانده شده",
    dot: "bg-slate-500",
    chip: "border-slate-300 bg-slate-100 text-slate-700 dark:border-slate-700 dark:bg-slate-900/70 dark:text-slate-300",
    soft: "bg-slate-500/5 dark:bg-slate-900/20",
    solid: "bg-slate-600 hover:bg-slate-700 text-white",
  },
};

/** The single next step in the linear pipeline, or null (branching/terminal). */
export function nextPipelineAction(status: OrderStatus): OrderStatus | null {
  return nextInPipeline(status);
}

/** The action label for advancing to `next` from `from`. */
export function advanceActionLabel(from: OrderStatus): string | null {
  const next = nextInPipeline(from);
  if (!next) return null;
  const labels: Partial<Record<OrderStatus, string>> = {
    pending: "تایید پرداخت",
    processing: "شروع پردازش",
    completed: "تکمیل سفارش",
  };
  return labels[next] ?? "مرحله بعد";
}

// ── Payment ────────────────────────────────────────────────────────────────

export type PaymentStatus = "paid" | "pending" | "failed" | "refunded" | "unpaid";

export interface PaymentVisual {
  label: string;
  chip: string;
}

export const PAYMENT_VISUALS: Record<PaymentStatus, PaymentVisual> = {
  paid: {
    label: "پرداخت شده",
    chip: "border-emerald-300 bg-emerald-100 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300",
  },
  pending: {
    label: "در انتظار پرداخت",
    chip: "border-amber-300 bg-amber-100 text-amber-800 dark:border-amber-800 dark:bg-amber-950/70 dark:text-amber-300",
  },
  failed: {
    label: "پرداخت ناموفق",
    chip: "border-rose-300 bg-rose-100 text-rose-800 dark:border-rose-800 dark:bg-rose-950/70 dark:text-rose-300",
  },
  refunded: {
    label: "استرداد شده",
    chip: "border-slate-300 bg-slate-100 text-slate-700 dark:border-slate-700 dark:bg-slate-900/70 dark:text-slate-300",
  },
  unpaid: {
    label: "بدون پرداخت",
    chip: "border-border bg-muted text-muted-foreground",
  },
};

/**
 * Derive the payment status of an order from its payment rows.
 *
 * The backend OrderListItem carries NO payment field — the old kanban page
 * defaulted every order to "پرداخت شده" (paid), which is a fabricated fact
 * on an ops screen. When payment rows are available (detail endpoint), this
 * is the honest derivation; when they are not, the caller shows "unpaid"
 * rather than inventing "paid".
 */
export function derivePaymentStatus(
  payments: { status: string }[] | undefined | null,
): PaymentStatus {
  if (!payments || payments.length === 0) return "unpaid";
  const statuses = payments.map((p) => p.status.toLowerCase());
  if (statuses.includes("completed")) {
    if (statuses.includes("refunded")) return "refunded";
    return "paid";
  }
  if (statuses.includes("refunded")) return "refunded";
  if (statuses.includes("pending") || statuses.includes("processing")) return "pending";
  if (statuses.includes("failed")) return "failed";
  return "unpaid";
}

// ── Money ──────────────────────────────────────────────────────────────────

/**
 * Order amounts are integer Rials everywhere in the order module
 * (`subtotal`, `total`, `unit_price`, `payment.amount`). The shared
 * `formatPrice` takes Toman — every call site converts here, once, instead
 * of each component remembering `/10` (the old pages each had their own
 * slightly different truncation).
 */
export function rialsToToman(amountRial: number | null | undefined): number {
  if (amountRial == null) return 0;
  return Math.trunc(amountRial / 10);
}

// ── Staleness ──────────────────────────────────────────────────────────────

/** Statuses where "sitting too long" means someone must act. */
const STALE_TRACKED: readonly OrderStatus[] = ["waiting_payment_gateway", "waiting_payment_card", "pending", "processing"];

export const STALE_AFTER_HOURS = 24;

/**
 * Hours since the order was created, floored; 0 for an unparsable date.
 */
export function hoursSince(iso: string): number {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return 0;
  return Math.max(0, Math.floor((Date.now() - t) / 3_600_000));
}

export function isOrderStale(status: OrderStatus, createdAt: string): boolean {
  if (!STALE_TRACKED.includes(status)) return false;
  return hoursSince(createdAt) >= STALE_AFTER_HOURS;
}

/** Persian relative time ("۳ ساعت پیش"). Shared by board and list. */
export function formatRelativeTime(iso: string, toPersianDigits: (v: string | number) => string): string {
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
