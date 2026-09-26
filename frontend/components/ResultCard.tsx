"use client";

import React from "react";
import { ShieldCheck, AlertTriangle, Cpu, CheckCircle2 } from "lucide-react";

interface ResultCardProps {
  realProb: number;
  fakeProb: number;
  confidence: number;
}

export default function ResultCard({ realProb, fakeProb, confidence }: ResultCardProps) {
  const isFake = fakeProb > 0.5;
  const fakePercent = (fakeProb * 100).toFixed(1);
  const realPercent = (realProb * 100).toFixed(1);
  const confPercent = (confidence * 100).toFixed(1);

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 backdrop-blur-md shadow-2xl relative overflow-hidden">
      {/* Background ambient lighting */}
      <div
        className={`absolute -right-20 -top-20 w-64 h-64 rounded-full blur-3xl opacity-20 pointer-events-none ${
          isFake ? "bg-rose-500" : "bg-emerald-500"
        }`}
      />

      {/* Header Verdict */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800/80">
        <div>
          <div className="flex items-center space-x-2">
            <span className="text-xs font-semibold tracking-wider uppercase text-slate-400">
              Classification Verdict
            </span>
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700">
              <Cpu className="w-3 h-3 mr-1 text-cyan-400" /> Keras + GPT-4
            </span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-extrabold mt-1 tracking-tight flex items-center gap-2">
            {isFake ? (
              <span className="text-rose-400 flex items-center gap-2">
                <AlertTriangle className="w-7 h-7 text-rose-500 animate-pulse" />
                SYNTHETIC / DEEPFAKE DETECTED
              </span>
            ) : (
              <span className="text-emerald-400 flex items-center gap-2">
                <ShieldCheck className="w-7 h-7 text-emerald-400" />
                AUTHENTIC SPECIMEN
              </span>
            )}
          </h2>
        </div>

        <div className="flex items-center space-x-4 bg-slate-950/60 px-4 py-2 rounded-xl border border-slate-800">
          <div>
            <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Confidence Level</div>
            <div className="text-xl font-black text-cyan-400">{confPercent}%</div>
          </div>
          <div className="w-8 h-8 rounded-full border-2 border-cyan-400/40 border-t-cyan-400 flex items-center justify-center animate-spin-slow">
            <CheckCircle2 className="w-4 h-4 text-cyan-400" />
          </div>
        </div>
      </div>

      {/* Primary Probability Gauges */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 my-6">
        {/* Fake Probability Card */}
        <div
          className={`rounded-xl p-5 border transition-all ${
            isFake
              ? "bg-rose-950/20 border-rose-500/40 shadow-[0_0_25px_rgba(255,42,95,0.15)]"
              : "bg-slate-950/40 border-slate-800/80"
          }`}
        >
          <div className="flex justify-between items-center mb-3">
            <span className="text-sm font-semibold text-slate-300 flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full ${isFake ? "bg-rose-500 animate-ping" : "bg-slate-600"}`} />
              Synthetic / Fake Probability
            </span>
            <span className={`text-2xl font-black ${isFake ? "text-rose-400" : "text-slate-400"}`}>
              {fakePercent}%
            </span>
          </div>
          <div className="w-full bg-slate-800/60 rounded-full h-3 overflow-hidden p-0.5">
            <div
              className={`h-full rounded-full transition-all duration-1000 ${
                isFake
                  ? "bg-gradient-to-r from-rose-600 to-red-400 shadow-[0_0_10px_#ff2a5f]"
                  : "bg-slate-600"
              }`}
              style={{ width: `${fakePercent}%` }}
            />
          </div>
          <p className="text-xs text-slate-400 mt-2">
            Likelihood of GAN, Diffusion, or FaceSwap manipulation markers.
          </p>
        </div>

        {/* Real Probability Card */}
        <div
          className={`rounded-xl p-5 border transition-all ${
            !isFake
              ? "bg-emerald-950/20 border-emerald-500/40 shadow-[0_0_25px_rgba(0,255,157,0.15)]"
              : "bg-slate-950/40 border-slate-800/80"
          }`}
        >
          <div className="flex justify-between items-center mb-3">
            <span className="text-sm font-semibold text-slate-300 flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full ${!isFake ? "bg-emerald-400 animate-ping" : "bg-slate-600"}`} />
              Authentic / Real Probability
            </span>
            <span className={`text-2xl font-black ${!isFake ? "text-emerald-400" : "text-slate-400"}`}>
              {realPercent}%
            </span>
          </div>
          <div className="w-full bg-slate-800/60 rounded-full h-3 overflow-hidden p-0.5">
            <div
              className={`h-full rounded-full transition-all duration-1000 ${
                !isFake
                  ? "bg-gradient-to-r from-emerald-600 to-cyan-400 shadow-[0_0_10px_#00ff9d]"
                  : "bg-slate-600"
              }`}
              style={{ width: `${realPercent}%` }}
            />
          </div>
          <p className="text-xs text-slate-400 mt-2">
            Coherence with natural camera sensor noise and uncompressed optics.
          </p>
        </div>
      </div>
    </div>
  );
}
