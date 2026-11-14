import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import { AccountAuthGuard } from "@/components/account/account-auth-guard";
import { PluginWidgetLoader } from "@/components/chat/plugin-widget-loader";

export default function AccountLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1 bg-muted/30">
        <AccountAuthGuard>{children}</AccountAuthGuard>
      </main>
      <Footer />
      {/* B5: the plugin enqueues its widget on every frontend page; the account
          area is a separate layout and was missing it. */}
      <PluginWidgetLoader />
    </div>
  );
}
