"use client";

import React, { useState } from "react";
import {
  AlertTriangle,
  ShieldCheck,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  Copy,
  CheckCircle2,
  Info,
} from "lucide-react";
import { useLang } from "@/lib/i18n";
import MultiAspectChart from "@/components/MultiAspectChart";
import type { AnalysisRecord, ReportAxis } from "@/lib/analysis";

const LABEL_KEYS = {
  "AI Detected": "v_ai_detected",
  "Possible Edits": "v_possible_edits",
  Investigate: "v_investigate",
  "No AI Detected": "v_no_ai",
} as const;

const AXIS_KEYS = {
  ai_generation: "axis_ai_gen",
  editing_check: "axis_editing",
  source_check: "axis_source",
} as const;

const fmt = (template: string, vars: Record<string, string | number>) =>
  template.replace(/\{(\w+)\}/g, (_m, k) => String(vars[k] ?? `{${k}}`));

export default function VerdictCard({ record }: { record: AnalysisRecord }) {
  const { t, lang } = useLang();
  const [showReasoning, setShowReasoning] = useState(false);
  const [openAxis, setOpenAxis] = useState<string | null>(null);
  const [copied, setCopied] = useState<boolean | null>(null);

  const verdict = record.verdict;
  const label = verdict.label ?? "Investigate";
  const labelKey = LABEL_KEYS[label as keyof typeof LABEL_KEYS] ?? "v_investigate";
  const counts = verdict.counts ?? {};
  const exifCheck = record.forensics.checks.find((c) => c.id === "exif");
  const c2paCheck = record.forensics.checks.find((c) => c.id === "c2pa");
  const hashCheck = record.forensics.checks.find((c) => c.id === "hash_db");
  const tech = record.technical_info.data;

  const tone =
    label === "AI Detected"
      ? { text: "text-[#ff4d6a]", icon: AlertTriangle, glow: "bg-[#ff4d6a]" }
      : label === "No AI Detected"
        ? { text: "text-[#3dffa0]", icon: ShieldCheck, glow: "bg-[#3dffa0]" }
        : { text: "text-[#ffc857]", icon: HelpCircle, glow: "bg-[#ffc857]" };
  const ToneIcon = tone.icon;

  if (verdict.state === "error") {
    return (
      <section id="our-verdict" className="evidence-card chamfer p-5 border border-[#ff4d6a]/40">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#ff4d6a]">{t("state_error")}</p>
        <p className="text-sm text-[#ff8fa3] mt-2">{verdict.error || t("state_error")}</p>
      </section>
    );
  }
  if (verdict.state === "loading") {
    return (
      <section id="our-verdict" className="evidence-card chamfer p-5">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#7da291]">{t("state_loading")}…</p>
      </section>
    );
  }

  /* ---- HERE IS WHAT YOU SHOULD KNOW bullets (all from real record) ---- */
  const bullets: string[] = [];
  if (counts.signal_total !== undefined) {
    bullets.push(
      fmt(t("n_signals"), {
        flagged: counts.n_flag ?? 0,
        total: record.models.length,
        clear: counts.n_clear ?? 0,
      })
    );
  }
  bullets.push(verdict.disagreement.length > 0 ? t("vd_disagreement") : t("vd_no_disagreement"));
  const exifTags = exifCheck?.data?.exif ?? {};
  const camera = `${exifTags.make ?? ""} ${exifTags.model ?? ""}`.trim();
  if (exifCheck?.status === "ok") {
    bullets.push(
      exifCheck.data?.exif_present
        ? fmt(t("n_exif"), { camera: camera || "—", date: exifTags.datetime ?? "—" })
        : t("n_no_exif")
    );
  }
  const c2paData = c2paCheck?.data;
  if (c2paData?.found && c2paData.declares_generation) {
    bullets.push(fmt(t("n_c2pa_gen"), { generator: c2paData.generator ?? "unknown" }));
  }
  const generators = exifCheck?.data?.generator_signatures ?? [];
  if (generators.length > 0) {
    bullets.push(fmt(t("n_generator_sig"), { list: generators.join(", ") }));
  }
  if (hashCheck?.data?.match) {
    bullets.push(t("n_hash_match"));
  }
  if (record.quality && record.quality.tier && record.quality.tier !== "good") {
    bullets.push(fmt(t("n_quality"), { tier: record.quality.tier }));
  }

  /* ---- forensic narrative: conditional templates, honest phrasing ---- */
  const narrative: string[] = [];
  if (c2paData?.found && c2paData.declares_generation && c2paData.crypto_valid) {
    narrative.push(
      fmt(t("n_c2pa_gen"), { generator: c2paData.generator ?? "unknown" }) +
        (c2paData.trusted ? "" : ` (${t("vd_disclaimer")})`)
    );
  }
  if (generators.length > 0) {
    narrative.push(fmt(t("n_generator_sig"), { list: generators.join(", ") }));
  }
  if (exifCheck?.status === "ok" && !exifCheck.data?.exif_present) {
    narrative.push(t("n_no_exif"));
  } else if (exifCheck?.data?.exif_present) {
    narrative.push(fmt(t("n_exif"), { camera: camera || "—", date: exifTags.datetime ?? "—" }));
  }
  if (hashCheck?.data?.match) {
    narrative.push(t("n_hash_match"));
  }
  if ((counts.n_flag ?? 0) === 0 && (counts.n_working ?? 0) > 0) {
    narrative.push(t("n_models_clear"));
  }

  const copyVerdict = async () => {
    const text = [
      t(labelKey),
      verdict.why_rule ? verdict.why_rule[lang] : "",
      verdict.human_line ? verdict.human_line[lang] : "",
      `DeepGuard rule: ${verdict.rule_id ?? "-"}`,
    ]
      .filter(Boolean)
      .join("\n");
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(null), 2000);
    } catch {
      setCopied(false);
      setTimeout(() => setCopied(null), 2500);
    }
  };

  const renderAxis = (axis: ReportAxis) => {
    const key = AXIS_KEYS[axis.id];
    const body = axis.summary?.[lang] ?? axis.reason?.[lang] ?? "";
    const isOpen = openAxis === axis.id;
    return (
      <div key={axis.id} className="border border-[#12281f] bg-[#081210]/60">
        <button
          type="button"
          onClick={() => setOpenAxis(isOpen ? null : axis.id)}
          aria-expanded={isOpen}
          className="w-full flex items-center justify-between gap-3 px-4 py-3 text-start"
        >
          <span className="flex items-center gap-2 min-w-0">
            <span
              className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                axis.state === "ok"
                  ? axis.id === "ai_generation" && (counts.n_flag ?? 0) > 0
                    ? "bg-[#ff4d6a]"
                    : "bg-[#3dffa0]"
                  : "bg-[#456355]"
              }`}
            />
            <span className="font-semibold text-sm text-[#d7efe2] truncate">{t(key)}</span>
            <span className="font-mono text-[10px] text-[#456355] hidden sm:inline">
              {axis.state === "ok"
                ? t("state_ok")
                : axis.state === "not_applicable"
                  ? t("state_not_applicable")
                  : axis.state === "skipped"
                    ? t("state_skipped")
                    : t("state_error")}
            </span>
          </span>
          {isOpen ? <ChevronUp className="w-4 h-4 text-[#456355]" /> : <ChevronDown className="w-4 h-4 text-[#456355]" />}
        </button>
        {isOpen && <p className="px-4 pb-3 text-xs text-[#7da291] leading-relaxed">{body}</p>}
      </div>
    );
  };

  return (
    <section id="our-verdict" className="evidence-card chamfer relative overflow-hidden scroll-mt-24">
      <div className={`absolute -right-20 -top-20 w-64 h-64 rounded-full blur-3xl opacity-20 pointer-events-none ${tone.glow}`} />

      <div className="p-5 space-y-5 relative">
        {/* Header: big verdict + detection-type badge */}
        <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-[#12281f]">
          <div>
            <span className="font-mono text-[10px] tracking-[0.2em] uppercase text-[#7da291]">
              {t("sec_verdict")}
            </span>
            <h2 className={`font-display text-3xl font-black tracking-tight flex items-center gap-2 ${tone.text}`}>
              <ToneIcon className="w-7 h-7" />
              {t(labelKey)}
            </h2>
          </div>
          <div className="flex flex-col items-end gap-1.5">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-semibold bg-[#081210] border border-[#1d4534] text-[#3dffa0]">
              <Info className="w-3 h-3" /> {t("vd_badge_type")}: {t("vd_badge_generation")}
            </span>
            <div className="flex gap-1.5">
              <span className="px-2 py-0.5 text-[10px] font-mono bg-[#081210] border border-[#12281f] text-[#7da291]">
                {t("axis_editing")}
              </span>
              <span className="px-2 py-0.5 text-[10px] font-mono bg-[#081210] border border-[#12281f] text-[#7da291]">
                {t("axis_source")}
              </span>
            </div>
          </div>
        </div>

        {/* HERE IS WHAT YOU SHOULD KNOW */}
        <div className="border border-[#1d4534] bg-[#0a1613]/70 p-4 space-y-2">
          <h4 className="font-mono text-[11px] tracking-[0.16em] uppercase text-[#59e8ff]">
            {t("vd_should_know")}
          </h4>
          <ul className="space-y-1.5">
            {bullets.map((line, i) => (
              <li key={i} className="text-sm text-[#d7efe2] flex gap-2 leading-relaxed">
                <span className="text-[#3dffa0] mt-1" aria-hidden>›</span>
                <span>{line}</span>
              </li>
            ))}
          </ul>
          <p className="text-[11px] text-[#ffc857]/90 border-t border-[#12281f] pt-2 mt-2 leading-relaxed">
            {t("vd_disclaimer")}
          </p>
        </div>

        {/* Three axes (expandable) */}
        <div className="space-y-2" role="group" aria-label={t("sec_verdict")}>
          {verdict.axes.map(renderAxis)}
        </div>

        {/* Actions */}
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setShowReasoning((v) => !v)}
            aria-expanded={showReasoning}
            className="px-3 py-2 border border-[#12281f] text-[#7da291] hover:text-[#8fffc9] hover:border-[#1d4534] text-xs font-semibold transition flex items-center gap-1.5"
          >
            {showReasoning ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            {t("vd_reasoning")}
          </button>
          <button
            type="button"
            onClick={copyVerdict}
            className="px-3 py-2 bg-[#3dffa0]/10 hover:bg-[#3dffa0]/20 border border-[#3dffa0]/35 text-[#8fffc9] text-xs font-semibold transition flex items-center gap-1.5 [clip-path:polygon(7px_0,100%_0,100%_calc(100%-7px),calc(100%-7px) 100%,0 100%,0_7px)]"
          >
            {copied === true ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
            {copied === true ? t("vd_copied") : copied === false ? t("vd_copy_failed") : t("vd_copy")}
          </button>
        </div>

        {showReasoning && verdict.reasoning && (
          <p className="text-sm text-[#d7efe2] leading-relaxed border border-[#12281f] bg-[#040806] p-4">
            {verdict.reasoning[lang]}
          </p>
        )}

        {/* Human review line */}
        {verdict.human_line && (
          <div className="text-sm text-[#7da291] border-s-2 border-[#59e8ff]/60 ps-3">
            <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-[#59e8ff] block mb-1">
              {t("vd_human")}
            </span>
            {verdict.human_line[lang]}
          </div>
        )}

        {/* What the computer sees */}
        <div className="border border-[#12281f] bg-[#081210]/60 p-4 space-y-3">
          <h4 className="font-mono text-[11px] tracking-[0.16em] uppercase text-[#59e8ff]">
            {t("vd_computer")}
          </h4>
          {record.technical_info.state === "ok" && tech ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1.5 text-xs">
              <span className="text-[#456355]">{t("sec_technical")}</span>
              <span className="text-[#d7efe2] col-span-1 sm:col-span-2" dir="ltr">
                {tech.dimensions?.width}×{tech.dimensions?.height} · {tech.format} · {tech.aspect_ratio}
                {tech.jpeg_quality_estimate != null ? ` · Q≈${tech.jpeg_quality_estimate}` : ""}
              </span>
              <span className="text-[#456355]">EXIF</span>
              <span className="text-[#d7efe2] col-span-1 sm:col-span-2">
                {tech.exif_present
                  ? `${camera || "—"} ${exifTags.datetime ? `· ${exifTags.datetime}` : ""}`
                  : t("n_no_exif")}
              </span>
              <span className="text-[#456355]">{t("vd_web")}</span>
              <span className="text-[#456355] italic col-span-1 sm:col-span-2">{t("vd_not_checked")}</span>
            </div>
          ) : (
            <p className="text-xs text-[#456355]">
              {record.technical_info.error || t("state_not_applicable")}
            </p>
          )}
          {record.multi_aspect_scores && (
            <MultiAspectChart scores={record.multi_aspect_scores as any} />
          )}
        </div>

        {/* WHY THIS VERDICT */}
        <div className="border border-[#1d4534] bg-[#0a1613]/70 p-4 space-y-1.5">
          <h4 className="font-mono text-[11px] tracking-[0.16em] uppercase text-[#3dffa0]">{t("vd_why")}</h4>
          <p className="text-sm text-[#d7efe2] leading-relaxed">
            {verdict.why_rule ? verdict.why_rule[lang] : "—"}
          </p>
          {verdict.rule_id && (
            <p className="font-mono text-[10px] text-[#456355]" dir="ltr">
              rule: {verdict.rule_id}
            </p>
          )}
        </div>

        {/* Forensic narrative */}
        <div className="space-y-2">
          <h4 className="font-mono text-[11px] tracking-[0.16em] uppercase text-[#7da291]">{t("vd_narrative")}</h4>
          <ul className="space-y-1.5">
            {narrative.map((line, i) => (
              <li key={i} className="text-sm text-[#d7efe2]/90 leading-relaxed flex gap-2">
                <span className="text-[#456355] mt-1" aria-hidden>•</span>
                <span>{line}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Privacy line */}
        <p className="text-[11px] text-[#456355] border-t border-[#12281f] pt-3" dir="auto">
          {t("vd_privacy")}
        </p>
      </div>
    </section>
  );
}
