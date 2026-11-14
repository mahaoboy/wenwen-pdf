"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getToken } from "@/lib/auth";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    router.replace(getToken() ? "/docs" : "/login");
  }, [router]);

  return (
    <div className="grid min-h-dvh place-items-center text-sm text-slate-400">
      正在进入文问…
    </div>
  );
}
