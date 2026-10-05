"use client";

import React from "react";
import { ShieldAlert, ShieldCheck, HelpCircle, FileSearch, Globe, Quote, ListChecks, Microscope } from "lucide-react";
import { useLang, type DictKey } from "@/lib/i18n";

export interface NewsResult {
  status: string;
  verdict: string;
  misinformation_prob: number;
  confidence: number;
  extracted_text: string;
  ocr_available: boolean;
  text_analysis: {
    cues: Record<string, unknown>;
    legit_markers?: string[];
    has_date?: boolean;
    has_url?: boolean;
  };
  deep_analysis?: Record<
    string,
    { score: number; detail: Record<string, unknown> }
  >;
  forensic_fake_prob: number;
  image_provenance?: string;
  fact_check: {
    status: string;
    disputed: number;
    verified: number;
    results: { rating: string; publisher: string; url: string }[];
  };
  arbiter_audit: string[];
}

const VERDICT_META: Record<string, { color: string; bg: string; border: string; icon: React.ElementType; key: DictKey }> = {
  misleading: {
    color: "#ff4d6a",
    bg: "rgba(255,77,106,0.08)",
    border: "rgba(255,77,106,0.45)",
    icon: ShieldAlert,
    key: "news_verdict_misleading",
  },
  suspicious: {
    color: "#ffc857",
    bg: "rgba(255,200,87,0.08)",
    border: "rgba(255,200,87,0.45)",
    icon: HelpCircle,
    key: "news_verdict_suspicious",
  },
  likely_fine: {
    color: "#3dffa0",
    bg: "rgba(61,255,160,0.08)",
    border: "rgba(61,255,160,0.45)",
    icon: ShieldCheck,
    key: "news_verdict_likely_fine",
  },
};

const CUE_KEYS: { k: string; labelKey: DictKey }[] = [
  { k: "urgency", labelKey: "news_cue_urgency" },
  { k: "engagement_bait", labelKey: "news_cue_engagement" },
  { k: "unsourced_authority", labelKey: "news_cue_authority" },
  { k: "emotional_shock", labelKey: "news_cue_shock" },
  { k: "question_density", labelKey: "news_cue_questions" },
];

const DEEP_CARDS: { k: string; labelKey: DictKey; subKey: DictKey; color: string }[] = [
  { k: "source", labelKey: "deep_source", subKey: "deep_source_sub", color: "#59e8ff" },
  { k: "date", labelKey: "deep_date", subKey: "deep_date_sub", color: "#ffc857" },
  { k: "logic", labelKey: "deep_logic", subKey: "deep_logic_sub", color: "#ff8fa3" },
  { k: "agenda", labelKey: "deep_agenda", subKey: "deep_agenda_sub", color: "#ff4d6a" },
];

function deepTone(score: number): { label: string; color: string } {
  if (score < 0.3) return { label: "deep_low", color: "#3dffa0" };
  if (score < 0.55) return { label: "deep_mid", color: "#ffc857" };
  return { label: "deep_high", color: "#ff4d6a" };
}

