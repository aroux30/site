export interface BulkImportRowResult {
  row_number?: number;
  row?: number;
  field?: string | null;
  serial_number?: string | null;
  status: "success" | "duplicate_skipped" | "error";
  detail?: string | null;
  error_code?: string | null;
}

export interface FileValidationResult {
  isValid: boolean;
  error: string | null;
}

export interface PinsTextValidationResult {
  isValid: boolean;
  pins: string[];
  duplicateCount: number;
  emptyLinesCount: number;
  error: string | null;
}

const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB
const ALLOWED_EXTENSIONS = [".csv", ".xlsx", ".xls"];

/**
 * Validates file size and format before upload to the server.
 */
export function validateBulkImportFile(file: File | null | undefined): FileValidationResult {
  if (!file) {
    return { isValid: false, error: "لطفاً یک فایل انتخاب کنید." };
  }

  const fileName = file.name.toLowerCase();
  const hasValidExt = ALLOWED_EXTENSIONS.some((ext) => fileName.endsWith(ext));
  if (!hasValidExt) {
    return {
      isValid: false,
      error: "فرمت فایل مجاز نیست. فقط فایل‌های CSV، XLSX یا XLS پذیرفته می‌شوند.",
    };
  }

  if (file.size > MAX_FILE_SIZE_BYTES) {
    return {
      isValid: false,
      error: "حجم فایل بیشتر از سقف مجاز (۱۰ مگابایت) است.",
    };
  }

  if (file.size === 0) {
    return {
      isValid: false,
      error: "فایل انتخاب‌شده خالی است.",
    };
  }

  return { isValid: true, error: null };
}

/**
 * Validates pasted PINs/credentials text, detecting duplicates and blank lines.
 */
export function validatePastedPins(text: string): PinsTextValidationResult {
  if (!text || !text.trim()) {
    return {
      isValid: false,
      pins: [],
      duplicateCount: 0,
      emptyLinesCount: 0,
      error: "هیچ کدی برای بارگذاری وارد نشده است.",
    };
  }

  const rawLines = text.split(/\r?\n/);
  const seen = new Set<string>();
  const pins: string[] = [];
  let duplicateCount = 0;
  let emptyLinesCount = 0;

  for (const line of rawLines) {
    const trimmed = line.trim();
    if (!trimmed) {
      emptyLinesCount++;
      continue;
    }
    if (seen.has(trimmed)) {
      duplicateCount++;
    } else {
      seen.add(trimmed);
      pins.push(trimmed);
    }
  }

  if (pins.length === 0) {
    return {
      isValid: false,
      pins: [],
      duplicateCount,
      emptyLinesCount,
      error: "تمام خطوط وارد شده خالی هستند.",
    };
  }

  return {
    isValid: true,
    pins,
    duplicateCount,
    emptyLinesCount,
    error: null,
  };
}

/**
 * Filters and formats row-level issues for presentation in the UI.
 */
export function extractRowErrors(details: BulkImportRowResult[] = []): BulkImportRowResult[] {
  return details.filter((d) => d.status === "error" || d.status === "duplicate_skipped");
}
