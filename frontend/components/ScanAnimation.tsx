"use client";

import React, { useState, useEffect, useRef } from "react";
import { Radar, Fingerprint, Network, ScanFace, Layers, FileCheck2 } from "lucide-react";
import { useLang, type DictKey } from "@/lib/i18n";

interface ScanAnimationProps {
  scanStep: string;
}

const PHASES: { key: string; labelKey: DictKey; icon: React.ComponentType<{ className?: string }>; color: string }[] = [
  { key: "bytes", labelKey: "sa_phase_bytes", icon: Fingerprint, color: "#3dffa0" },
  { key: "detect", labelKey: "sa_phase_detect", icon: Network, color: "#59e8ff" },
  { key: "face", labelKey: "sa_phase_face", icon: ScanFace, color: "#ffc857" },
  { key: "quality", labelKey: "sa_phase_quality", icon: Layers, color: "#8fffc9" },
  { key: "fuse", labelKey: "sa_phase_fuse", icon: Layers, color: "#8fffc9" },
  { key: "report", labelKey: "sa_phase_report", icon: FileCheck2, color: "#ff4d6a" },
];

/** Maps the backend scanStep text onto the visual phase index. */
function phaseIndexFromStep(step: string): number {
  if (!step) return 0;
  const s = step.toLowerCase();
  if (s.includes("pre-processing")) return 0;
  if (s.includes("spatial") || s.includes("extract")) return 1;
  if (s.includes("report") || s.includes("synthesiz")) return 3;
  return 1;
}

