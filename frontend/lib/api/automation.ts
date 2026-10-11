import apiClient from "./client";

// ── Types ───────────────────────────────────────────────────────────────────

/**
 * Triggers the engine subscribes to. Kept as a literal union rather than a bare
 * `string` so a typo is a compile error here instead of a 422 at runtime — the
 * backend validates against exactly these five names.
 */
export type AutomationTriggerType =
  | "order_paid"
  | "order_created"
  | "user_registered"
  | "review_created"
  | "stock_low";

export type ConditionOperator =
  | "eq"
  | "ne"
  | "gt"
  | "lt"
  | "gte"
  | "lte"
  | "contains";

// "send_email" was removed on 2026-10-07 with the rest of the email feature.
export type AutomationActionType = "send_notification";

/** One condition: a dotted path into the trigger context, compared to a value. */
export interface RuleCondition {
  field: string;
  operator: ConditionOperator;
  value: unknown;
}

/** One action. `params` is action-specific — see the engine for each shape. */
export interface RuleAction {
  type: AutomationActionType;
  params: Record<string, unknown>;
}

export interface AutomationRule {
  id: string;
  name: string;
  description: string | null;
  trigger_type: AutomationTriggerType;
  conditions: RuleCondition[];
  actions: RuleAction[];
  is_active: boolean;
  cooldown_minutes: number | null;
  last_triggered_at: string | null;
  created_at: string;
}

export interface AutomationRuleList {
  items: AutomationRule[];
  total: number;
}

/** One action's outcome from a dry-run. A failing action is reported, not raised. */
export interface RuleActionResult {
  type: string;
  status: "ok" | "failed";
  error?: string;
}

export interface RuleTestResult {
  matched: boolean;
  actions: RuleActionResult[];
}

/**
 * Create payload. `trigger_type` is fixed at create time — PATCH does not accept
 * it, so a rule cannot be silently re-pointed at a different event by an edit
 * that only meant to change the name.
 */
export interface AutomationRuleCreate {
  name: string;
  description?: string | null;
  trigger_type: AutomationTriggerType;
  conditions?: RuleCondition[];
  actions: RuleAction[];
  is_active?: boolean;
  cooldown_minutes?: number | null;
}

/** Patch payload. Omit a key to leave it untouched. */
export interface AutomationRuleUpdate {
  name?: string;
  description?: string | null;
  conditions?: RuleCondition[];
  actions?: RuleAction[];
  is_active?: boolean;
  cooldown_minutes?: number | null;
}

// ── Reference data (mirrors the engine, not a second source of truth) ───────

export const TRIGGER_LABELS: Record<AutomationTriggerType, string> = {
  order_paid: "پرداخت سفارش",
  order_created: "ایجاد سفارش",
  user_registered: "ثبت‌نام کاربر",
  review_created: "ثبت نظر",
  stock_low: "کمبود موجودی",
};

export const OPERATOR_LABELS: Record<ConditionOperator, string> = {
  eq: "برابر",
  ne: "نابرابر",
  gt: "بزرگ‌تر از",
  lt: "کوچک‌تر از",
  gte: "بزرگ‌تر یا مساوی",
  lte: "کوچک‌تر یا مساوی",
  contains: "شامل",
};

export const ACTION_LABELS: Record<AutomationActionType, string> = {
  send_notification: "اعلان درون‌برنامه‌ای",
};

/**
 * Required `params` per action type, taken from the engine's handlers — a rule
 * whose params are missing one of these fails at fire time with a message no
 * operator can act on, so the form labels them up front instead.
 */
export const ACTION_PARAM_HINTS: Record<AutomationActionType, Record<string, string>> = {
  send_notification: {
    user_id: "شناسه کاربر (الزامی)",
    title: "عنوان",
    body: "متن",
    type: "نوع اعلان",
  },
};

// ── API (admin) ─────────────────────────────────────────────────────────────

export const automationApi = {
  /** فهرست قواعد خودکارسازی */
  listRules: async (params?: {
    trigger_type?: AutomationTriggerType;
    is_active?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<AutomationRuleList> => {
    const res = await apiClient.get<AutomationRuleList>("/automation/admin/rules", { params });
    return res.data;
  },

  /** یک قاعده */
  getRule: async (ruleId: string): Promise<AutomationRule> => {
    const res = await apiClient.get<AutomationRule>(`/automation/admin/rules/${ruleId}`);
    return res.data;
  },

  /** ایجاد قاعده */
  createRule: async (payload: AutomationRuleCreate): Promise<AutomationRule> => {
    const res = await apiClient.post<AutomationRule>("/automation/admin/rules", payload);
    return res.data;
  },

  /** ویرایش قاعده */
  updateRule: async (
    ruleId: string,
    payload: AutomationRuleUpdate,
  ): Promise<AutomationRule> => {
    const res = await apiClient.patch<AutomationRule>(
      `/automation/admin/rules/${ruleId}`,
      payload,
    );
    return res.data;
  },

  /** حذف قاعده */
  deleteRule: async (ruleId: string): Promise<void> => {
    await apiClient.delete(`/automation/admin/rules/${ruleId}`);
  },

  /**
   * اجرای آزمایشی قاعده با یک context دلخواه.
   *
   * This is not side-effect free: a matching rule really does run its actions,
   * which really do create the notification. The endpoint is
   * a dry run in the sense that it ignores the rule's active flag and
   * cooldown, not in the sense that it fakes the actions.
   */
  triggerRule: async (
    ruleId: string,
    context: Record<string, unknown>,
  ): Promise<RuleTestResult> => {
    const res = await apiClient.post<RuleTestResult>(
      `/automation/admin/rules/${ruleId}/trigger`,
      { context },
    );
    return res.data;
  },
};
