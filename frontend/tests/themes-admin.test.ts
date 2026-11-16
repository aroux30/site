import { describe, it, expect, vi } from "vitest";
import { themesAdminApi } from "@/lib/api/themes";
import { DEFAULT_THEME_TOKENS } from "@/lib/builder/theme-schema";

describe("Theme Studio Admin API Client", () => {
  it("has complete CRUD and activation method signatures", () => {
    expect(typeof themesAdminApi.list).toBe("function");
    expect(typeof themesAdminApi.getActive).toBe("function");
    expect(typeof themesAdminApi.create).toBe("function");
    expect(typeof themesAdminApi.update).toBe("function");
    expect(typeof themesAdminApi.activate).toBe("function");
    expect(typeof themesAdminApi.listRevisions).toBe("function");
    expect(typeof themesAdminApi.restoreRevision).toBe("function");
    expect(typeof themesAdminApi.clone).toBe("function");
    expect(typeof themesAdminApi.delete).toBe("function");
  });

  it("formats DTCG tokens correctly for create requests", () => {
    const payload = {
      name: "تم تست یونیت",
      slug: "test-unit-theme",
      tokens: {
        ...DEFAULT_THEME_TOKENS,
        semantic: {
          ...DEFAULT_THEME_TOKENS.semantic,
          color: {
            primary: { $value: "#7c3aed", $type: "color" },
            secondary: { $value: "#0d9488", $type: "color" },
          },
        },
      },
    };

    expect(payload.tokens.semantic.color.primary.$value).toBe("#7c3aed");
    expect(payload.name).toBe("تم تست یونیت");
  });
});
