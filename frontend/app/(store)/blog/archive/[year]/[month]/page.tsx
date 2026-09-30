import ArchivePage from "../../[year]/page";

/** Month archive, e.g. /blog/archive/2026/09.
 *
 * The year page already handles an optional month segment, so this only
 * forwards the params rather than duplicating the render.
 */
export default function MonthArchivePage({
  params,
}: {
  params: Promise<{ year: string; month: string }>;
}) {
  return <ArchivePage params={params} />;
}
