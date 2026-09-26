"use client";

import React, { useState, useRef } from "react";
import { Upload, Image as ImageIcon, ShieldAlert, Sparkles, CheckCircle, RefreshCw } from "lucide-react";

interface UploadZoneProps {
  onFileSelected: (file: File) => void;
  isLoading: boolean;
}

export default function UploadZone({ onFileSelected, isLoading }: UploadZoneProps) {
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
      alert("Please upload a valid image file (JPG, PNG, WEBP, GIF).");
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
        className={`relative border-2 border-dashed rounded-2xl p-6 sm:p-10 transition-all duration-300 cursor-pointer overflow-hidden backdrop-blur-md ${
          dragActive
            ? "border-cyan-400 bg-cyan-950/20 shadow-[0_0_30px_rgba(0,255,255,0.2)]"
            : "border-slate-800 hover:border-slate-700 bg-slate-900/40 hover:bg-slate-900/60"
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
            <div className="w-full h-1 bg-gradient-to-r from-transparent via-cyan-400 to-transparent shadow-[0_0_15px_#00ffff] animate-scanline" />
          </div>
        )}

        {previewUrl ? (
          <div className="flex flex-col items-center justify-center space-y-4">
            <div className="relative group max-w-xs sm:max-w-sm rounded-xl overflow-hidden border border-cyan-500/30 shadow-[0_0_20px_rgba(0,242,254,0.15)]">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={previewUrl}
                alt="Uploaded specimen preview"
                className="w-full max-h-64 object-contain rounded-xl bg-black/40"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-end justify-between p-3">
                <span className="text-xs text-slate-300 truncate max-w-[200px]">{fileInfo?.name}</span>
                <button
                  type="button"
                  onClick={triggerReset}
                  className="px-2 py-1 text-xs font-semibold text-rose-400 bg-rose-950/60 border border-rose-500/40 rounded hover:bg-rose-900/80"
                >
                  Change
                </button>
              </div>
            </div>

            <div className="text-center">
              <div className="flex items-center justify-center space-x-2 text-cyan-400 text-sm font-medium">
                {isLoading ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin text-cyan-400" />
                    <span>Executing Deep Neural & GPT-4 Forensic Pipeline...</span>
                  </>
                ) : (
                  <>
                    <CheckCircle className="w-4 h-4 text-emerald-400" />
                    <span>Specimen Loaded: {fileInfo?.name} ({fileInfo?.size})</span>
                  </>
                )}
              </div>
              {!isLoading && (
                <p className="text-xs text-slate-500 mt-1">Click or drop another image to analyze a new specimen</p>
              )}
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center text-center space-y-4 py-4">
            <div className="relative">
              <div className="w-16 h-16 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shadow-[0_0_20px_rgba(0,255,255,0.1)] group-hover:scale-110 transition-transform">
                <Upload className="w-8 h-8" />
              </div>
              <div className="absolute -top-1 -right-1 w-4 h-4 bg-cyan-400 rounded-full animate-ping opacity-60" />
            </div>

            <div className="space-y-1">
              <p className="text-base font-semibold text-slate-200">
                Drag & drop image specimen here, or <span className="text-cyan-400 underline underline-offset-4">browse</span>
              </p>
              <p className="text-xs text-slate-400">
                Supports high-resolution JPG, PNG, WEBP, GIF up to 20MB
              </p>
            </div>

            <div className="flex items-center space-x-4 pt-2 text-xs text-slate-500">
              <span className="flex items-center gap-1">
                <ShieldAlert className="w-3.5 h-3.5 text-cyan-500" /> Neural Preprocessing (299×299)
              </span>
              <span className="flex items-center gap-1">
                <Sparkles className="w-3.5 h-3.5 text-purple-400" /> GPT-4 Forensic Fingerprints
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
