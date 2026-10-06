"use client";

import React from "react";
import { TriangleAlert, CircleCheck, CircleHelp, CircleX } from "lucide-react";
import { useLang } from "@/lib/i18n";
import type { AnalysisRecord } from "@/lib/analysis";
import { ReportSection } from "@/components/ReportShell";

export default function ModelScoresCard({ record }: { record: AnalysisRecord }) {
  const { t, lang } = useLang();
  const section = record.sections.model_scores;
  const banded = record.verdict.models_banded ?? [];

  /* Majority among DECISIVE calls only — an "uncertain" model neither votes
   * for the majority nor can carry the outlier badge. The backend verdict
   * engine already ships band.outlier with this rule; this local fallback
   * keeps old records (without the field) consistent. */
  const decisiveCounts: Record<string, number> = {};
  for (const b of banded) {
    if (b.call === "flag" || b.call === "clear")
      decisiveCounts[b.call] = (decisiveCounts[b.call] ?? 0) + 1;
  }
  const top = Math.max(0, ...Object.values(decisiveCounts));
  const leaders = Object.entries(decisiveCounts).filter(([, n]) => n === top);
  const localMajority =
    leaders.length === 1 && Object.keys(decisiveCounts).length > 1 ? leaders[0][0] : null;

  const callChip = (call?: string) => {
    if (call === "flag")
      return (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-mono border border-[#ff4d6a]/50 text-[#ff8fa3] bg-[#ff4d6a]/10">
          <TriangleAlert className="w-3 h-3" /> {t("ms_call_flag")}
        </span>
      );
    if (call === "clear")
      return (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-mono border border-[#3dffa0]/40 text-[#8fffc9] bg-[#3dffa0]/10">
          <CircleCheck className="w-3 h-3" /> {t("ms_call_clear")}
        </span>
      );
    if (call === "uncertain")
      return (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-mono border border-[#ffc857]/40 text-[#ffe3a0] bg-[#ffc857]/10">
          <CircleHelp className="w-3 h-3" /> {t("ms_call_uncertain")}
        </span>
      );
    return null;
  };

  return (
    <ReportSection id="model-scores" titleKey="sec_scores" state={section?.state}>
      <div className="space-y-3">
        {record.models.map((model) => {
          const band = banded.find((b) => b.id === model.id);
          const isOutlier =
            band != null &&
            (band.outlier ??
              (localMajority !== null &&
                (band.call === "flag" || band.call === "clear") &&
                band.call !== localMajority));
          const hasResult = model.status === "ok" && model.prob_fake !== undefined;
          const pct =
            model.status === "ok" && model.prob_fake !== undefined
              ? Math.round(model.prob_fake * 1000) / 10
              : null;
          const isUncertain = band?.call === "uncertain";

          return (
            <div
              key={model.id}
              className="border border-[#12281f] bg-[#081210]/60 p-3.5 space-y-2"
            >
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="font-display font-bold text-sm text-[#d7efe2]">
                    {lang === "ar" ? model.label_ar : model.label_en}
                  </span>
                  <span className="px-1.5 py-0.5 text-[9px] font-mono uppercase border border-[#1d4534] text-[#3dffa0] bg-[#0a1613]">
                    {t("ms_kind_generation")}
                  </span>
                  <span className="px-1.5 py-0.5 text-[9px] font-mono border border-[#12281f] text-[#456355]">
                    {model.role === "primary" ? t("ms_role_primary") : t("ms_role_supporting")}
                  </span>
                  {isOutlier && (
                    <span className="px-1.5 py-0.5 text-[9px] font-mono border border-[#ffc857]/50 text-[#ffe3a0] bg-[#ffc857]/10">
                      {t("ms_outlier")}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {callChip(band?.call)}
                  {pct !== null && (
                    <span className="font-black tabular-nums text-lg text-white" dir="ltr">
                      {pct}%
                    </span>
                  )}
                </div>
              </div>

              {hasResult && pct !== null ? (
                <>
                  <div className="w-full bg-[#040806] h-2.5 overflow-hidden p-0.5" role="meter"
                       aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}
                       aria-label={`${model.id} ${t("ms_prob")}`}>
                    <div
                      className={`h-full transition-all duration-1000 ${
                        band?.call === "flag"
                          ? "bg-gradient-to-r from-[#ff4d6a]/70 to-[#ff4d6a]"
                          : band?.call === "clear"
                            ? "bg-gradient-to-r from-[#21d67e]/70 to-[#3dffa0]"
                            : "bg-gradient-to-r from-[#8a6d1f]/70 to-[#ffc857]"
                      }`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <p className="text-[10px] text-[#456355]">{t("ms_prob")}</p>
                  {model.default_value && (
                    <p className="text-[10px] text-[#ffe3a0] border border-[#ffc857]/40 bg-[#ffc857]/5 px-2 py-1">
                      {t("ms_default_note")}
                    </p>
                  )}
                  {isUncertain && (
                    <p className="text-[10px] text-[#7da291]">{t("ms_uncertain_reason")}</p>
                  )}
                </>
              ) : (
                <p className="text-xs text-[#7da291] flex items-center gap-1.5">
                  <CircleX className="w-3.5 h-3.5 text-[#ff8fa3]" />
                  {model.status === "skipped"
                    ? model.reason || t("state_skipped")
                    : model.error === "Model not loaded in this process."
                      ? t("ms_not_loaded")
                      : model.error || t("ms_error_generic")}
                </p>
              )}

              {/* ---- collapsible per-model details ---- */}
              <details className="text-[10px] text-[#7da291]">
                <summary className="cursor-pointer select-none inline-flex items-center gap-1.5 hover:text-[#8fffc9]">
                  <CircleHelp className="w-3 h-3" />
                  {t("ms_details")}
                </summary>
                <div className="mt-2 space-y-1 border-s-2 border-[#1d4534] ps-3">
                  <p className="flex justify-between gap-3">
                    <span>{t("ms_details_score4")}</span>
                    <span className="font-mono tabular-nums" dir="ltr">
                      {hasResult ? model.prob_fake?.toFixed(4) : t("ms_details_none")}
                    </span>
                  </p>
                  <p className="flex justify-between gap-3">
                    <span>{t("ms_details_logit")}</span>
                    <span className="font-mono tabular-nums" dir="ltr">
                      {model.logit !== undefined ? model.logit.toFixed(4) : t("ms_details_none")}
                    </span>
                  </p>
                  <p className="flex justify-between gap-3">
                    <span>{t("ms_details_weight")}</span>
                    <span className="font-mono tabular-nums" dir="ltr">
                      {model.weight != null ? model.weight : t("ms_details_none")}
                    </span>
                  </p>
                  <p className="flex justify-between gap-3">
                    <span>{t("ms_details_role")}</span>
                    <span>
                      {model.role === "primary"
                        ? t("ms_role_primary")
                        : model.role === "supporting"
                          ? t("ms_role_supporting")
                          : t("ms_details_none")}
                    </span>
                  </p>
                  {model.id === "face_v2" && (
                    <>
                      <p className="flex justify-between gap-3">
                        <span>{t("ms_details_faces")}</span>
                        <span className="font-mono tabular-nums" dir="ltr">
                          {model.face_count != null ? model.face_count : t("ms_details_none")}
                        </span>
                      </p>
                      <p className="flex justify-between gap-3">
                        <span>{t("ms_details_crops")}</span>
                        <span className="font-mono tabular-nums" dir="ltr">
                          {model.crop_count != null ? model.crop_count : t("ms_details_none")}
                        </span>
                      </p>
                    </>
                  )}
                </div>
              </details>
            </div>
          );
        })}
      </div>

      <p className="text-[11px] text-[#7da291] border-t border-[#12281f] pt-3 leading-relaxed">
        {t("ms_no_editing")}
      </p>
      <p className="text-[10px] text-[#456355] leading-relaxed">{t("ms_bands_note")}</p>
    </ReportSection>
  );
}
