"use client";

import React from "react";
import { Sun, Fingerprint, Palette, Image as BgIcon, ScanFace, Activity } from "lucide-react";
import { useLang, type DictKey } from "@/lib/i18n";

interface MultiAspectChartProps {
  scores: {
    lighting?: number;
    texture?: number;
    color_consistency?: number;
    background_artifacts?: number;
    facial_distortion?: number;
    [key: string]: number | undefined;
  };
}

export default function MultiAspectChart({ scores }: MultiAspectChartProps) {
  const { t } = useLang();
  const aspects = [
    {
      id: "lighting",
      labelKey: "mc_lighting" as DictKey,
      icon: Sun,
      score: scores.lighting ?? 0,
      descKey: "mc_lighting_d" as DictKey,
    },
    {
      id: "texture",
      labelKey: "mc_texture" as DictKey,
      icon: Fingerprint,
      score: scores.texture ?? 0,
      descKey: "mc_texture_d" as DictKey,
    },
    {
      id: "color_consistency",
      labelKey: "mc_color" as DictKey,
      icon: Palette,
      score: scores.color_consistency ?? 0,
      descKey: "mc_color_d" as DictKey,
    },
    {
      id: "background_artifacts",
      labelKey: "mc_background" as DictKey,
      icon: BgIcon,
      score: scores.background_artifacts ?? 0,
      descKey: "mc_background_d" as DictKey,
    },
    {
      id: "facial_distortion",
      labelKey: "mc_face" as DictKey,
      icon: ScanFace,
      score: scores.facial_distortion ?? 0,
      descKey: "mc_face_d" as DictKey,
    },
  ];

  const getStatus = (score: number) => {
    if (score <= 0) return { label: t("st_none"), color: "text-[#456355] bg-[#081210]/60 border-[#12281f]", bar: "from-[#1d4534] to-[#143024]" };
    if (score > 88) return { label: t("st_high"), color: "text-[#ff8fa3] bg-[#ff4d6a]/10 border-[#ff4d6a]/30", bar: "from-[#ff4d6a] to-[#ffc857]" };
    if (score > 75) return { label: t("st_elevated"), color: "text-[#ffc857] bg-[#ffc857]/10 border-[#ffc857]/30", bar: "from-[#ffc857] to-[#ffe3a0]" };
    return { label: t("st_nominal"), color: "text-[#8fffc9] bg-[#3dffa0]/10 border-[#3dffa0]/30", bar: "from-[#21d67e] to-[#3dffa0]" };
  };

  return (
    <div className="evidence-card chamfer p-6">
      <div className="flex items-center justify-between mb-6 pb-4 border-b border-[#12281f]">
        <div className="flex items-center space-x-2">
          <Activity className="w-5 h-5 text-[#3dffa0]" />
          <h3 className="font-display text-lg font-bold text-[#d7efe2]">{t("mc_title")}</h3>
        </div>
        <span className="text-xs text-[#7da291]">
          {t("mc_sub")}
        </span>
      </div>

      <div className="space-y-5">
        {aspects.map((aspect) => {
          const Icon = aspect.icon;
          const status = getStatus(aspect.score);

          return (
            <div key={aspect.id} className="bg-[#081210]/40 border border-[#12281f] p-4 transition-all hover:border-[#1d4534]">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
                <div className="flex items-center space-x-3">
                  <div className="p-2 bg-[#0a1613] border border-[#12281f] text-[#3dffa0]">
                    <Icon className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-[#d7efe2]">{t(aspect.labelKey)}</h4>
                    <p className="text-xs text-[#7da291] line-clamp-1">{t(aspect.descKey)}</p>
                  </div>
                </div>

                <div className="flex items-center space-x-3 self-end sm:self-auto">
                  <span className={`px-2 py-0.5 text-[11px] font-semibold border ${status.color}`}>
                    {status.label}
                  </span>
                  <span className="text-sm font-black text-[#d7efe2] w-12 text-right tabular-nums">
                    {aspect.score.toFixed(1)}%
                  </span>
                </div>
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-[#040806] h-2 overflow-hidden">
                <div
                  className={`h-full bg-gradient-to-r ${status.bar} transition-all duration-700`}
                  style={{ width: `${Math.min(100, aspect.score)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
