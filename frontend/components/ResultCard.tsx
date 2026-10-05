"use client";

import React from "react";
import { ShieldCheck, AlertTriangle, Cpu, CheckCircle2, HelpCircle } from "lucide-react";
import { useLang } from "@/lib/i18n";

interface ResultCardProps {
  realProb: number;
  fakeProb: number;
  confidence: number;
  verdict?: string;
}

export default function ResultCard({ realProb, fakeProb, confidence, verdict }: ResultCardProps) {
  const { t } = useLang();
  const isUncertain = verdict === "uncertain";
  const isFake = isUncertain ? false : verdict ? verdict === "fake" : fakeProb > 0.6;
  const fakePercent = (fakeProb * 100).toFixed(1);
  const realPercent = (realProb * 100).toFixed(1);
  const confPercent = (confidence * 100).toFixed(1);

  return (
    <div className="evidence-card chamfer p-6 relative overflow-hidden">
      {/* Background ambient lighting */}
      <div
        className={`absolute -right-20 -top-20 w-64 h-64 rounded-full blur-3xl opacity-20 pointer-events-none ${
          isUncertain ? "bg-[#ffc857]" : isFake ? "bg-[#ff4d6a]" : "bg-[#3dffa0]"
        }`}
      />

      {/* Header Verdict */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-[#12281f]">
        <div>
          <div className="flex items-center space-x-2">
            <span className="text-xs font-semibold tracking-wider uppercase text-[#7da291]">
              {t("rc_verdict")}
            </span>
            <span className="inline-flex items-center px-2 py-0.5 text-[11px] font-medium bg-[#081210] text-[#7da291] border border-[#12281f]">
              <Cpu className="w-3 h-3 mr-1 text-[#3dffa0]" /> {t("rc_engine")}
            </span>
          </div>
          <h2 className="font-display text-2xl sm:text-3xl font-bold mt-1 tracking-tight flex items-center gap-2">
            {isUncertain ? (
              <span className="text-[#ffc857] flex items-center gap-2">
                <HelpCircle className="w-7 h-7 text-[#ffc857]" />
                {t("rc_uncertain")}
              </span>
            ) : isFake ? (
              <span className="text-[#ff4d6a] flex items-center gap-2">
                <AlertTriangle className="w-7 h-7 text-[#ff4d6a] animate-pulse" />
                {t("rc_fake")}
              </span>
            ) : (
              <span className="text-[#3dffa0] flex items-center gap-2">
                <ShieldCheck className="w-7 h-7 text-[#3dffa0]" />
                {t("rc_real")}
              </span>
            )}
          </h2>
        </div>

        <div className="flex items-center space-x-4 bg-[#081210]/70 px-4 py-2 border border-[#12281f]">
          <div>
            <div className="text-[10px] uppercase font-bold text-[#456355] tracking-wider">{t("rc_confidence")}</div>
            <div className="text-xl font-black text-[#3dffa0] tabular-nums">{confPercent}%</div>
          </div>
          <div className="w-8 h-8 rounded-full border-2 border-[#3dffa0]/40 border-t-[#3dffa0] flex items-center justify-center animate-spin-slow">
            <CheckCircle2 className="w-4 h-4 text-[#3dffa0]" />
          </div>
        </div>
      </div>

      {/* Primary Probability Gauges */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 my-6">
        {/* Fake Probability Card */}
        <div
          className={`p-5 border transition-all ${
            isFake
              ? "bg-[#ff4d6a]/[0.07] border-[#ff4d6a]/40 shadow-[0_0_25px_rgba(255,77,106,0.15)]"
              : "bg-[#081210]/40 border-[#12281f]"
          }`}
        >
          <div className="flex justify-between items-center mb-3">
            <span className="text-sm font-semibold text-[#d7efe2] flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full ${isFake ? "bg-[#ff4d6a] animate-ping" : "bg-[#456355]"}`} />
              {t("rc_fake_prob")}
            </span>
            <span className={`text-2xl font-black tabular-nums ${isFake ? "text-[#ff4d6a]" : "text-[#456355]"}`}>
              {fakePercent}%
            </span>
          </div>
          <div className="w-full bg-[#040806] h-3 overflow-hidden p-0.5">
            <div
              className={`h-full transition-all duration-1000 ${
                isFake
                  ? "bg-gradient-to-r from-[#ff4d6a]/70 to-[#ff4d6a] shadow-[0_0_10px_#ff4d6a]"
                  : "bg-[#1d4534]"
              }`}
              style={{ width: `${fakePercent}%` }}
            />
          </div>
          <p className="text-xs text-[#7da291] mt-2">
            {t("rc_fake_note")}
          </p>
        </div>

        {/* Real Probability Card */}
        <div
          className={`p-5 border transition-all ${
            !isFake
              ? "bg-[#3dffa0]/[0.07] border-[#3dffa0]/40 shadow-[0_0_25px_rgba(61,255,160,0.15)]"
              : "bg-[#081210]/40 border-[#12281f]"
          }`}
        >
          <div className="flex justify-between items-center mb-3">
            <span className="text-sm font-semibold text-[#d7efe2] flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full ${!isFake ? "bg-[#3dffa0] animate-ping" : "bg-[#456355]"}`} />
              {t("rc_real_prob")}
            </span>
            <span className={`text-2xl font-black tabular-nums ${!isFake ? "text-[#3dffa0]" : "text-[#456355]"}`}>
              {realPercent}%
            </span>
          </div>
          <div className="w-full bg-[#040806] h-3 overflow-hidden p-0.5">
            <div
              className={`h-full transition-all duration-1000 ${
                !isFake
                  ? "bg-gradient-to-r from-[#21d67e]/70 to-[#3dffa0] shadow-[0_0_10px_#3dffa0]"
                  : "bg-[#1d4534]"
              }`}
              style={{ width: `${realPercent}%` }}
            />
          </div>
          <p className="text-xs text-[#7da291] mt-2">
            {t("rc_real_note")}
          </p>
        </div>
      </div>
    </div>
  );
}
