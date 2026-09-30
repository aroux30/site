import type { ReactNode } from "react";

/**
 * Accounting feed section shell. Detail routes (``journal/[id]``) render under
 * this layout, so the section's own header language stays in one place.
 */
export default function AccountingLayout({ children }: { children: ReactNode }) {
  return <div className="space-y-6">{children}</div>;
}
