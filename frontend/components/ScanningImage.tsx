"use client";

import React, { useEffect, useRef, useState } from "react";
import { useLang } from "@/lib/i18n";

/**
 * ScanningImage — layered real-time forensic scan over the ACTUAL specimen.
 *
 * Architecture rule: the uploaded image is ALWAYS the visible base layer.
 * Every scan effect is an overlay on top of it — the specimen never blanks:
 *
 *   L1  real image, full frame, every frame
 *   L2  pixel-decomposition intro (750ms) blended OVER the image
 *   L3  tiered analysis grid: cells flip to "analyzed" (green) as the
 *       sweep front passes — layered grid forensics, real-time state
 *   L4  X-Ray sweep front: hot vertical line + band with glitch-sliced
 *       redraw of the real image + cyan cast
 *   L5  green evidence boxes (MATCH labels), two staggered waves
 *   L6  HUD: corner brackets, progress rail, live percentage
 */

interface ScanningImageProps {
  src: string;
  /** total scan duration ms — synced with the API min-theatre delay */
  duration?: number;
  className?: string;
}

// English-only HUD readouts: keep monospace terminal authenticity (dir=ltr)
const PHASES = [
  "SCANNING RAW BYTES",
  "C2PA PROVENANCE CHECK",
  "MAPPING SCENE GRID",
  "PANEL INFERENCE",
  "FUSING SIGNAL VOTES",
];

const GRID_COLS = 26; // analysis cells across the width

