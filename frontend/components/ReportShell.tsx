"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronUp, ArrowUp, ImagePlus } from "lucide-react";
import { useLang } from "@/lib/i18n";
import type { SectionState } from "@/lib/analysis";

/* ------------------------------------------------------------------ */
/*  Section card — mono uppercase title, collapse toggle, back-link    */
/* ------------------------------------------------------------------ */

interface ReportSectionProps {
  id: string;
  titleKey: Parameters<ReturnType<typeof useLang>["t"]>[0];
  state?: SectionState;
  defaultOpen?: boolean;
  children: React.ReactNode;
}

export function ReportSection({ id, titleKey, state, defaultOpen = true, children }: ReportSectionProps) {
  const { t } = useLang();
  const [open, setOpen] = useState(defaultOpen);

  const stateBadge =
    state && state !== "ok" ? (
      <span
        className={`px-2 py-0.5 text-[10px] font-mono border ${
          state === "error"
            ? "border-[#ff4d6a]/50 text-[#ff8fa3] bg-[#ff4d6a]/10"
            : "border-[#1d4534] text-[#7da291] bg-[#081210]"
        }`}
      >
        {state === "skipped"
          ? t("state_skipped")
          : state === "not_applicable"
            ? t("state_not_applicable")
            : state === "error"
              ? t("state_error")
              : t("state_loading")}
      </span>
    ) : null;

  return (
    <section
      id={id}
      aria-label={t(titleKey)}
      className="evidence-card chamfer scroll-mt-24"
    >
      <div className="flex items-center justify-between gap-3 px-5 py-4 border-b border-[#12281f]">
        <div className="flex items-center gap-3 min-w-0">
          <h3 className="font-mono text-[11px] tracking-[0.18em] uppercase text-[#3dffa0] truncate">
            {t(titleKey)}
          </h3>
          {stateBadge}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <a
            href="#our-verdict"
            className="hidden sm:inline text-[10px] font-mono text-[#7da291] hover:text-[#8fffc9] border border-[#12281f] px-2 py-1 transition"
          >
            {t("back_to_verdict")}
          </a>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-controls={`${id}-body`}
            title={open ? t("card_collapse") : t("card_expand")}
            className="p-1.5 border border-[#12281f] text-[#7da291] hover:text-[#8fffc9] hover:border-[#1d4534] transition"
          >
            {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>
      {open && (
        <div id={`${id}-body`} className="p-5 space-y-4">
          {children}
        </div>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Shell — sticky top verdict bar + sticky image column + sections    */
/* ------------------------------------------------------------------ */

interface ReportShellProps {
  verdictLabel: string;
  verdictTone: "red" | "amber" | "green";
  imageUrl: string | null;
  imageName: string;
  onAnalyzeAnother: () => void;
  children: React.ReactNode;
}

const TONE_DOT: Record<ReportShellProps["verdictTone"], string> = {
  red: "bg-[#ff4d6a] shadow-[0_0_10px_#ff4d6a]",
  amber: "bg-[#ffc857] shadow-[0_0_10px_#ffc857]",
  green: "bg-[#3dffa0] shadow-[0_0_10px_#3dffa0]",
};

export default function ReportShell({
  verdictLabel,
  verdictTone,
  imageUrl,
  imageName,
  onAnalyzeAnother,
  children,
}: ReportShellProps) {
  const { t } = useLang();

  const scrollToVerdict = (e: React.MouseEvent) => {
    e.preventDefault();
    document.getElementById("our-verdict")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Sticky mini bar: current verdict + back link */}
      <div className="sticky top-0 z-30 -mx-2 px-4 py-2.5 bg-[#050a08]/95 backdrop-blur border border-[#12281f] flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0" title={t("rep_verdict_dot")}>
          <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${TONE_DOT[verdictTone]}`} aria-hidden />
          <span className="font-display font-bold text-sm text-white truncate">{verdictLabel}</span>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <a
            href="#our-verdict"
            onClick={scrollToVerdict}
            className="text-[10px] font-mono text-[#7da291] hover:text-[#8fffc9] border border-[#12281f] px-2 py-1 transition"
          >
            {t("back_to_verdict")}
          </a>
          <button
            type="button"
            onClick={onAnalyzeAnother}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#3dffa0]/10 hover:bg-[#3dffa0]/20 border border-[#3dffa0]/35 text-[#8fffc9] text-[11px] font-semibold transition [clip-path:polygon(7px_0,100%_0,100%_calc(100%-7px),calc(100%-7px) 100%,0 100%,0_7px)]"
          >
            <ImagePlus className="w-3.5 h-3.5" /> {t("rep_analyze_another")}
          </button>
        </div>
      </div>

      {/* Two columns: sticky specimen | sections */}
      <div className="grid grid-cols-1 lg:grid-cols-[320px_minmax(0,1fr)] gap-6 items-start">
        <aside className="lg:sticky lg:top-20 space-y-4">
          <div className="evidence-card chamfer p-4 space-y-3">
            {imageUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={imageUrl}
                alt={imageName}
                className="w-full max-h-[380px] object-contain border border-[#12281f] bg-[#040806]"
              />
            ) : (
              <div className="w-full h-48 border border-dashed border-[#1d4534] flex items-center justify-center text-[#456355] text-xs">
                {t("state_loading")}
              </div>
            )}
            <p className="font-mono text-[10px] text-[#7da291] truncate" title={imageName}>
              {imageName}
            </p>
            <button
              type="button"
              onClick={onAnalyzeAnother}
              className="w-full flex items-center justify-center gap-1.5 px-3 py-2 bg-[#3dffa0]/10 hover:bg-[#3dffa0]/20 border border-[#3dffa0]/35 text-[#8fffc9] text-xs font-semibold transition [clip-path:polygon(7px_0,100%_0,100%_calc(100%-7px),calc(100%-7px) 100%,0 100%,0_7px)]"
            >
              <ImagePlus className="w-3.5 h-3.5" /> {t("rep_analyze_another")}
            </button>
            <a
              href="#our-verdict"
              onClick={scrollToVerdict}
              className="w-full flex items-center justify-center gap-1.5 px-3 py-2 border border-[#12281f] text-[#7da291] hover:text-[#8fffc9] text-xs font-mono transition"
            >
              <ArrowUp className="w-3.5 h-3.5" /> {t("back_to_verdict")}
            </a>
          </div>
        </aside>

        <div className="space-y-6 min-w-0">{children}</div>
      </div>
    </div>
  );
}
