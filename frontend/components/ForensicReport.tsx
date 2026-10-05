"use client";

import React, { useState } from "react";
import { FileText, Download, Sparkles, Check, Copy, Shield } from "lucide-react";
import { useLang } from "@/lib/i18n";

interface ForensicReportProps {
  analysis: string;
  reportId: string;
  downloadUrl?: string;
  isFake?: boolean;
}

export default function ForensicReport({ analysis, reportId, downloadUrl, isFake }: ForensicReportProps) {
  const { t } = useLang();
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
      alert(t("fr_copy_fail"));
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="evidence-card chamfer p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#12281f] mb-6">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-[#0a1613] border border-[#1d4534] text-[#3dffa0]">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-display text-lg font-bold text-[#d7efe2] flex items-center gap-2">
              {t("fr_title")}
            </h3>
            <p className="text-xs text-[#7da291]">
              {t("fr_sub")}
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <button
            type="button"
            onClick={handleCopy}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-[#081210] hover:bg-[#0a1613] text-[#7da291] hover:text-[#3dffa0] text-xs font-medium border border-[#12281f] hover:border-[#3dffa0]/50 transition"
            title={t("fr_copy")}
          >
            {copied ? <Check className="w-3.5 h-3.5 text-[#3dffa0]" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? t("fr_copied") : t("fr_copy")}</span>
          </button>

          <button
            type="button"
            onClick={handleDownload}
            disabled={isDownloading}
            className="btn-phosphor flex items-center space-x-1.5 px-4 py-1.5 text-xs disabled:opacity-50"
          >
            <Download className="w-3.5 h-3.5" />
            <span>{isDownloading ? t("fr_generating") : t("fr_export")}</span>
          </button>
        </div>
      </div>

      {/* Analysis Content Box */}
      <div className="max-w-none text-[#d7efe2] text-sm leading-relaxed space-y-4 bg-[#040806]/70 p-5 border border-[#12281f] max-h-[380px] overflow-y-auto">
        {analysis.split("\n").map((line, idx) => {
          const trimmed = line.trim();
          if (!trimmed) return <div key={idx} className="h-1" />;

          if (trimmed.startsWith("###") || trimmed.startsWith("##")) {
            return (
              <h4 key={idx} className="text-[#3dffa0] font-bold text-base mt-3 mb-1 border-b border-[#12281f] pb-1">
                {trimmed.replace(/^#+\s*/, "")}
              </h4>
            );
          }

          if (trimmed.startsWith("-") || trimmed.startsWith("*")) {
            return (
              <div key={idx} className="flex items-start space-x-2 pl-2">
                <span className="text-[#3dffa0] font-bold mt-0.5">•</span>
                <span dangerouslySetInnerHTML={{
                  __html: trimmed.replace(/^[-*]\s*/, "").replace(/\*\*(.*?)\*\*/g, "<strong class='text-white'>$1</strong>")
                }} />
              </div>
            );
          }

          return (
            <p key={idx} dangerouslySetInnerHTML={{
              __html: trimmed.replace(/\*\*(.*?)\*\*/g, "<strong class='text-white'>$1</strong>")
            }} />
          );
        })}
      </div>

      {/* Footer Legal & Verification */}
      <div className="mt-4 pt-4 border-t border-[#12281f] flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs text-[#456355]">
        <div className="flex items-center space-x-2">
          <Shield className="w-4 h-4 text-[#7da291]" />
          <span>{t("fr_report_id")} <code className="text-[#3dffa0]/80 font-mono">{reportId}</code></span>
        </div>
        <div>
          <span>{t("fr_coc")}</span>
        </div>
      </div>
    </div>
  );
}