export default function ScanningImage({ src, duration = 5000, className = "" }: ScanningImageProps) {
  const { t } = useLang();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const offRef = useRef<HTMLCanvasElement | null>(null);
  const lastPctRef = useRef(-1);
  const [progress, setProgress] = useState(0);
  const [acquiring, setAcquiring] = useState(true);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    let cancelled = false;
    let raf = 0;

    const img = new Image();
    let ready = false;
    img.onload = () => { ready = true; setAcquiring(false); };
    img.onerror = () => { setAcquiring(false); };
    img.src = src;
    if (img.complete && img.naturalWidth > 0) { ready = true; setAcquiring(false); }

    const off = offRef.current ?? (offRef.current = document.createElement("canvas"));

    const start = performance.now();

    const draw = (now: number) => {
      if (cancelled || !canvas.parentElement) return;
      const t = now - start;
      const p = Math.min(1, t / duration);

      const pct = Math.round(p * 100);
      if (pct !== lastPctRef.current) { lastPctRef.current = pct; setProgress(p); }

      const pw = canvas.parentElement.clientWidth;
      const ph = canvas.parentElement.clientHeight;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      if (canvas.width !== Math.round(pw * dpr) || canvas.height !== Math.round(ph * dpr)) {
        canvas.width = Math.round(pw * dpr);
        canvas.height = Math.round(ph * dpr);
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const W = pw, H = ph;

      ctx.clearRect(0, 0, W, H);

      const iw = img.naturalWidth, ih = img.naturalHeight;
      const haveImg = ready && iw > 0;

      // ---- L1: the specimen, always visible -------------------------------
      ctx.imageSmoothingEnabled = true;
      if (haveImg) {
        ctx.drawImage(img, 0, 0, W, H);
      } else {
        ctx.fillStyle = "#04120c";
        ctx.fillRect(0, 0, W, H);
        ctx.fillStyle = "rgba(61,255,160,0.55)";
        ctx.font = "600 11px ui-monospace, monospace";
        ctx.textAlign = "center";
        ctx.fillText(acquiring ? "ACQUIRING SPECIMEN…" : "SPECIMEN SIGNAL LOST", W / 2, H / 2);
        ctx.textAlign = "left";
      }

      if (haveImg) {
        // ---- L2: pixel-decomposition intro, blended OVER the image --------
        if (p < 0.15) {
          const a = 1 - p / 0.15;
          const block = Math.max(2, Math.round(4 + 12 * a));
          const tw = Math.max(1, Math.round(W / block));
          const th = Math.max(1, Math.round(H / block));
          if (off.width !== tw || off.height !== th) { off.width = tw; off.height = th; }
          const octx = off.getContext("2d");
          if (octx) {
            octx.imageSmoothingEnabled = true;
            octx.clearRect(0, 0, tw, th);
            octx.drawImage(img, 0, 0, tw, th);
            ctx.save();
            ctx.globalAlpha = Math.min(0.9, a);
            ctx.imageSmoothingEnabled = false;
            ctx.drawImage(off, 0, 0, tw, th, 0, 0, W, H);
            ctx.restore();
          }
        }

        // ---- L3: tiered analysis grid (real-time cell states) --------------
        const cellW = W / GRID_COLS;
        const rows = Math.ceil(H / cellW);
        const front = p * W; // sweep front position (LTR)
        ctx.save();
        for (let c = 0; c < GRID_COLS; c++) {
          const x = c * cellW;
          const isAnalyzed = x + cellW < front;
          const isFrontier = Math.abs(x + cellW / 2 - front) < cellW * 1.2;
          for (let r = 0; r < rows; r++) {
            const y = r * cellW;
            if (isFrontier) {
              ctx.fillStyle = "rgba(61,255,160,0.14)";
              ctx.fillRect(x, y, cellW, cellW);
              ctx.strokeStyle = "rgba(61,255,160,0.55)";
              ctx.lineWidth = 1;
              ctx.strokeRect(x + 0.5, y + 0.5, cellW - 1, cellW - 1);
            } else if (isAnalyzed) {
              // settled "analyzed" tier: faint green fill + crisp grid
              ctx.fillStyle = "rgba(61,255,160,0.035)";
              ctx.fillRect(x, y, cellW, cellW);
              ctx.strokeStyle = "rgba(61,255,160,0.09)";
              ctx.lineWidth = 0.6;
              ctx.strokeRect(x + 0.5, y + 0.5, cellW - 1, cellW - 1);
            } else {
              ctx.strokeStyle = "rgba(125,162,145,0.06)";
              ctx.lineWidth = 0.5;
              ctx.strokeRect(x + 0.5, y + 0.5, cellW - 1, cellW - 1);
            }
          }
        }
        ctx.restore();

        // ---- L4: X-Ray sweep front + glitch slices of the real image -------
        const band = Math.max(46, W * 0.07);
        const bx0 = Math.max(0, front - band / 2);
        const bw = Math.min(band, W - bx0);
        if (bw > 1) {
          const bh = H;
          // glitch-sliced redraw of the band region (real pixels, jittered)
          ctx.save();
          ctx.beginPath();
          ctx.rect(bx0, 0, bw, bh);
          ctx.clip();
          const slices = 7;
          const sh = bh / slices;
          for (let i = 0; i < slices; i++) {
            const yy = i * sh;
            const syImg = (yy / H) * ih;
            const shImg = (sh / H) * ih;
            const dx = Math.sin(now / 70 + i * 1.9) * 4;
            ctx.drawImage(img, 0, syImg, iw, shImg, dx, yy, W, sh);
          }
          // green x-ray cast inside the band
          ctx.fillStyle = "rgba(61,255,160,0.14)";
          ctx.fillRect(bx0, 0, bw, bh);
          ctx.restore();

          // hot vertical front line
          ctx.save();
          ctx.strokeStyle = "rgba(61,255,160,0.95)";
          ctx.lineWidth = 1.8;
          ctx.shadowColor = "#3dffa0";
          ctx.shadowBlur = 16;
          ctx.beginPath();
          ctx.moveTo(front, 0);
          ctx.lineTo(front, H);
          ctx.stroke();
          ctx.restore();
        }

        // ---- L5: green evidence boxes (two staggered waves) -----------------
        const waves = [
          { s: 0.16, e: 0.5, seed: 7, n: 9 },
          { s: 0.5, e: 0.85, seed: 23, n: 7 },
        ];
        const mulberry = (seed: number) => () => {
          seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
          let x = Math.imul(seed ^ (seed >>> 15), 1 | seed);
          x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x;
          return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
        };
        for (const w of waves) {
          if (p < w.s || p > w.e) continue;
          const local = (p - w.s) / (w.e - w.s);
          const rnd = mulberry(w.seed);
          for (let i = 0; i < w.n; i++) {
            const u = rnd(), v = rnd();
            const appear = i / w.n;
            const life = (local - appear) / 0.45;
            if (life < 0 || life > 1) continue;
            const alpha = life < 0.15 ? life / 0.15 : life > 0.75 ? (1 - life) / 0.25 : 1;
            const bwid = 26 + u * (W * 0.16);
            const bhei = 26 + v * (H * 0.16);
            const bx = u * (W - bwid);
            const by = v * (H - bhei);
            const jx = Math.sin(now / 240 + i * 2.1) * 1.5;
            const jy = Math.cos(now / 300 + i * 1.7) * 1.5;
            ctx.save();
            ctx.globalAlpha = Math.max(0, Math.min(1, alpha));
            ctx.strokeStyle = "#3dffa0";
            ctx.lineWidth = 1.4;
            ctx.shadowColor = "#3dffa0";
            ctx.shadowBlur = 10;
            const cc = Math.min(10, bwid / 3, bhei / 3);
            ctx.beginPath();
            ctx.moveTo(bx + jx, by + jy + cc); ctx.lineTo(bx + jx, by + jy); ctx.lineTo(bx + jx + cc, by + jy);
            ctx.moveTo(bx + jx + bwid - cc, by + jy); ctx.lineTo(bx + jx + bwid, by + jy); ctx.lineTo(bx + jx + bwid, by + jy + cc);
            ctx.moveTo(bx + jx + bwid, by + jy + bhei - cc); ctx.lineTo(bx + jx + bwid, by + jy + bhei); ctx.lineTo(bx + jx + bwid - cc, by + jy + bhei);
            ctx.moveTo(bx + jx + cc, by + jy + bhei); ctx.lineTo(bx + jx, by + jy + bhei); ctx.lineTo(bx + jx, by + jy + bhei - cc);
            ctx.stroke();
            ctx.shadowBlur = 0;
            ctx.font = "600 8px ui-monospace, monospace";
            ctx.fillStyle = "#3dffa0";
            ctx.fillText(`MATCH ${(0.72 + v * 0.25).toFixed(2)}`, bx + jx, Math.max(7, by + jy - 4));
            ctx.restore();
          }
        }
      }

      // ---- L6: HUD brackets + progress rail --------------------------------
      ctx.save();
      ctx.strokeStyle = "rgba(61,255,160,0.65)";
      ctx.lineWidth = 1.4;
      const m = 6, L = 16;
      ctx.beginPath();
      ctx.moveTo(m, m + L); ctx.lineTo(m, m); ctx.lineTo(m + L, m);
      ctx.moveTo(W - m - L, m); ctx.lineTo(W - m, m); ctx.lineTo(W - m, m + L);
      ctx.moveTo(W - m, H - m - L); ctx.lineTo(W - m, H - m); ctx.lineTo(W - m - L, H - m);
      ctx.moveTo(m + L, H - m); ctx.lineTo(m, H - m); ctx.lineTo(m, H - m - L);
      ctx.stroke();
      ctx.strokeStyle = "rgba(125,162,145,0.25)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(m + L + 6, H - m - 3);
      ctx.lineTo(W - m - L - 6, H - m - 3);
      ctx.stroke();
      ctx.strokeStyle = "#3dffa0";
      ctx.shadowColor = "#3dffa0";
      ctx.shadowBlur = 6;
      ctx.beginPath();
      ctx.moveTo(m + L + 6, H - m - 3);
      ctx.lineTo(m + L + 6 + (W - 2 * (m + L + 6)) * p, H - m - 3);
      ctx.stroke();
      ctx.restore();

      if (p < 1) raf = requestAnimationFrame(draw);
    };

    raf = requestAnimationFrame(draw);
    return () => { cancelled = true; cancelAnimationFrame(raf); };
  }, [src, duration]);

  const phase = PHASES[Math.min(PHASES.length - 1, Math.floor(progress * PHASES.length))] ?? PHASES[0];

  return (
    <div className={`relative w-full overflow-hidden border border-[#3dffa0]/40 shadow-[0_0_30px_rgba(61,255,160,0.25)] ${className}`}>
      <div className="relative w-full h-56 sm:h-72">
        <canvas ref={canvasRef} className="absolute inset-0 w-full h-full" aria-label="Scanning specimen" role="img" />
        <div className="absolute top-2 left-2 flex items-center gap-2 px-2 py-1 bg-black/60 border border-[#3dffa0]/30 backdrop-blur-sm">
          <span className="w-1.5 h-1.5 rounded-full bg-[#3dffa0] animate-pulse" />
          <span className="font-mono text-[10px] tracking-widest text-[#8fffc9]">{phase}…</span>
        </div>
        <div className="absolute top-2 right-2 px-2 py-1 bg-black/60 border border-[#3dffa0]/30 backdrop-blur-sm">
          <span className="font-mono text-[10px] font-bold text-[#8fffc9]">{Math.round(progress * 100)}%</span>
        </div>
        {/* live tier readout */}
        <div className="absolute bottom-6 left-2 font-mono text-[9px] tracking-widest text-[#8fffc9]/80" dir="ltr">
          {t("si_grid_note")}
        </div>
      </div>
    </div>
  );
}
