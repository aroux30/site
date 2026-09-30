import validator from "validator";

/**
 * Security validation suite based on Validator.js
 * Provides input sanitization and verification against injection and malformed input.
 */
export const SecurityValidator = {
  /**
   * Validate email address format and normalize it
   */
  isValidEmail(email: string | null | undefined): boolean {
    if (!email) return false;
    return validator.isEmail(email.trim());
  },

  /**
   * Normalize email to lowercase and trim
   */
  normalizeEmail(email: string): string {
    return validator.normalizeEmail(email.trim()) || email.trim().toLowerCase();
  },

  /**
   * Verify strong password criteria (min 8 chars, 1 uppercase, 1 lowercase, 1 number)
   */
  isStrongPassword(password: string): boolean {
    return validator.isStrongPassword(password, {
      minLength: 8,
      minLowercase: 1,
      minUppercase: 0, // optional uppercase for ease of use in Persian keyboards
      minNumbers: 1,
      minSymbols: 0,
    });
  },

  /**
   * Validate safe web URL
   */
  isValidUrl(url: string | null | undefined): boolean {
    if (!url) return false;
    return validator.isURL(url.trim(), {
      protocols: ["http", "https"],
      require_protocol: true,
    });
  },

  /**
   * Escape HTML special characters to prevent injection
   */
  escape(text: string): string {
    return validator.escape(text);
  },

  /**
   * Check if string contains only Persian/Arabic or English alphanumeric chars
   */
  isSafeString(input: string): boolean {
    // Rejects control characters, null bytes, and suspicious script tags
    if (/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/.test(input)) {
      return false;
    }
    return !/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi.test(input);
  },
};

export default SecurityValidator;
