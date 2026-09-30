import type { Metadata } from "next";
import { CapabilityRegistry } from "@/components/admin/capability-registry";

export const metadata: Metadata = {
  title: "فهرست قابلیت‌های یکپارچه‌سازی | پنل مدیریت",
  description:
    "وضعیت اعلام‌شده قابلیت‌های یکپارچه‌سازی سمت سرور، بدون نمایش اطلاعات محرمانه.",
};

export default function AdminIntegrationsPage() {
  return <CapabilityRegistry />;
}