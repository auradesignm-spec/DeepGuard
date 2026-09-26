"use client";

import React, { useState } from "react";
import { FileText, Download, Sparkles, Check, Copy, Shield } from "lucide-react";

interface ForensicReportProps {
  analysis: string;
  reportId: string;
  downloadUrl?: string;
  isFake?: boolean;
}

export default function ForensicReport({ analysis, reportId, downloadUrl, isFake }: ForensicReportProps) {
  const [copied, setCopied] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(analysis);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = async () => {
    try {
      setIsDownloading(true);
      const url = downloadUrl || `/api/v1/download-report/${reportId}`;
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error("Failed to download PDF report");
      }
      const blob = await response.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = blobUrl;
      link.download = reportId || "deepfake_forensic_report.pdf";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(blobUrl);
    } catch (err) {
      console.error(err);
      alert("Downloading report failed. Please ensure the backend is available.");
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 backdrop-blur-md shadow-2xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800/80 mb-6">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-xl bg-purple-950/40 border border-purple-500/30 text-purple-400">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2">
              GPT-4 Forensic Intelligence Findings
            </h3>
            <p className="text-xs text-slate-400">
              Automated Forensic Fingerprints, Optical Inconsistencies & Attribution
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <button
            type="button"
            onClick={handleCopy}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 transition"
            title="Copy Report Text"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? "Copied" : "Copy"}</span>
          </button>

          <button
            type="button"
            onClick={handleDownload}
            disabled={isDownloading}
            className="flex items-center space-x-1.5 px-4 py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 text-xs font-bold shadow-[0_0_15px_rgba(0,255,255,0.3)] transition transform hover:scale-[1.02] disabled:opacity-50"
          >
            <Download className="w-3.5 h-3.5" />
            <span>{isDownloading ? "Generating PDF..." : "Export PDF Report"}</span>
          </button>
        </div>
      </div>

      {/* Analysis Content Box */}
      <div className="prose prose-invert max-w-none text-slate-300 text-sm leading-relaxed space-y-4 bg-slate-950/50 p-5 rounded-xl border border-slate-800/70 max-h-[380px] overflow-y-auto">
        {analysis.split("\n").map((line, idx) => {
          const trimmed = line.trim();
          if (!trimmed) return <div key={idx} className="h-1" />;

          if (trimmed.startsWith("###") || trimmed.startsWith("##")) {
            return (
              <h4 key={idx} className="text-cyan-400 font-bold text-base mt-3 mb-1 border-b border-cyan-950/80 pb-1">
                {trimmed.replace(/^#+\s*/, "")}
              </h4>
            );
          }

          if (trimmed.startsWith("-") || trimmed.startsWith("*")) {
            return (
              <div key={idx} className="flex items-start space-x-2 pl-2">
                <span className="text-cyan-400 font-bold mt-0.5">•</span>
                <span dangerouslySetInnerHTML={{
                  __html: trimmed.replace(/^[-*]\s*/, "").replace(/\*\*(.*?)\*\*/g, "<strong class='text-slate-100'>$1</strong>")
                }} />
              </div>
            );
          }

          return (
            <p key={idx} dangerouslySetInnerHTML={{
              __html: trimmed.replace(/\*\*(.*?)\*\*/g, "<strong class='text-slate-100'>$1</strong>")
            }} />
          );
        })}
      </div>

      {/* Footer Legal & Verification */}
      <div className="mt-4 pt-4 border-t border-slate-800/60 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs text-slate-500">
        <div className="flex items-center space-x-2">
          <Shield className="w-4 h-4 text-slate-400" />
          <span>Report ID: <code className="text-cyan-400/80 font-mono">{reportId}</code></span>
        </div>
        <div>
          <span>Chain-of-Custody: SHA-256 Verified Specimen</span>
        </div>
      </div>
    </div>
  );
}
