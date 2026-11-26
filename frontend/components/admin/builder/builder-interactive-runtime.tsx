"use client";

import { useEffect } from "react";

function toPersianDigits(num: number): string {
  return Math.max(0, Math.floor(num)).toLocaleString("fa-IR", {
    minimumIntegerDigits: 2,
    useGrouping: false,
  });
}

function updateCountdowns() {
  const nodes = document.querySelectorAll<HTMLElement>(
    '.builder-rendered-content [data-widget="countdown"][data-target]'
  );
  const now = Date.now();

  nodes.forEach((node) => {
    const targetRaw = node.getAttribute("data-target") || "";
    const targetMs = Date.parse(targetRaw);
    if (!targetRaw || Number.isNaN(targetMs)) return;

    const diffMs = Math.max(0, targetMs - now);
    const d = Math.floor(diffMs / 86_400_000);
    const h = Math.floor((diffMs % 86_400_000) / 3_600_000);
    const m = Math.floor((diffMs % 3_600_000) / 60_000);
    const s = Math.floor((diffMs % 60_000) / 1000);

    const values: Record<string, string> = {
      days: toPersianDigits(d),
      hours: toPersianDigits(h),
      minutes: toPersianDigits(m),
      seconds: toPersianDigits(s),
    };

    const unitEls = node.querySelectorAll<HTMLElement>("[data-cd-unit]");
    if (unitEls.length > 0) {
      unitEls.forEach((el) => {
        const key = el.getAttribute("data-cd-unit") || "";
        const val = values[key];
        if (val !== undefined) {
          el.textContent = val;
        }
      });
    } else {
      // Positional fallback if compiled markup lacks data-cd-unit
      const digitSpans = node.querySelectorAll<HTMLElement>("div[dir='ltr'] > div > span:first-child");
      const order = ["days", "hours", "minutes", "seconds"] as const;
      order.forEach((key, idx) => {
        const span = digitSpans[idx];
        const val = values[key];
        if (span && val !== undefined) {
          span.textContent = val;
        }
      });
    }

    const expiredText = node.getAttribute("data-expired-text") || "این مهلت به پایان رسید!";
    let expiredBanner = node.querySelector<HTMLElement>("[data-cd-expired]");
    if (diffMs <= 0) {
      if (!expiredBanner) {
        expiredBanner = document.createElement("p");
        expiredBanner.setAttribute("data-cd-expired", "1");
        expiredBanner.className = "text-xs font-bold text-destructive pt-1";
        node.appendChild(expiredBanner);
      }
      expiredBanner.textContent = expiredText;
    } else if (expiredBanner) {
      expiredBanner.remove();
    }
  });
}

export function BuilderInteractiveRuntime({ pageSlug }: { pageSlug?: string }) {
  useEffect(() => {
    updateCountdowns();
    const timer = window.setInterval(updateCountdowns, 1000);

    const handleClick = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null;
      if (!target) return;

      const root = target.closest(".builder-rendered-content");
      if (!root) return;

      const tabWidget = target.closest<HTMLElement>(
        '[data-widget="tabs"], [data-widget="nested_tabs"], .builder-tabs, .builder-nested-tabs'
      );
      if (!tabWidget) return;

      const btn = target.closest<HTMLButtonElement>("button");
      if (!btn || !tabWidget.contains(btn)) return;

      const headerBar = btn.parentElement;
      if (!headerBar) return;
      const buttons = Array.from(headerBar.children).filter(
        (el): el is HTMLButtonElement => el.tagName === "BUTTON"
      );
      const clickedIdxAttr = btn.getAttribute("data-tab-index");
      const activeIdx =
        clickedIdxAttr !== null ? Number(clickedIdxAttr) : buttons.indexOf(btn);
      if (Number.isNaN(activeIdx) || activeIdx < 0) return;

      buttons.forEach((b, i) => {
        const isActive = i === activeIdx;
        b.setAttribute("aria-selected", isActive ? "true" : "false");
        b.classList.toggle("border-primary", isActive);
        b.classList.toggle("text-primary", isActive);
        b.classList.toggle("bg-background", isActive);
        b.classList.toggle("border-transparent", !isActive);
        b.classList.toggle("text-muted-foreground", !isActive);
      });

      const paneContainer = tabWidget.querySelector<HTMLElement>(".tab-contents, .tab-panes");
      if (!paneContainer) return;
      const panes = Array.from(paneContainer.children).filter(
        (el): el is HTMLElement => el instanceof HTMLElement
      );
      panes.forEach((pane, i) => {
        const paneIdxAttr = pane.getAttribute("data-tab-pane");
        const paneIdx = paneIdxAttr !== null ? Number(paneIdxAttr) : i;
        pane.classList.toggle("hidden", paneIdx !== activeIdx);
      });
    };

    const handleSubmit = async (event: SubmitEvent) => {
      const form = event.target as HTMLFormElement | null;
      if (!form || !form.matches('form[data-form-container="true"]')) return;
      if (!form.closest(".builder-rendered-content")) return;

      event.preventDefault();
      if (typeof form.reportValidity === "function" && !form.reportValidity()) {
        return;
      }

      const submitBtn = form.querySelector<HTMLButtonElement>('button[type="submit"]');
      const originalLabel = submitBtn?.textContent || "";
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = "در حال ارسال...";
      }

      let statusEl = form.querySelector<HTMLElement>("[data-form-status]");
      if (!statusEl) {
        statusEl = document.createElement("div");
        statusEl.setAttribute("data-form-status", "1");
        form.appendChild(statusEl);
      }

      const rawData: Record<string, unknown> = {};
      const fd = new FormData(form);
      fd.forEach((val, key) => {
        if (key === "_hp_website") return;
        rawData[key] = typeof val === "string" ? val : val.name;
      });
      form.querySelectorAll<HTMLInputElement>('input[type="checkbox"][name]').forEach((cb) => {
        if (cb.name && cb.name !== "_hp_website") {
          rawData[cb.name] = cb.checked;
        }
      });

      const action = form.getAttribute("action") || "/api/v1/content/forms/submit";
      const successMsg =
        form.getAttribute("data-success-message") || "پیام شما با موفقیت ثبت شد.";
      const errorMsg =
        form.getAttribute("data-error-message") || "خطا در ارسال فرم. لطفاً مجدداً تلاش کنید.";

      try {
        const res = await fetch(action, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            form_id: form.id || "builder_form",
            page_slug: pageSlug || undefined,
            data: rawData,
          }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        statusEl.className =
          "mt-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs font-medium text-emerald-700 dark:text-emerald-300";
        statusEl.textContent = successMsg;
        form.reset();
      } catch {
        statusEl.className =
          "mt-3 rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs font-medium text-destructive";
        statusEl.textContent = errorMsg;
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = originalLabel;
        }
      }
    };

    document.addEventListener("click", handleClick);
    document.addEventListener("submit", handleSubmit);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("click", handleClick);
      document.removeEventListener("submit", handleSubmit);
    };
  }, [pageSlug]);

  return null;
}
