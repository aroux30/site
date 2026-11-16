import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { BlocksPalette } from "@/components/admin/builder/blocks-palette";
import { pageTemplatesAdminApi } from "@/lib/api/content";
import { blockPatternsApi } from "@/lib/api/block-patterns";
import { useBuilderStore } from "@/stores/builder-store";

vi.mock("@/lib/api/block-patterns", () => ({
  blockPatternsApi: {
    list: vi.fn().mockResolvedValue([]),
    render: vi.fn().mockResolvedValue({ html: "<div>Pattern</div>" }),
  },
}));

vi.mock("@/lib/api/content", () => ({
  pageTemplatesAdminApi: {
    list: vi.fn(),
    delete: vi.fn(),
    update: vi.fn(),
  },
}));

describe("BlocksPalette - My Templates Management (P2.5)", () => {
  const mockTemplates = [
    {
      id: "tpl_hero_1",
      title: "قالب هیرو ویژه",
      slug: "hero-special",
      templateType: "section" as const,
      category: "هیرو",
      builderData: {
        schemaVersion: 1,
        title: "هیرو",
        slug: "hero",
        rootElements: [
          {
            id: "el_hero_cnt",
            name: "کانتینر اصلی هیرو",
            type: "container",
            isLocked: false,
            isHidden: false,
            styles: { mobile: {} },
            children: [],
          },
        ],
      },
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    (pageTemplatesAdminApi.list as any).mockResolvedValue(mockTemplates);
    useBuilderStore.getState().initPage("test-page", {
      schemaVersion: 1,
      title: "Test Page",
      slug: "test-page",
      globalStyles: {},
      rootElements: [],
    });
  });

  it("renders saved templates tab and shows template items", async () => {
    render(<BlocksPalette />);

    // Click on "قالب‌های من" tab
    const templatesTab = screen.getByText(/قالب‌های من/);
    fireEvent.click(templatesTab);

    // Wait for template to appear
    await waitFor(() => {
      expect(screen.getByText("قالب هیرو ویژه")).toBeDefined();
      expect(screen.getByText("هیرو")).toBeDefined();
    });
  });

  it("opens preview structure dialog when eye icon is clicked", async () => {
    render(<BlocksPalette />);

    fireEvent.click(screen.getByText(/قالب‌های من/));

    await waitFor(() => {
      expect(screen.getByText("قالب هیرو ویژه")).toBeDefined();
    });

    const previewButton = screen.getByTitle("پیش‌نمایش ساختار قالب");
    fireEvent.click(previewButton);

    await waitFor(() => {
      expect(screen.getByText(/پیش‌نمایش ساختار قالب «قالب هیرو ویژه»/)).toBeDefined();
      expect(screen.getByText("درج این قالب در بوم")).toBeDefined();
    });
  });

  it("opens edit dialog and calls update API on save", async () => {
    (pageTemplatesAdminApi.update as any).mockResolvedValue({
      ...mockTemplates[0],
      title: "قالب هیرو ویرایش شده",
    });

    render(<BlocksPalette />);

    fireEvent.click(screen.getByText(/قالب‌های من/));

    await waitFor(() => {
      expect(screen.getByText("قالب هیرو ویژه")).toBeDefined();
    });

    const editButton = screen.getByTitle("ویرایش عنوان و دسته‌بندی");
    fireEvent.click(editButton);

    await waitFor(() => {
      expect(screen.getByText("ویرایش مشخصات قالب")).toBeDefined();
    });

    const saveButton = screen.getByText("ذخیره تغییرات");
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(pageTemplatesAdminApi.update).toHaveBeenCalledWith("tpl_hero_1", {
        title: "قالب هیرو ویژه",
        category: "هیرو",
      });
    });
  });

  it("calls delete API when trash button is clicked", async () => {
    (pageTemplatesAdminApi.delete as any).mockResolvedValue(undefined);

    render(<BlocksPalette />);

    fireEvent.click(screen.getByText(/قالب‌های من/));

    await waitFor(() => {
      expect(screen.getByText("قالب هیرو ویژه")).toBeDefined();
    });

    const deleteButton = screen.getByTitle("حذف قالب");
    fireEvent.click(deleteButton);

    await waitFor(() => {
      expect(pageTemplatesAdminApi.delete).toHaveBeenCalledWith("tpl_hero_1");
    });
  });
});
