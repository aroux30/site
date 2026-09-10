"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function AccountFavoritesRedirect() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/favorites");
  }, [router]);

  return (
    <div className="flex items-center justify-center min-h-[300px]">
      <div className="w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}
