"use client";

import React from "react";
import { Sun, Fingerprint, Palette, Image as BgIcon, ScanFace, Activity } from "lucide-react";

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
  const aspects = [
    {
      id: "lighting",
      label: "Lighting & Specular Variance",
      icon: Sun,
      score: scores.lighting ?? 82.5,
      desc: "Directional luminance falloff and specular reflection alignment across eyes and nose bridge.",
    },
    {
      id: "texture",
      label: "Micro-Texture Coherence",
      icon: Fingerprint,
      score: scores.texture ?? 91.0,
      desc: "High-frequency dermal pore structures vs GAN artificial smoothing.",
    },
    {
      id: "color_consistency",
      label: "Color Space Dispersion",
      icon: Palette,
      score: scores.color_consistency ?? 78.4,
      desc: "Inter-channel RGB standard deviation and chrominance consistency.",
    },
    {
      id: "background_artifacts",
      label: "Boundary & Background Integrity",
      icon: BgIcon,
      score: scores.background_artifacts ?? 85.0,
      desc: "Edge transition interpolation, jitter, and perimeter blending seams.",
    },
    {
      id: "facial_distortion",
      label: "Facial Symmetry & Distortion",
      icon: ScanFace,
      score: scores.facial_distortion ?? 92.1,
      desc: "Neural face-swap warping detection, earlobe symmetry, and teeth alignment.",
    },
  ];

  const getStatus = (score: number) => {
    if (score > 88) return { label: "High Anomaly", color: "text-rose-400 bg-rose-950/50 border-rose-500/30", bar: "from-rose-500 to-amber-500" };
    if (score > 75) return { label: "Elevated", color: "text-amber-400 bg-amber-950/50 border-amber-500/30", bar: "from-amber-500 to-yellow-400" };
    return { label: "Nominal", color: "text-emerald-400 bg-emerald-950/50 border-emerald-500/30", bar: "from-emerald-500 to-cyan-400" };
  };

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 backdrop-blur-md shadow-2xl">
      <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-800/80">
        <div className="flex items-center space-x-2">
          <Activity className="w-5 h-5 text-cyan-400" />
          <h3 className="text-lg font-bold text-slate-100">Multi-Aspect Forensic Breakdown</h3>
        </div>
        <span className="text-xs text-slate-400">
          5 Dimensional Spatial & Frequency Checks
        </span>
      </div>

      <div className="space-y-5">
        {aspects.map((aspect) => {
          const Icon = aspect.icon;
          const status = getStatus(aspect.score);

          return (
            <div key={aspect.id} className="bg-slate-950/40 border border-slate-800/80 rounded-xl p-4 transition-all hover:border-slate-700">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
                <div className="flex items-center space-x-3">
                  <div className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-cyan-400">
                    <Icon className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-slate-200">{aspect.label}</h4>
                    <p className="text-xs text-slate-400 line-clamp-1">{aspect.desc}</p>
                  </div>
                </div>

                <div className="flex items-center space-x-3 self-end sm:self-auto">
                  <span className={`px-2 py-0.5 rounded text-[11px] font-semibold border ${status.color}`}>
                    {status.label}
                  </span>
                  <span className="text-sm font-black text-slate-100 w-12 text-right">
                    {aspect.score.toFixed(1)}%
                  </span>
                </div>
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-slate-800/60 rounded-full h-2 overflow-hidden">
                <div
                  className={`h-full bg-gradient-to-r ${status.bar} rounded-full transition-all duration-700`}
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
