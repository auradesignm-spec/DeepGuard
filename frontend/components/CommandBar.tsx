"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Shield } from "lucide-react";
import { useLang, LanguageToggle, type DictKey } from "@/lib/i18n";

/* ------------------------------------------------------------------ */
/*  CommandBar — the shared forensic header.                           */
/*  Quiet, precise, single-accent. Brand seal + nav + language toggle.  */
/* ------------------------------------------------------------------ */

function useScrollProgress(): number {
  const [pct, setPct] = useState(0);
  useEffect(() => {
    const onScroll = () => {
      const h = document.documentElement;
      const max = h.scrollHeight - h.clientHeight;
      setPct(max > 0 ? Math.min(100, (h.scrollTop / max) * 100) : 0);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return pct;
}

export default function CommandBar({ variant = "landing" }: { variant?: "landing" | "dashboard" }) {
  const { t } = useLang();
  const progress = useScrollProgress();
  const isLanding = variant === "landing";

  const navLinks: { href: string; labelKey: DictKey }[] = [
    { href: "#detectors", labelKey: "nav_features" },
    { href: "#pipeline", labelKey: "nav_how" },
    { href: "#simulator", labelKey: "nav_sim" },
    { href: "#faq", labelKey: "nav_faq" },
  ];

  return (
    <>
      {/* scroll progress hairline */}
      <div className="scroll-rail" aria-hidden="true">
        <div style={{ width: `${progress}%` }} />
      </div>

      <header className="glass-bar sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-5 h-[64px] flex items-center justify-between gap-6">
          {/* brand */}
          <Link href={isLanding ? "/landing" : "/"} className="flex items-center gap-3 group shrink-0">
            <span className="relative w-9 h-9 grid place-items-center bg-[#0a1613] border border-[#1d4534] transition-all duration-300 group-hover:border-[#3dffa0]/70 group-hover:shadow-[0_0_16px_rgba(61,255,160,0.25)]">
              <Shield className="w-[17px] h-[17px] text-[#3dffa0]" strokeWidth={2.2} />
            </span>
            <span className="leading-none">
              <span className="block font-display font-bold tracking-[0.18em] text-white text-[15px]" dir="ltr">
                DEEP<span className="text-[#2EE59D]">GUARD</span>
              </span>
            </span>
          </Link>

          {/* section nav — landing only */}
          {isLanding && (
            <nav className="hidden lg:flex items-center gap-10 text-[13px] font-medium text-[#7da291]">
              {navLinks.map((l) => (
                <a
                  key={l.href}
                  href={l.href}
                  className="py-1 transition-all duration-300 hover:text-[#00ff9d]"
                >
                  {t(l.labelKey)}
                </a>
              ))}
            </nav>
          )}

          <div className="flex items-center gap-3 sm:gap-4 shrink-0">
            <LanguageToggle />

            {isLanding ? (
              <Link href="/" className="btn-cta px-6 py-2.5 text-[13px] hidden sm:inline-block rounded-xl">
                {t("nav_open")}
              </Link>
            ) : (
              <Link href="/landing" className="btn-ghost px-4 py-2 text-[12px] hidden sm:inline-block">
                {t("dash_about")}
              </Link>
            )}
          </div>
        </div>
      </header>
    </>
  );
}