export default function ScanAnimation({ scanStep }: ScanAnimationProps) {
  const { t } = useLang();
  const [phase, setPhase] = useState(0);
  const [progress, setProgress] = useState(8);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    setPhase(phaseIndexFromStep(scanStep));
  }, [scanStep]);

  // smooth creep toward 92% while loading; never completes until real result
  useEffect(() => {
    let alive = true;
    const tick = () => {
      if (!alive) return;
      setProgress((p) => (p < 92 ? p + (92 - p) * 0.015 : p));
      rafRef.current = window.setTimeout(tick, 120) as unknown as number;
    };
    rafRef.current = window.setTimeout(tick, 120) as unknown as number;
    return () => {
      alive = false;
      if (rafRef.current) clearTimeout(rafRef.current);
    };
  }, []);

  return (
    <div className="relative border border-[#1d4534] bg-[#081210]/90 overflow-hidden shadow-[0_0_40px_rgba(61,255,160,0.08)]">
      {/* corner brackets */}
      <span className="absolute top-3 left-3 w-4 h-4 border-t-2 border-l-2 border-[#3dffa0]/50 z-20" />
      <span className="absolute top-3 right-3 w-4 h-4 border-t-2 border-r-2 border-[#3dffa0]/50 z-20" />
      <span className="absolute bottom-3 left-3 w-4 h-4 border-b-2 border-l-2 border-[#3dffa0]/50 z-20" />
      <span className="absolute bottom-3 right-3 w-4 h-4 border-b-2 border-r-2 border-[#3dffa0]/50 z-20" />

      {/* scanning beam sweeping the whole card */}
      <div className="pointer-events-none absolute inset-0 z-10 overflow-hidden">
        <div className="scan-beam absolute left-0 right-0 h-24" />
      </div>

      {/* grid backdrop */}
      <div
        className="absolute inset-0 opacity-[0.13]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(61,255,160,.5) 1px, transparent 1px), linear-gradient(90deg, rgba(61,255,160,.5) 1px, transparent 1px)",
          backgroundSize: "34px 34px",
          maskImage: "radial-gradient(ellipse at center, black 30%, transparent 85%)",
        }}
      />

      <div className="relative z-10 px-6 py-7 md:px-10 md:py-8 grid md:grid-cols-[220px_1fr] gap-8 items-center">
        {/* radar dial */}
        <div className="mx-auto relative w-40 h-40">
          {/* rings */}
          <div className="absolute inset-0 rounded-full border border-[#3dffa0]/25" />
          <div className="absolute inset-4 rounded-full border border-[#3dffa0]/15" />
          <div className="absolute inset-8 rounded-full border border-[#3dffa0]/25" />
          {/* crosshairs */}
          <div className="absolute left-1/2 top-3 bottom-3 w-px bg-[#3dffa0]/15" />
          <div className="absolute top-1/2 left-3 right-3 h-px bg-[#3dffa0]/15" />
          {/* rotating sweep */}
          <div className="absolute inset-0 rounded-full overflow-hidden">
            <div
              className="absolute inset-0 rounded-full"
              style={{
                background: "conic-gradient(from 0deg, rgba(61,255,160,0.4), rgba(61,255,160,0.06) 70deg, transparent 90deg)",
                animation: "radarSweep 2.6s linear infinite",
              }}
            />
          </div>
          {/* center core */}
          <div className="absolute inset-0 grid place-items-center">
            <div className="relative">
              <div className="w-12 h-12 rounded-full bg-[#3dffa0]/10 border border-[#3dffa0]/50 grid place-items-center shadow-[0_0_24px_rgba(61,255,160,0.4)]">
                <Radar className="w-5 h-5 text-[#8fffc9]" />
              </div>
              {/* ping rings */}
              <span className="ping-ring absolute inset-0 rounded-full border border-[#3dffa0]/60" />
              <span className="ping-ring absolute inset-0 rounded-full border border-[#3dffa0]/40" style={{ animationDelay: "1.1s" }} />
            </div>
          </div>
          {/* progress arc text */}
          <div className="absolute -bottom-7 inset-x-0 text-center">
            <span className="font-mono text-[11px] text-[#3dffa0]/90 tracking-widest">{Math.round(progress)}% · {t("si_percent")}</span>
          </div>
        </div>

        {/* phase checklist */}
        <div className="space-y-3 min-w-0">
          <div className="font-mono text-[10px] tracking-[0.3em] text-[#3dffa0]/70 mb-4">
            {t("sa_corridor")}
          </div>
          {PHASES.map((p, i) => {
            const Icon = p.icon;
            const done = i < phase;
            const active = i === phase;
            return (
              <div
                key={p.key}
                className={`flex items-center gap-3.5 px-3.5 py-2.5 border transition-all duration-500 ${
                  active
                    ? "border-[#3dffa0]/40 bg-[#3dffa0]/[0.05]"
                    : done
                    ? "border-[#12281f] bg-[#081210]/20"
                    : "border-[#12281f]/50 bg-transparent opacity-40"
                }`}
              >
                <div
                  className="w-8 h-8 rounded-md grid place-items-center border shrink-0 transition-all duration-500"
                  style={{
                    borderColor: done || active ? `${p.color}55` : "rgba(100,116,139,0.25)",
                    background: active ? `${p.color}14` : done ? `${p.color}0a` : "transparent",
                    color: done || active ? p.color : "#475569",
                    boxShadow: active ? `0 0 16px ${p.color}44` : "none",
                  }}
                >
                  <Icon className={`w-4 h-4 ${active ? "animate-pulse" : ""}`} />
                </div>
                <span
                  className={`font-mono text-[13px] tracking-wide transition-colors duration-500 ${
                    active ? "text-white" : done ? "text-[#d7efe2]" : "text-[#456355]"
                  }`}
                >
                  {t(p.labelKey)}
                </span>
                <span className="ms-auto font-mono text-[10px] shrink-0" style={{ color: done ? "#00ff9d" : active ? p.color : "#334155" }}>
                  {done ? t("sa_done") : active ? t("sa_run") : t("sa_queued")}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* bottom progress rail */}
      <div className="relative z-10 h-1 bg-[#040806]">
        <div
          className="h-full bg-gradient-to-r from-[#21d67e] via-[#3dffa0] to-[#59e8ff] transition-all duration-300"
          style={{ width: `${progress}%`, boxShadow: "0 0 12px rgba(61,255,160,0.7)" }}
        />
      </div>

      <style jsx global>{`
        @keyframes radarSweep {
          to { transform: rotate(360deg); }
        }
        .scan-beam {
          background: linear-gradient(
            to bottom,
            transparent,
            rgba(0, 242, 254, 0.16) 45%,
            rgba(0, 242, 254, 0.55) 50%,
            rgba(0, 242, 254, 0.16) 55%,
            transparent
          );
          animation: beamSweep 2.8s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }
        @keyframes beamSweep {
          0% { top: -15%; }
          100% { top: 105%; }
        }
        .ping-ring {
          animation: corePing 2.2s cubic-bezier(0, 0, 0.2, 1) infinite;
        }
        @keyframes corePing {
          0% { transform: scale(1); opacity: 0.9; }
          80%, 100% { transform: scale(2.1); opacity: 0; }
        }
      `}</style>
    </div>
  );
}
