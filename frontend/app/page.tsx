"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Shield, ShieldAlert, Cpu, Sparkles, Activity, FileCheck, Layers, FileSearch, Newspaper } from "lucide-react";
import UploadZone from "@/components/UploadZone";
import ReportShell from "@/components/ReportShell";
import VerdictCard from "@/components/VerdictCard";
import ModelScoresCard from "@/components/ModelScoresCard";
import ManipulationMapCard from "@/components/ManipulationMapCard";
import NewsResultCard, { type NewsResult } from "@/components/NewsResultCard";
import ScanAnimation from "@/components/ScanAnimation";
import CommandBar from "@/components/CommandBar";
import { useLang } from "@/lib/i18n";
import type { AnalysisRecord } from "@/lib/analysis";

export default function DeepGuardDashboard() {
  const { t } = useLang();
  const [mode, setMode] = useState<"image" | "news">("image");
  const [isLoading, setIsLoading] = useState(false);
  const [report, setReport] = useState<AnalysisRecord | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [newsResult, setNewsResult] = useState<NewsResult | null>(null);
  const [scanStep, setScanStep] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => () => {
    if (imageUrl) URL.revokeObjectURL(imageUrl);
  }, [imageUrl]);

  const resetReport = () => {
    setReport(null);
    if (imageUrl) URL.revokeObjectURL(imageUrl);
    setImageUrl(null);
    setErrorMsg(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const runAnalysis = async (file: File) => {
    const isNews = mode === "news";
    setIsLoading(true);
    setErrorMsg(null);
    setReport(null);
    setNewsResult(null);
    setScanStep(isNews ? "Extracting text (OCR ar/en)..." : "Byte-level provenance scan...");

    try {
      const timer1 = setTimeout(() => {
        setScanStep(isNews ? "Analyzing manipulation tactics..." : "Detector-panel inference in progress...");
      }, 900);

      const timer2 = setTimeout(() => {
        setScanStep(isNews ? "Cross-checking claims..." : "Forensic verdict synthesis...");
      }, 2200);

      const formData = new FormData();
      formData.append("file", file);

      // Fire the API call and the cinematic minimum together: the layered
      // scan animation gets its full 5s run before any verdict is shown,
      // even when the engine answers faster.
      const minTheatreMs = 5000;
      const minTheatre = new Promise((r) => setTimeout(r, minTheatreMs));
      const startedAt = Date.now();

      const response = await fetch(isNews ? "/api/analyze-news" : "/api/v1/analyze", {
        method: "POST",
        body: formData,
      });

      clearTimeout(timer1);
      clearTimeout(timer2);

      const waitRemaining = Math.max(0, minTheatreMs - (Date.now() - startedAt));
      if (waitRemaining > 0) {
        setScanStep(isNews ? "Cross-checking claims..." : "Forensic verdict synthesis...");
        await new Promise((r) => setTimeout(r, waitRemaining));
      }
      await minTheatre;

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Forensic analysis failed.");
      }

      if (isNews) {
        const data: NewsResult = await response.json();
        setNewsResult(data);
      } else {
        const data: AnalysisRecord = await response.json();
        setReport(data);
        if (imageUrl) URL.revokeObjectURL(imageUrl);
        setImageUrl(URL.createObjectURL(file));
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "An unexpected error occurred.";
      setErrorMsg(msg);
    } finally {
      setIsLoading(false);
      setScanStep("");
    }
  };

  const loadSampleSpecimen = async (isDeepfake: boolean) => {
    if (mode === "news") {
      // generate a sensational fake-news screenshot sample
      try {
        const canvas = document.createElement("canvas");
        canvas.width = 640;
        canvas.height = 300;
        const ctx = canvas.getContext("2d");
        if (ctx) {
          ctx.fillStyle = "#ffffff";
          ctx.fillRect(0, 0, 640, 300);
          ctx.fillStyle = "#111111";
          ctx.font = "bold 30px Arial";
          ctx.fillText("URGENT!!! EXCLUSIVE LEAK", 40, 70);
          ctx.font = "24px Arial";
          ctx.fillText("Shocking scandal — sources confirm!", 40, 130);
          ctx.fillStyle = "#cc0000";
          ctx.fillText("share before they delete!!!", 40, 180);
        }
        canvas.toBlob((blob) => {
          if (blob) {
            runAnalysis(new File([blob], "sample_news_screenshot.png", { type: "image/png" }));
          }
        }, "image/png");
      } catch (e) {
        console.error(e);
      }
      return;
    }
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
      {/* Shared cyber command bar */}
      <CommandBar variant="dashboard" />

      {/* Main Content Dashboard */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Mode toggle: image forensics / news misinformation */}
        <div className="flex justify-center">
          <div
            role="tablist"
            aria-label={t("mode_toggle_aria")}
            dir="ltr"
            className="relative inline-flex items-center gap-1 p-1 bg-[#080c10] border border-[#122b20] rounded-full"
          >
            {([
              { id: "image", icon: FileSearch, key: "mode_image" as const },
              { id: "news", icon: Newspaper, key: "mode_news" as const },
            ]).map(({ id, icon: Icon, key }) => {
              const on = mode === id;
              return (
                <button
                  key={id}
                  role="tab"
                  aria-selected={on}
                  type="button"
                  onClick={() => setMode(id as "image" | "news")}
                  className={`relative z-10 flex items-center gap-2 px-6 h-9 rounded-full text-[13px] font-semibold transition-all duration-300 ${
                    on
                      ? "bg-[#00ff9d] text-[#080c10] shadow-[0_0_16px_rgba(0,255,157,0.4)]"
                      : "text-[#7da291] hover:text-[#8fffc9]"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {t(key)}
                </button>
              );
            })}
          </div>
        </div>

        {/* Hero & Quick Specimen Demo Controls */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 border border-[#1d4534] bg-[#0a1613]/80 text-[#3dffa0]/90 text-[11px] font-mono tracking-[0.1em] mb-3">
              <Sparkles className="w-3.5 h-3.5" /> {mode === "news" ? t("news_badge") : t("dash_badge")}
            </div>
            <h1 className="font-display text-3xl sm:text-4xl font-bold text-white tracking-tight">
              {mode === "news" ? t("news_h1") : t("dash_h1")}
            </h1>
            <p className="text-[#7da291] text-sm max-w-2xl mt-1">
              {mode === "news" ? t("news_h1_sub") : t("dash_h1_sub")}
            </p>
          </div>

          {/* Quick Demo Pre-load buttons */}
          <div className="flex items-center gap-2">
            {mode === "image" && (
              <>
                <button
                  type="button"
                  onClick={() => loadSampleSpecimen(true)}
                  disabled={isLoading}
                  className="px-3 py-2 bg-[#ff4d6a]/10 hover:bg-[#ff4d6a]/20 border border-[#ff4d6a]/35 text-[#ff8fa3] text-xs font-semibold transition flex items-center gap-1.5 disabled:opacity-50 [clip-path:polygon(7px_0,100%_0,100%_calc(100%-7px),calc(100%-7px)_100%,0_100%,0_7px)]"
                >
                  <ShieldAlert className="w-3.5 h-3.5 text-[#ff4d6a]" /> {t("dash_demo_fake")}
                </button>
                <button
                  type="button"
                  onClick={() => loadSampleSpecimen(false)}
                  disabled={isLoading}
                  className="px-3 py-2 bg-[#3dffa0]/10 hover:bg-[#3dffa0]/20 border border-[#3dffa0]/35 text-[#8fffc9] text-xs font-semibold transition flex items-center gap-1.5 disabled:opacity-50 [clip-path:polygon(7px_0,100%_0,100%_calc(100%-7px),calc(100%-7px)_100%,0_100%,0_7px)]"
                >
                  <FileCheck className="w-3.5 h-3.5 text-[#3dffa0]" /> {t("dash_demo_real")}
                </button>
              </>
            )}
            {mode === "news" && (
              <button
                type="button"
                onClick={() => loadSampleSpecimen(false)}
                disabled={isLoading}
                className="px-3 py-2 bg-[#ffc857]/10 hover:bg-[#ffc857]/20 border border-[#ffc857]/35 text-[#ffe3a0] text-xs font-semibold transition flex items-center gap-1.5 disabled:opacity-50 [clip-path:polygon(7px_0,100%_0,100%_calc(100%-7px),calc(100%-7px)_100%,0_100%,0_7px)]"
              >
                <Newspaper className="w-3.5 h-3.5 text-[#ffc857]" /> {t("news_demo")}
              </button>
            )}
          </div>
        </div>

        {/* Upload Dropzone */}
        <section>
          <UploadZone onFileSelected={runAnalysis} isLoading={isLoading} />
        </section>

        {/* Loading Progress State */}
        {isLoading && <ScanAnimation scanStep={scanStep} />}

        {/* Error Message */}
        {errorMsg && (
          <div className="bg-[#ff4d6a]/10 border border-[#ff4d6a]/45 p-4 text-[#ff8fa3] text-sm flex items-center gap-3">
            <ShieldAlert className="w-5 h-5 text-[#ff4d6a] flex-shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Results Section */}
        {newsResult && !isLoading && (
          <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <NewsResultCard result={newsResult} />
          </div>
        )}

        {report && !isLoading && (
          <ReportShell
            verdictLabel={
              report.verdict.label
                ? t(
                    report.verdict.label === "AI Detected"
                      ? "v_ai_detected"
                      : report.verdict.label === "No AI Detected"
                        ? "v_no_ai"
                        : report.verdict.label === "Possible Edits"
                          ? "v_possible_edits"
                          : "v_investigate"
                  )
                : t("state_loading")
            }
            verdictTone={
              report.verdict.label === "AI Detected"
                ? "red"
                : report.verdict.label === "No AI Detected"
                  ? "green"
                  : "amber"
            }
            imageUrl={imageUrl}
            imageName={report.image.name}
            onAnalyzeAnother={resetReport}
          >
            <VerdictCard record={report} />
            <ModelScoresCard record={report} />
            <ManipulationMapCard record={report} imageUrl={imageUrl} />
          </ReportShell>
        )}

        {/* Technical Features & Pipeline Specification */}
        <section className="pt-6 border-t border-[#12281f]">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="evidence-card chamfer p-5 space-y-2">
              <div className="flex items-center space-x-2 text-[#3dffa0] font-semibold text-sm">
                <Cpu className="w-4 h-4" />
                <h4 className="font-display">{t("feat1_t")}</h4>
              </div>
              <p className="text-xs text-[#7da291] leading-relaxed">{t("feat1_d")}</p>
            </div>

            <div className="evidence-card chamfer p-5 space-y-2">
              <div className="flex items-center space-x-2 text-[#59e8ff] font-semibold text-sm">
                <Layers className="w-4 h-4" />
                <h4 className="font-display">{t("feat2_t")}</h4>
              </div>
              <p className="text-xs text-[#7da291] leading-relaxed">{t("feat2_d")}</p>
            </div>

            <div className="evidence-card chamfer p-5 space-y-2">
              <div className="flex items-center space-x-2 text-[#ffc857] font-semibold text-sm">
                <Activity className="w-4 h-4" />
                <h4 className="font-display">{t("feat3_t")}</h4>
              </div>
              <p className="text-xs text-[#7da291] leading-relaxed">{t("feat3_d")}</p>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-[#12281f] bg-[#050a08] py-6 mt-12 text-xs text-[#7da291]">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center space-x-2">
            <Shield className="w-4 h-4 text-[#3dffa0]" />
            <span className="font-mono">DeepGuard &copy; {new Date().getFullYear()}</span>
          </div>
          <div className="flex items-center space-x-4">
            <span>
              {t("dash_footer_api")} <code className="text-[#3dffa0]" dir="ltr">/api/v1/detect</code>
            </span>
            <span>
              {t("dash_footer_pdf")} <code className="text-[#3dffa0]" dir="ltr">/api/v1/download-report</code>
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