export default function NewsResultCard({ result }: { result: NewsResult }) {
  const { t, lang } = useLang();
  const meta = VERDICT_META[result.verdict] ?? VERDICT_META.suspicious;
  const VIcon = meta.icon;
  const misinfoPct = ((result.misinformation_prob ?? 0) * 100).toFixed(1);
  const isMisleading = result.verdict === "misleading";
  const arbiterAudit = result.arbiter_audit ?? [];

  const fc = result.fact_check ?? { status: "unavailable", disputed: 0, verified: 0, results: [] };
  const fcStatusKey: DictKey =
    fc.status === "ok"
      ? "news_fc_ok"
      : fc.status === "no_coverage"
      ? "news_fc_no_coverage"
      : fc.status === "unavailable"
      ? "news_fc_unavailable"
      : "news_fc_disabled";

  const textCues = result.text_analysis?.cues ?? {};
  const activeCues = CUE_KEYS.filter(({ k }) => {
    const v = textCues[k];
    return Array.isArray(v) ? v.length > 0 : typeof v === "number" && v >= 1.5;
  });
  const families = Number(textCues.cue_families ?? 0);

  return (
    <div className="evidence-card chamfer p-6 space-y-6" dir={lang === "ar" ? "rtl" : "ltr"}>
      {/* Header verdict */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-[#12281f]">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-xs font-semibold tracking-wider uppercase text-[#7da291]">{t("news_misinfo_prob")}</span>
            <span className="inline-flex items-center px-2 py-0.5 text-[11px] font-medium bg-[#081210] text-[#7da291] border border-[#12281f]">
              <FileSearch className="w-3 h-3 mr-1 text-[#3dffa0]" /> {t("news_engine_note")}
            </span>
          </div>
          <h2 className="font-display text-2xl sm:text-3xl font-bold tracking-tight flex items-center gap-2" style={{ color: meta.color }}>
            <VIcon className={`w-7 h-7 ${isMisleading ? "animate-pulse" : ""}`} />
            {t(meta.key)}
          </h2>
        </div>
        <div className="flex items-center gap-4 bg-[#081210]/70 px-4 py-2 border border-[#12281f]">
          <div>
            <div className="text-[10px] uppercase font-bold text-[#456355] tracking-wider">{t("news_misinfo_prob")}</div>
            <div className="text-xl font-black tabular-nums" style={{ color: meta.color }}>
              {misinfoPct}%
            </div>
          </div>
        </div>
      </div>

      {/* probability bar */}
      <div>
        <div className="w-full bg-[#040806] h-3 overflow-hidden">
          <div
            className="h-full transition-all duration-1000"
            style={{
              width: `${misinfoPct}%`,
              background: `linear-gradient(90deg, ${meta.color}66, ${meta.color})`,
              boxShadow: `0 0 10px ${meta.color}`,
            }}
          />
        </div>
      </div>

      {/* extracted text */}
      <div>
        <div className="flex items-center gap-2 mb-2 text-[#7da291]">
          <Quote className="w-4 h-4 text-[#3dffa0]" />
          <h3 className="font-display text-sm font-bold">{t("news_extracted")}</h3>
        </div>
        {result.ocr_available ? (
          <pre
            className="whitespace-pre-wrap text-[13px] leading-relaxed bg-[#040806]/70 border border-[#12281f] p-4 max-h-44 overflow-y-auto text-[#d7efe2] font-[var(--font-body)]"
            dir="auto"
          >
            {result.extracted_text}
          </pre>
        ) : (
          <p className="text-[13px] text-[#ffc857]/80 bg-[#ffc857]/[0.06] border border-[#ffc857]/25 p-4">{t("news_no_text")}</p>
        )}
      </div>

      {/* three signals */}
      <div>
        <div className="flex items-center gap-2 mb-3 text-[#7da291]">
          <ListChecks className="w-4 h-4 text-[#3dffa0]" />
          <h3 className="font-display text-sm font-bold">{t("news_signals_title")}</h3>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {/* text */}
          <div className="bg-[#081210]/40 border border-[#12281f] p-4">
            <div className="text-[10px] uppercase tracking-widest text-[#456355] mb-1">{t("news_signal_text")}</div>
            <div className="font-mono text-xl font-black text-[#d7efe2]">{families}×</div>
            <div className="text-[12px] text-[#7da291] mt-1">{t("news_cue_families")}</div>
          </div>
          {/* forensic */}
          <div className="bg-[#081210]/40 border border-[#12281f] p-4">
            <div className="text-[10px] uppercase tracking-widest text-[#456355] mb-1">{t("news_signal_forensic")}</div>
            <div className="font-mono text-xl font-black text-[#d7efe2]">{((result.forensic_fake_prob ?? 0) * 100).toFixed(0)}%</div>
            {result.image_provenance && (
              <div className="text-[11px] text-[#ffc857]/90 mt-1">provenance: {result.image_provenance}</div>
            )}
          </div>
          {/* fact-check */}
          <div className="bg-[#081210]/40 border border-[#12281f] p-4">
            <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest text-[#456355] mb-1">
              <Globe className="w-3 h-3" /> {t("news_signal_factcheck")}
            </div>
            <div className="text-[12px] text-[#d7efe2] font-semibold">{t(fcStatusKey) as string}</div>
            {fc.status === "ok" && (
              <div className="text-[11px] mt-1">
                <span className="text-[#ff8fa3]">{fc.disputed} {t("news_fc_disputed")}</span>
                {" · "}
                <span className="text-[#8fffc9]">{fc.verified} {t("news_fc_verified")}</span>
              </div>
            )}
            {fc.results?.length > 0 && (
              <div className="mt-2 space-y-1">
                {fc.results.slice(0, 2).map((r, i) => (
                  <a
                    key={i}
                    href={r.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block text-[11px] text-[#59e8ff] hover:underline truncate"
                  >
                    {r.publisher || r.url}: {r.rating}
                  </a>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* deep analysis: sources / dates / logic / agenda */}
      {result.deep_analysis && Object.keys(result.deep_analysis).length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3 text-[#7da291]">
            <Microscope className="w-4 h-4 text-[#3dffa0]" />
            <h3 className="font-display text-sm font-bold">{t("deep_title")}</h3>
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {DEEP_CARDS.filter(({ k }) => result.deep_analysis?.[k]).map(({ k, labelKey, subKey, color }) => {
              const entry = result.deep_analysis![k];
              const tone = deepTone(entry.score);
              return (
                <div key={k} className="bg-[#081210]/40 border border-[#12281f] p-3 flex flex-col">
                  <div className="text-[10px] uppercase tracking-widest mb-1" style={{ color }}>
                    {t(labelKey)}
                  </div>
                  <div className="font-mono text-lg font-black tabular-nums" style={{ color: tone.color }}>
                    {(entry.score * 100).toFixed(0)}%
                  </div>
                  <div className="text-[10px] font-bold mt-0.5" style={{ color: tone.color }}>
                    {t(tone.label as DictKey)}
                  </div>
                  <div className="text-[10px] text-[#456355] mt-1 leading-snug">{t(subKey)}</div>
                  <div className="mt-2 h-1 w-full bg-[#040806] overflow-hidden">
                    <div
                      className="h-full transition-all duration-1000"
                      style={{ width: `${entry.score * 100}%`, background: tone.color, boxShadow: `0 0 6px ${tone.color}` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* manipulation cues */}
      {activeCues.length > 0 && (
        <div>
          <h3 className="font-display text-sm font-bold text-[#7da291] mb-2">{t("news_cues_title")}</h3>
          <div className="flex flex-wrap gap-2">
            {activeCues.map(({ k, labelKey }) => (
              <span key={k} className="px-2.5 py-1 text-[11px] font-semibold bg-[#ff4d6a]/10 border border-[#ff4d6a]/35 text-[#ff8fa3]">
                {t(labelKey)}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* arbiter audit */}
      <div>
        <h3 className="font-display text-sm font-bold text-[#7da291] mb-2">{t("news_audit_title")}</h3>
        <div className="bg-[#040806]/70 border border-[#12281f] p-4 font-mono text-[11px] leading-5 text-[#7da291]" dir="ltr">
          {arbiterAudit.map((a, i) => (
            <div key={i} className={a.includes("anchor") || a.includes("misinformation_prob") ? "text-[#8fffc9]" : ""}>
              {a}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
