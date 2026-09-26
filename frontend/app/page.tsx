"use client";

import React, { useState } from "react";
import { Shield, ShieldAlert, Cpu, Sparkles, Terminal, Activity, FileCheck, Layers, HelpCircle } from "lucide-react";
import UploadZone from "@/components/UploadZone";
import ResultCard from "@/components/ResultCard";
import MultiAspectChart from "@/components/MultiAspectChart";
import ForensicReport from "@/components/ForensicReport";

interface DetectionResult {
  status: string;
  real_prob: number;
  fake_prob: number;
  confidence: number;
  multi_aspect_scores: {
    lighting: number;
    texture: number;
    color_consistency: number;
    background_artifacts: number;
    facial_distortion: number;
    [key: string]: number;
  };
  forensic_analysis: string;
  report_id: string;
}

export default function DeepGuardDashboard() {
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<DetectionResult | null>(null);
  const [scanStep, setScanStep] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const runAnalysis = async (file: File) => {
    setIsLoading(true);
    setErrorMsg(null);
    setScanStep("Pre-processing specimen (299×299 normalized tensor)...");

    try {
      const timer1 = setTimeout(() => {
        setScanStep("Extracting multi-aspect spatial & frequency anomaly gradients...");
      }, 700);

      const timer2 = setTimeout(() => {
        setScanStep("Synthesizing GPT-4 Deepfake Forensic Report...");
      }, 1400);

      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch("/api/v1/detect", {
        method: "POST",
        body: formData,
      });

      clearTimeout(timer1);
      clearTimeout(timer2);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Forensic analysis failed.");
      }

      const data: DetectionResult = await response.json();
      setResult(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "An unexpected error occurred.";
      setErrorMsg(msg);
    } finally {
      setIsLoading(false);
      setScanStep("");
    }
  };

  const loadSampleSpecimen = async (isDeepfake: boolean) => {
    try {
      // Generate synthetic sample canvas image
      const canvas = document.createElement("canvas");
      canvas.width = 400;
      canvas.height = 400;
      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.fillStyle = isDeepfake ? "#1a0b1e" : "#0c1b24";
        ctx.fillRect(0, 0, 400, 400);
        ctx.fillStyle = isDeepfake ? "#ff2a5f" : "#00f2fe";
        ctx.beginPath();
        ctx.arc(200, 180, 80, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#ffffff";
        ctx.font = "bold 16px monospace";
        ctx.textAlign = "center";
        ctx.fillText(isDeepfake ? "DEMO: SYNTHETIC GAN" : "DEMO: AUTHENTIC PHOTO", 200, 320);
      }
      canvas.toBlob((blob) => {
        if (blob) {
          const testFile = new File(
            [blob],
            isDeepfake ? "sample_deepfake_specimen.png" : "sample_authentic_specimen.png",
            { type: "image/png" }
          );
          runAnalysis(testFile);
        }
      }, "image/png");
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Navigation Top Bar */}
      <header className="border-b border-slate-800/80 bg-slate-950/70 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center shadow-[0_0_15px_rgba(0,242,254,0.4)]">
              <Shield className="w-5 h-5 text-black font-black" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-black tracking-wider text-lg text-white font-mono">
                  DEEP<span className="text-cyan-400">GUARD</span>
                </span>
                <span className="text-[10px] uppercase font-bold tracking-widest px-1.5 py-0.5 rounded bg-cyan-950/80 text-cyan-400 border border-cyan-800/60">
                  v2.0 PRO
                </span>
              </div>
              <p className="text-[10px] text-slate-400 hidden sm:block">AI Deepfake Detection & Media Forensics Engine</p>
            </div>
          </div>

          <div className="flex items-center space-x-3 text-xs">
            <div className="hidden md:flex items-center space-x-2 bg-slate-900 px-3 py-1.5 rounded-lg border border-slate-800">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-slate-300 font-mono">Backend: FastAPI & Keras Active</span>
            </div>
            <a
              href="https://github.com/auradesignm-spec/DeepGuard"
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition flex items-center gap-1.5"
            >
              <Terminal className="w-3.5 h-3.5 text-cyan-400" />
              <span>FastAPI Docs</span>
            </a>
          </div>
        </div>
      </header>

      {/* Main Content Dashboard */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Hero & Quick Specimen Demo Controls */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-950/40 border border-cyan-500/20 text-cyan-400 text-xs font-semibold mb-3">
              <Sparkles className="w-3.5 h-3.5" /> Next.js 14 + FastAPI + GPT-4 Forensic Pipeline
            </div>
            <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
              Media Forgery & Deepfake Inspection
            </h1>
            <p className="text-slate-400 text-sm max-w-2xl mt-1">
              Upload any image specimen to scan for GAN generation, diffusion inpainting, face-swap blending seams, and generate certified forensic reports.
            </p>
          </div>

          {/* Quick Demo Pre-load buttons */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => loadSampleSpecimen(true)}
              disabled={isLoading}
              className="px-3 py-2 rounded-xl bg-rose-950/30 hover:bg-rose-950/60 border border-rose-500/30 text-rose-300 text-xs font-semibold transition flex items-center gap-1.5 disabled:opacity-50"
            >
              <ShieldAlert className="w-3.5 h-3.5 text-rose-400" /> Test Synthetic Demo
            </button>
            <button
              type="button"
              onClick={() => loadSampleSpecimen(false)}
              disabled={isLoading}
              className="px-3 py-2 rounded-xl bg-emerald-950/30 hover:bg-emerald-950/60 border border-emerald-500/30 text-emerald-300 text-xs font-semibold transition flex items-center gap-1.5 disabled:opacity-50"
            >
              <FileCheck className="w-3.5 h-3.5 text-emerald-400" /> Test Authentic Demo
            </button>
          </div>
        </div>

        {/* Upload Dropzone */}
        <section>
          <UploadZone onFileSelected={runAnalysis} isLoading={isLoading} />
        </section>

        {/* Loading Progress State */}
        {isLoading && (
          <div className="bg-slate-900/60 border border-cyan-500/30 rounded-2xl p-6 backdrop-blur-md text-center space-y-3 shadow-[0_0_30px_rgba(0,255,255,0.1)]">
            <div className="flex justify-center items-center space-x-3">
              <div className="w-6 h-6 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
              <span className="text-cyan-400 font-mono text-sm font-semibold tracking-wide">
                {scanStep || "Processing image specimen..."}
              </span>
            </div>
            <div className="max-w-md mx-auto bg-slate-950 rounded-full h-1.5 overflow-hidden">
              <div className="bg-gradient-to-r from-cyan-500 via-blue-500 to-purple-500 h-full w-2/3 animate-pulse rounded-full" />
            </div>
          </div>
        )}

        {/* Error Message */}
        {errorMsg && (
          <div className="bg-rose-950/40 border border-rose-500/50 rounded-2xl p-4 text-rose-300 text-sm flex items-center gap-3">
            <ShieldAlert className="w-5 h-5 text-rose-400 flex-shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Results Section */}
        {result && !isLoading && (
          <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Primary Result Gauge Card */}
            <ResultCard
              realProb={result.real_prob}
              fakeProb={result.fake_prob}
              confidence={result.confidence}
            />

            {/* Two-Column Grid: Multi-Aspect Chart & GPT-4 Forensic Report */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              <MultiAspectChart scores={result.multi_aspect_scores} />
              <ForensicReport
                analysis={result.forensic_analysis}
                reportId={result.report_id}
                isFake={result.fake_prob > 0.5}
              />
            </div>
          </div>
        )}

        {/* Technical Features & Pipeline Specification */}
        <section className="pt-6 border-t border-slate-800/80">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-slate-950/40 border border-slate-800/60 rounded-xl p-5 space-y-2">
              <div className="flex items-center space-x-2 text-cyan-400 font-semibold text-sm">
                <Cpu className="w-4 h-4" />
                <h4>TensorFlow / Keras Classifier</h4>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Normalized 299×299 tensor input trained on StyleGAN, FaceForensics++, and diffusion synthesized datasets.
              </p>
            </div>

            <div className="bg-slate-950/40 border border-slate-800/60 rounded-xl p-5 space-y-2">
              <div className="flex items-center space-x-2 text-purple-400 font-semibold text-sm">
                <Layers className="w-4 h-4" />
                <h4>5-Aspect Forensic Spatial Matrix</h4>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Cross-channel luminance gradient variance, high-frequency dermal noise, edge jitter, and geometric facial symmetry analysis.
              </p>
            </div>

            <div className="bg-slate-950/40 border border-slate-800/60 rounded-xl p-5 space-y-2">
              <div className="flex items-center space-x-2 text-emerald-400 font-semibold text-sm">
                <Activity className="w-4 h-4" />
                <h4>FastAPI & ReportLab Export</h4>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Automated PDF document generation with cryptographic specimen IDs, executive summaries, and legal chain-of-custody notes.
              </p>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-950 py-6 mt-12 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center space-x-2">
            <Shield className="w-4 h-4 text-cyan-500" />
            <span className="font-mono text-slate-400">DeepGuard Forensic Platform &copy; {new Date().getFullYear()}</span>
          </div>
          <div className="flex items-center space-x-4">
            <span>FastAPI Backend: <code className="text-cyan-400">/api/v1/detect</code></span>
            <span>PDF Export: <code className="text-cyan-400">/api/v1/download-report</code></span>
          </div>
        </div>
      </footer>
    </div>
  );
}
