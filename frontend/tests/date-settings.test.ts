import { describe, it, expect, beforeEach } from "vitest";
import {
  DEFAULT_DATE_FORMAT,
  DEFAULT_TIME_FORMAT,
  DEFAULT_TIMEZONE,
  isValidTimeZone,
  phpToJalaliPattern,
  __resetDateSettingsCache,
  getDateSettings,
} from "@/lib/date-settings";

/**
 * The date_format / time_format options are seeded in PHP's date() vocabulary
 * ("Y/m/d", "H:i") while the formatter speaks date-fns-jalali ("yyyy/MM/dd",
 * "HH:mm"). These tests pin the translation, because a wrong mapping here is
 * silent: the date still renders, just with the parts in the wrong order.
 */

describe("phpToJalaliPattern", () => {
  beforeEach(() => {
    __resetDateSettingsCache();
  });

  it("maps the seeded date format", () => {
    expect(phpToJalaliPattern("Y/m/d")).toBe("yyyy/MM/dd");
  });

  it("maps the seeded time format", () => {
    expect(phpToJalaliPattern("H:i")).toBe("HH:mm");
  });

  it("keeps separators", () => {
    expect(phpToJalaliPattern("d/m/Y")).toBe("dd/MM/yyyy");
    expect(phpToJalaliPattern("Y-m-d")).toBe("yyyy-MM-dd");
  });

  it("maps single-character day and month forms", () => {
    // PHP's d/j and m/n are the unpadded forms.
    expect(phpToJalaliPattern("j/n/Y")).toBe("d/M/yyyy");
  });

  it("maps the meridiem forms", () => {
    expect(phpToJalaliPattern("g:i a")).toBe("h:mm aa");
  });

  it("treats a backslash escape as a literal", () => {
    // PHP's \Y is a literal Y, not the year.
    expect(phpToJalaliPattern("\\Y")).toBe("Y");
  });

  it("passes an already-modern pattern through unchanged", () => {
    // A store that already wrote the date-fns form must not be mangled.
    expect(phpToJalaliPattern("yyyy/MM/dd")).toBe("yyyy/MM/dd");
    expect(phpToJalaliPattern("HH:mm")).toBe("HH:mm");
  });

  it("falls back for an empty or unusable value", () => {
    expect(phpToJalaliPattern("")).toBe(DEFAULT_DATE_FORMAT);
    expect(phpToJalaliPattern("/")).toBe("/");
  });
});

describe("isValidTimeZone", () => {
  it("accepts a real zone", () => {
    expect(isValidTimeZone(DEFAULT_TIMEZONE)).toBe(true);
    expect(isValidTimeZone("UTC")).toBe(true);
  });

  it("rejects an unknown zone instead of letting Intl throw", () => {
    // Intl.DateTimeFormat throws on an unknown zone, so an unchecked value from
    // the options table would take down every page that renders a date.
    expect(isValidTimeZone("Mars/Olympus_Mons")).toBe(false);
    expect(isValidTimeZone("")).toBe(false);
  });
});

describe("defaults", () => {
  beforeEach(() => {
    __resetDateSettingsCache();
  });

  it("are what the date helpers used to hardcode", () => {
    const s = getDateSettings();
    expect(s.dateFormat).toBe(DEFAULT_DATE_FORMAT);
    expect(s.timeFormat).toBe(DEFAULT_TIME_FORMAT);
    expect(s.timezone).toBe(DEFAULT_TIMEZONE);
  });

  it("start unloaded, so a first render uses the defaults", () => {
    expect(getDateSettings().loaded).toBe(false);
  });
});
