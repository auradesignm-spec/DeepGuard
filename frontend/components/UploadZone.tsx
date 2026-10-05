"use client";

import React, { useState, useRef } from "react";
import { Upload, ShieldAlert, Sparkles, CheckCircle } from "lucide-react";
import ScanningImage from "./ScanningImage";
import { useLang } from "@/lib/i18n";

interface UploadZoneProps {
  onFileSelected: (file: File) => void;
  isLoading: boolean;
}

export default function UploadZone({ onFileSelected, isLoading }: UploadZoneProps) {
  const { t } = useLang();
  const [dragActive, setDragActive] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [fileInfo, setFileInfo] = useState<{ name: string; size: string } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const processFile = (file: File) => {
    if (!file.type.startsWith("image/")) {
      alert(t("up_alert_invalid"));
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    setFileInfo({
      name: file.name,
      size: `${(file.size / (1024 * 1024)).toFixed(2)} MB`,
    });
    onFileSelected(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      processFile(e.target.files[0]);
    }
  };

  const triggerReset = (e: React.MouseEvent) => {
    e.stopPropagation();
    setPreviewUrl(null);
    setFileInfo(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <div className="w-full">
      <div
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => !isLoading && inputRef.current?.click()}
        className={`relative border border-dashed p-6 sm:p-10 transition-all duration-300 cursor-pointer overflow-hidden ${
          dragActive
            ? "border-[#3dffa0]/70 bg-[#3dffa0]/[0.05] shadow-[0_0_30px_rgba(61,255,160,0.2)]"
            : "border-[#1d4534] hover:border-[#3dffa0]/50 bg-[#081210]/40 hover:bg-[#0a1613]/70"
        } ${isLoading ? "pointer-events-none opacity-80" : ""}`}
      >
        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif"
          onChange={handleChange}
          className="hidden"
        />

        {/* Scan line effect when loading */}
        {isLoading && (
          <div className="absolute inset-0 pointer-events-none overflow-hidden z-20">
            <div className="w-full h-1 bg-gradient-to-r from-transparent via-[#3dffa0] to-transparent shadow-[0_0_15px_#3dffa0] animate-scanline" />
          </div>
        )}

        {previewUrl ? (
          <div className="flex flex-col items-center justify-center space-y-4">
            {isLoading ? (
              /* cinematic forensic scan over the real uploaded image */
              <ScanningImage src={previewUrl} duration={5000} className="max-w-xs sm:max-w-sm w-full" />
            ) : (
              <div className="relative group max-w-xs sm:max-w-sm overflow-hidden border border-[#3dffa0]/40 shadow-[0_0_20px_rgba(61,255,160,0.15)]">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={previewUrl}
                  alt="Uploaded specimen preview"
                  className="w-full max-h-64 object-contain rounded-xl bg-black/40"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-end justify-between p-3">
                  <span className="text-xs text-[#d7efe2] truncate max-w-[200px]">{fileInfo?.name}</span>
                  <button
                    type="button"
                    onClick={triggerReset}
                    className="px-2 py-1 text-xs font-semibold text-[#ff8fa3] bg-[#ff4d6a]/15 border border-[#ff4d6a]/40 hover:bg-[#ff4d6a]/30"
                  >
                    {t("up_change")}
                  </button>
                </div>
              </div>
            )}

            <div className="text-center">
              <div className="flex items-center justify-center space-x-2 text-[#3dffa0] text-sm font-medium">
                {!isLoading && (
                  <>
                    <CheckCircle className="w-4 h-4 text-[#3dffa0]" />
                    <span>{t("up_loaded_pre")}{fileInfo?.name} ({fileInfo?.size})</span>
                  </>
                )}
              </div>
              {!isLoading && (
                <p className="text-xs text-[#7da291] mt-1">{t("up_another")}</p>
              )}
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center text-center space-y-4 py-4">
            <div className="relative">
              <div className="w-16 h-16 bg-[#3dffa0]/[0.08] border border-[#3dffa0]/35 flex items-center justify-center text-[#3dffa0] shadow-[0_0_20px_rgba(61,255,160,0.1)] group-hover:scale-110 transition-transform">
                <Upload className="w-8 h-8" />
              </div>
              <div className="absolute -top-1 -right-1 w-4 h-4 bg-[#3dffa0] rounded-full animate-ping opacity-60" />
            </div>

            <div className="space-y-1">
              <p className="text-base font-semibold text-[#d7efe2]">
                {t("up_drop_title_pre")}<span className="text-[#3dffa0] underline underline-offset-4">{t("up_drop_link")}</span>
              </p>
              <p className="text-xs text-[#7da291]">
                {t("up_drop_formats")}
              </p>
            </div>

            <div className="flex items-center space-x-4 pt-2 text-xs text-[#456355]">
              <span className="flex items-center gap-1">
                <ShieldAlert className="w-3.5 h-3.5 text-[#3dffa0]/80" /> {t("up_chip1")}
              </span>
              <span className="flex items-center gap-1">
                <Sparkles className="w-3.5 h-3.5 text-[#59e8ff]" /> {t("up_chip2")}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
