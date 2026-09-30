import { NewsletterTokenAction } from "@/components/shared/newsletter-token-action";

interface ConfirmPageProps {
  searchParams: Promise<{ token?: string; email?: string }>;
}

export default async function NewsletterConfirmPage({
  searchParams,
}: ConfirmPageProps) {
  const { token = null, email = null } = await searchParams;
  return <NewsletterTokenAction mode="confirm" token={token} email={email} />;
}
