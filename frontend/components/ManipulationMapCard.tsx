"use client";

import React, { useState } from "react";
import { Layers } from "lucide-react";
import { useLang } from "@/lib/i18n";
import type { AnalysisRecord } from "@/lib/analysis";
import { ReportSection } from "@/components/ReportShell";

type LayerMode = "original" | "ela" | "blend";

export default function ManipulationMapCard({
  record,
  imageUrl,
}: {
  record: AnalysisRecord;
  imageUrl: string | null;
}) {
  const { t, lang } = useLang();
  const section = record.sections.manipulation_map;
  const ela = record.forensics.checks.find((c) => c.id === "ela");
  const [mode, setMode] = useState<LayerMode>("blend");
  const [opacity, setOpacity] = useState(0.6);

  const mapB64 = ela?.status === "ok" ? ela.data?.map_png_base64 : null;

  const body =
    section?.state === "skipped" ? (
      <p className="text-xs text-[#7da291]">{section.reason || t("state_skipped")}</p>
    ) : ela?.status !== "ok" ? (
      <p className="text-xs text-[#7da291]">
        {ela?.status === "error" ? ela.error : ela?.reason || t("state_not_applicable")}
      </p>
    ) : !mapB64 ? (
      <p className="text-xs text-[#7da291]">{t("mm_unavailable")}</p>
    ) : (
      <div className="space-y-3">
        {/* Layer controls */}
        <div
          className="inline-flex items-center gap-1 p-1 bg-[#080c10] border border-[#122b20] rounded-full"
          role="group"
          aria-label={t("sec_map")}
          dir="ltr"
        >
          {([
            { id: "original", key: "mm_original" as const },
            { id: "ela", key: "mm_ela" as const },
            { id: "blend", key: "mm_blend" as const },
          ]).map(({ id, key }) => (
            <button
              key={id}
              type="button"
              aria-pressed={mode === id}
              onClick={() => setMode(id as LayerMode)}
              className={`px-3 h-7 rounded-full text-[11px] font-semibold transition-all ${
                mode === id
                  ? "bg-[#00ff9d] text-[#080c10] shadow-[0_0_12px_rgba(0,255,157,0.35)]"
                  : "text-[#7da291] hover:text-[#8fffc9]"
              }`}
            >
              {t(key)}
            </button>
          ))}
        </div>

        {mode === "blend" && (
          <label className="flex items-center gap-3 text-xs text-[#7da291]">
            <span className="font-mono text-[10px] uppercase">{t("mm_opacity")}</span>
            <input
              type="range"
              min={0}
              max={100}
              value={Math.round(opacity * 100)}
              onChange={(e) => setOpacity(Number(e.target.value) / 100)}
              className="flex-1 accent-[#3dffa0]"
              aria-label={t("mm_opacity")}
            />
            <span className="tabular-nums w-9 text-end" dir="ltr">{Math.round(opacity * 100)}%</span>
          </label>
        )}

        {/* Stacked layers */}
        <div className="relative border border-[#12281f] bg-[#040806] inline-block max-w-full">
          {imageUrl && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={imageUrl} alt={t("mm_original")} className="block max-h-[420px] max-w-full object-contain" />
          )}
          {(mode === "ela" || mode === "blend") && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={`data:image/png;base64,${mapB64}`}
              alt={t("mm_ela")}
              className="absolute inset-0 w-full h-full object-contain transition-opacity duration-300"
              style={{ opacity: mode === "ela" ? 1 : opacity }}
            />
          )}
          <span className="absolute bottom-1 start-1 font-mono text-[9px] px-1.5 py-0.5 bg-[#050a08]/85 text-[#7da291] border border-[#12281f] flex items-center gap-1">
            <Layers className="w-3 h-3" />
            {mode === "original" ? t("mm_original") : mode === "ela" ? t("mm_ela") : t("mm_blend")}
          </span>
        </div>

        <p className="text-xs text-[#7da291] leading-relaxed">{t("mm_ela_note")}</p>
        <p className="text-[11px] text-[#ffc857]/90 border-t border-[#12281f] pt-2 leading-relaxed">
          {t("mm_no_editing_model")}
        </p>
        {ela?.data?.ela_mean !== undefined && (
          <p className="font-mono text-[10px] text-[#456355]" dir="ltr">
            ELA mean={ela.data.ela_mean} · p99={ela.data.ela_p99} · border/interior={ela.data.border_interior_ratio}
          </p>
        )}
      </div>
    );

  return (
    <ReportSection id="manipulation-map" titleKey="sec_map" state={section?.state ?? "loading"}>
      {body}
    </ReportSection>
  );
}
