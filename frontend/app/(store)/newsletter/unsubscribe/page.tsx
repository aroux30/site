import { NewsletterTokenAction } from "@/components/shared/newsletter-token-action";

interface UnsubscribePageProps {
  searchParams: Promise<{ token?: string; email?: string }>;
}

export default async function NewsletterUnsubscribePage({
  searchParams,
}: UnsubscribePageProps) {
  const { token = null, email = null } = await searchParams;
  return <NewsletterTokenAction mode="unsubscribe" token={token} email={email} />;
}
