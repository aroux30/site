import type { ApiCategoryCustomField } from "./api/services";

export interface FieldValidationError {
  fieldKey: string;
  message: string;
}

export interface DynamicFieldsValidationResult {
  isValid: boolean;
  errors: Record<string, string>;
  cleanedAnswers: Record<string, string | number>;
}

/**
 * Normalizes Persian/Arabic digits to English digits for clean numeric parsing.
 */
export function normalizeDigits(input: string): string {
  return input
    .replace(/[۰-۹]/g, (d) => String(d.charCodeAt(0) - 1776))
    .replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 1632));
}

/**
 * Validates a single dynamic category field in real-time as the user inputs data.
 */
export function validateSingleDynamicField(
  def: ApiCategoryCustomField,
  rawValue: unknown
): string | null {
  const strVal = rawValue !== undefined && rawValue !== null ? String(rawValue).trim() : "";

  // 1. Required field check
  if (def.is_required && !strVal) {
    return `پر کردن فیلد «${def.label}» الزامی است`;
  }

  // If optional and empty, it's valid
  if (!strVal) {
    return null;
  }

  // 2. Type-specific validation
  if (def.field_type === "number") {
    const normalized = normalizeDigits(strVal);
    const num = Number(normalized);
    if (isNaN(num) || normalized === "") {
      return `مقدار فیلد «${def.label}» باید عدد باشد`;
    }
  } else if (def.field_type === "select") {
    const allowed = def.options_json ?? [];
    if (allowed.length > 0 && !allowed.includes(strVal)) {
      return `گزینه انتخاب شده برای فیلد «${def.label}» نامعتبر است`;
    }
  } else if (def.field_type === "text") {
    if (strVal.length > 200) {
      return `طول مقدار فیلد «${def.label}» نمی‌تواند بیشتر از ۲۰۰ کاراکتر باشد`;
    }
  }

  return null;
}

/**
 * Validates all category dynamic field answers against the schema definitions before submission.
 */
export function validateAllDynamicFields(
  definitions: ApiCategoryCustomField[],
  answers: Record<string, unknown>
): DynamicFieldsValidationResult {
  const errors: Record<string, string> = {};
  const cleanedAnswers: Record<string, string | number> = {};

  for (const def of definitions) {
    const raw = answers[def.field_key];
    const err = validateSingleDynamicField(def, raw);

    if (err) {
      errors[def.field_key] = err;
    } else {
      const strVal = raw !== undefined && raw !== null ? String(raw).trim() : "";
      if (strVal) {
        if (def.field_type === "number") {
          const normalized = normalizeDigits(strVal);
          const num = Number(normalized);
          cleanedAnswers[def.field_key] = Number.isInteger(num) ? parseInt(normalized, 10) : num;
        } else {
          cleanedAnswers[def.field_key] = strVal;
        }
      }
    }
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors,
    cleanedAnswers,
  };
}
