import { redirect } from "next/navigation";

/**
 * The kanban board moved into `/admin/orders` as its second view (owner
 * order 2026-10-10: one menu entry, one page, two views). This route stays
 * as a redirect so bookmarks, the old sidebar link and any external link
 * keep working — a deleted route would 404 them.
 */
export default function AdminKanbanRedirect() {
  redirect("/admin/orders?view=board");
}
