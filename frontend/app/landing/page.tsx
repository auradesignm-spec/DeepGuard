"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import {
  Shield,
  ShieldCheck,
  ShieldAlert,
  ScanFace,
  Fingerprint,
  Image as ImageIcon,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  HardDrive,
  CloudOff,
  BadgeCheck,
  Clock3,
  Info,
} from "lucide-react";
import { useLang, LanguageToggle, type DictKey } from "@/lib/i18n";
import CommandBar from "@/components/CommandBar";

/* ------------------------------------------------------------------ */
/*  Design tokens (landing v2 — calm, single accent)                   */
/* ------------------------------------------------------------------ */

const ACCENT = "#2EE59D";
const DANGER = "#FF5C6C";
const WARNING = "#F5B942";

/* ------------------------------------------------------------------ */
/*  Data                                                               */
/* ------------------------------------------------------------------ */

type IconCmp = React.ComponentType<{ className?: string; style?: React.CSSProperties }>;

const DETECTORS: {
  id: string;
  icon: IconCmp;
  nameKey: DictKey;
  badgeKey: DictKey;
  descKey: DictKey;
}[] = [
  { id: "c2pa", icon: Fingerprint, nameKey: "sig1_name", badgeKey: "sig1_badge", descKey: "sig1_desc" },
  { id: "scene", icon: ImageIcon, nameKey: "sig2_name", badgeKey: "sig2_badge", descKey: "sig2_desc" },
  { id: "face", icon: ScanFace, nameKey: "sig3_name", badgeKey: "sig3_badge", descKey: "sig3_desc" },
  { id: "guard", icon: ShieldCheck, nameKey: "sig4_name", badgeKey: "sig4_badge", descKey: "sig4_desc" },
];

/** Fixed detector readings shown inside the hero mockup (weighted → 92%). */
const MOCK_BARS: { icon: IconCmp; nameKey: DictKey; v: number }[] = [
  { icon: Fingerprint, nameKey: "sig1_name", v: 91 },
  { icon: ImageIcon, nameKey: "sig2_name", v: 88 },
  { icon: ScanFace, nameKey: "sig3_name", v: 93 },
  { icon: ShieldCheck, nameKey: "sig4_name", v: 61 },
];

const STATS: { vKey: DictKey; lKey: DictKey }[] = [
  { vKey: "stat1_v", lKey: "stat1_l" },
  { vKey: "stat2_v", lKey: "stat2_l" },
  { vKey: "stat3_v", lKey: "stat3_l" },
  { vKey: "stat4_v", lKey: "stat4_l" },
];

const PIPELINE: { tKey: DictKey; dKey: DictKey }[] = [
  { tKey: "pipe1_t", dKey: "pipe1_d" },
  { tKey: "pipe2_t", dKey: "pipe2_d" },
  { tKey: "pipe3_t", dKey: "pipe3_d" },
  { tKey: "pipe4_t", dKey: "pipe4_d" },
  { tKey: "pipe5_t", dKey: "pipe5_d" },
];

const FAQS: { qKey: DictKey; aKey: DictKey }[] = [
  { qKey: "faq1_q", aKey: "faq1_a" },
  { qKey: "faq2_q", aKey: "faq2_a" },
  { qKey: "faq3_q", aKey: "faq3_a" },
  { qKey: "faq4_q", aKey: "faq4_a" },
  { qKey: "faq5_q", aKey: "faq5_a" },
];

const TRUST: { icon: IconCmp; key: DictKey }[] = [
  { icon: HardDrive, key: "trust_local" },
  { icon: CloudOff, key: "trust_noupload" },
  { icon: BadgeCheck, key: "trust_evidence" },
];

/* ------------------------------------------------------------------ */
/*  Reveal — light fade/slide on scroll (200–300ms, reduced-motion safe) */
/* ------------------------------------------------------------------ */

function Reveal({
  children,
  delay = 0,
  className = "",
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
}) {
  const [ref, setRef] = useState<HTMLDivElement | null>(null);
  const [visible, setVisible] = useState(false);
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    setReduced(window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }, []);

  useEffect(() => {
    if (!ref) return;
    const obs = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setVisible(true);
          obs.disconnect();
        }
      },
      { threshold: 0.15 }
    );
    obs.observe(ref);
    return () => obs.disconnect();
  }, [ref]);

  const on = visible || reduced;
  return (
    <div
      ref={setRef}
      className={className}
      style={{
        opacity: on ? 1 : 0,
        transform: on ? "none" : "translateY(14px)",
        transition: reduced
          ? "none"
          : `opacity 0.28s ease ${delay}s, transform 0.28s ease ${delay}s`,
      }}
    >
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Hero mockup — clean result card: scene image + verdict + 4 bars    */
/* ------------------------------------------------------------------ */

function ResultMockup() {
  const { t } = useLang();
  return (
    <div className="mock-panel relative p-5 md:p-6">
      {/* verdict chip */}
      <div className="flex items-center justify-between mb-4">
        <span
          className="inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-sm font-semibold"
          style={{
            color: DANGER,
            background: "rgba(255, 92, 108, 0.12)",
            border: "1px solid rgba(255, 92, 108, 0.35)",
          }}
        >
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: DANGER }} />
          {t("sim_label_fake")} <span dir="ltr" className="font-mono">92%</span>
        </span>
        <span className="badge-chip">{t("sig1_name")}</span>
      </div>

      {/* example "photo" — pure CSS scene */}
      <div className="relative rounded-xl overflow-hidden aspect-[16/10]" aria-hidden="true">
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse 55% 40% at 72% 26%, rgba(245, 224, 178, 0.5), transparent 62%)," +
              "linear-gradient(180deg, #2c3e46 0%, #3a534c 46%, #26352e 68%, #1c2a23 100%)",
          }}
        />
        {/* horizon ridge */}
        <div
          className="absolute inset-x-0 bottom-0 h-[38%]"
          style={{
            background: "linear-gradient(180deg, transparent, rgba(10, 15, 13, 0.55))",
            clipPath: "polygon(0 55%, 22% 30%, 45% 48%, 68% 22%, 100% 42%, 100% 100%, 0 100%)",
          }}
        />
        <div className="mock-scan" />
      </div>

      {/* four detector bars */}
      <div className="mt-5 space-y-3">
        {MOCK_BARS.map((b) => {
          const Icon = b.icon;
          return (
            <div key={b.nameKey} className="flex items-center gap-3">
              <Icon className="w-4 h-4 shrink-0" style={{ color: ACCENT }} />
              <span className="flex-1 min-w-0 truncate text-sm" style={{ color: "var(--text)" }}>
                {t(b.nameKey)}
              </span>
              <div className="mini-bar w-24 sm:w-32" aria-hidden="true">
                <div style={{ width: `${b.v}%` }} />
              </div>
              <span className="w-10 text-end text-xs font-mono" dir="ltr" style={{ color: "var(--text-muted)" }}>
                {b.v}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Verdict simulator — bands 0–35 / 35–65 / 65–100                    */
/* ------------------------------------------------------------------ */

function VerdictSimulator() {
  const { t } = useLang();
  const [p, setP] = useState(72);

  const verdict = p > 65 ? "fake" : p < 35 ? "real" : "uncertain";
  const conf = {
    fake: {
      label: t("sim_label_fake"),
      color: DANGER,
      icon: ShieldAlert,
      desc: t("sim_desc_fake"),
    },
    uncertain: {
      label: t("sim_label_uncertain"),
      color: WARNING,
      icon: Clock3,
      desc: t("sim_desc_uncertain"),
    },
    real: {
      label: t("sim_label_real"),
      color: ACCENT,
      icon: ShieldCheck,
      desc: t("sim_desc_real"),
    },
  }[verdict];
  const VIcon = conf.icon;

  return (
    <div>
      <div
        className="rounded-2xl p-6 md:p-10"
        style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
      >
        <div className="grid md:grid-cols-[1fr_260px] gap-8 md:gap-10 items-center">
          {/* slider — LTR math is fixed so 0% always sits left, matching the band labels */}
          <div dir="ltr">
            <div className="relative h-6 flex items-center">
              {/* banded track */}
              <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-2.5 rounded-full overflow-hidden" aria-hidden="true">
                <div className="absolute inset-y-0 left-0" style={{ width: "35%", background: "rgba(46, 229, 157, 0.22)" }} />
                <div className="absolute inset-y-0" style={{ left: "35%", width: "30%", background: "rgba(245, 185, 66, 0.22)" }} />
                <div className="absolute inset-y-0" style={{ left: "65%", width: "35%", background: "rgba(255, 92, 108, 0.22)" }} />
              </div>
              <input
                type="range"
                min={0}
                max={100}
                value={p}
                onChange={(e) => setP(Number(e.target.value))}
                className="relative z-10 w-full cursor-pointer"
                aria-label={t("sim_aria")}
                aria-valuetext={`${p}%`}
              />
            </div>
            {/* band labels */}
            <div className="grid grid-cols-3 mt-2 text-xs" style={{ color: "var(--text-muted)" }}>
              <span className="text-center font-mono">{t("sim_band_real")}</span>
              <span className="text-center font-mono">{t("sim_band_review")}</span>
              <span className="text-center font-mono">{t("sim_band_fake")}</span>
            </div>
          </div>

          {/* live verdict card */}
          <div
            className="rounded-xl p-6 text-center transition-colors duration-300"
            style={{
              border: `1px solid ${conf.color}55`,
              background: `${conf.color}0d`,
            }}
          >
            <VIcon className="w-8 h-8 mx-auto mb-3" style={{ color: conf.color }} />
            <div className="text-lg font-bold" style={{ color: conf.color }}>
              {conf.label}
            </div>
            <div className="font-mono text-4xl font-bold mt-1" dir="ltr" style={{ color: conf.color }}>
              {p}%
            </div>
            <p className="text-[13px] leading-relaxed mt-3" style={{ color: "var(--text-muted)" }}>
              {conf.desc}
            </p>
          </div>
        </div>
      </div>

      {/* engineering honesty note */}
      <p
        className="copy flex items-start gap-2 text-sm mt-4 max-w-2xl mx-auto"
        style={{ color: "var(--text-muted)" }}
      >
        <Info className="w-4 h-4 mt-1 shrink-0" style={{ color: WARNING }} />
        {t("sim_honesty_note")}
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  FAQ item — full-height accordion (measured, never clipped)         */
/* ------------------------------------------------------------------ */

function FaqItem({
  index,
  open,
  onToggle,
  q,
  a,
}: {
  index: number;
  open: boolean;
  onToggle: () => void;
  q: string;
  a: string;
}) {
  const innerRef = useRef<HTMLDivElement>(null);
  const [h, setH] = useState(0);
  const bodyId = `faq-body-${index}`;

  useEffect(() => {
    const measure = () => setH(innerRef.current?.scrollHeight ?? 0);
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);

  return (
    <div className="card overflow-hidden" style={open ? { borderColor: "var(--border-strong)" } : undefined}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={bodyId}
        className="w-full flex items-center justify-between gap-4 px-6 py-5 text-start"
      >
        <span className="font-semibold text-base md:text-[17px]" style={{ color: "var(--text)" }}>
          {q}
        </span>
        <ChevronDown
          className={`w-5 h-5 shrink-0 transition-transform duration-300 ${
            open ? "rotate-180" : ""
          }`}
          style={{ color: open ? ACCENT : "var(--text-muted)" }}
        />
      </button>
      <div
        id={bodyId}
        role="region"
        className="overflow-hidden transition-[height] duration-300 ease-out"
        style={{ height: open ? h : 0 }}
      >
        <div ref={innerRef}>
          <p className="copy px-6 pb-6 text-base leading-relaxed" style={{ color: "var(--text-muted)" }}>
            {a}
          </p>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function LandingPage() {
  const { t, dir } = useLang();
  const [openFaq, setOpenFaq] = useState<number | null>(0);
  const isRtl = dir === "rtl";
  // RTL arrow convention: buttons point toward the reading direction
  const ArrowChevron = isRtl ? ChevronLeft : ChevronRight;

  return (
    <div className="min-h-screen" style={{ color: "var(--text)" }}>
      <CommandBar variant="landing" />

      <main>
        {/* ══ Hero ══ */}
        <section className="relative max-w-[1200px] mx-auto px-5 pt-14 md:pt-20 pb-16 md:pb-24">
          <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
            <div className="space-y-7">
              <Reveal>
                <h1
                  className="font-display font-bold tracking-tight leading-[1.25] text-[38px] sm:text-[46px] lg:text-[56px]"
                  style={{ color: "var(--text)" }}
                >
                  {t("hero_title")}
                </h1>
              </Reveal>
              <Reveal delay={0.06}>
                <p
                  className="copy text-base lg:text-[17px] leading-relaxed max-w-xl"
                  style={{ color: "var(--text-muted)" }}
                >
                  {t("hero_sub")}
                </p>
              </Reveal>
              <Reveal delay={0.12}>
                <div className="flex flex-wrap items-center gap-3">
                  <Link href="/" className="btn-primary inline-flex items-center gap-2 px-6 py-3 text-base">
                    {t("cta_start")}
                    <ArrowChevron className="w-4 h-4" />
                  </Link>
                  <a href="#pipeline" className="btn-outline inline-flex items-center px-6 py-3 text-base">
                    {t("cta_how")}
                  </a>
                </div>
              </Reveal>
              <Reveal delay={0.18}>
                <ul className="flex flex-wrap items-center gap-x-6 gap-y-2 pt-1">
                  {TRUST.map((item) => {
                    const Icon = item.icon;
                    return (
                      <li key={item.key} className="flex items-center gap-2 text-sm" style={{ color: "var(--text-muted)" }}>
                        <Icon className="w-4 h-4" style={{ color: ACCENT }} />
                        {t(item.key)}
                      </li>
                    );
                  })}
                </ul>
              </Reveal>
            </div>

            <Reveal delay={0.1}>
              <ResultMockup />
            </Reveal>
          </div>
        </section>

        {/* ══ Stats strip ══ */}
        <section className="section-pad max-w-[1200px] mx-auto px-5" aria-label={t("sec1_sub")}>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {STATS.map((s, i) => (
              <Reveal key={s.vKey} delay={i * 0.05}>
                <div className="stat-card p-6 h-full">
                  <div className="font-mono font-bold text-[32px] md:text-[36px] leading-none" dir="ltr" style={{ color: "var(--text)" }}>
                    {t(s.vKey)}
                  </div>
                  <div className="text-sm mt-3 leading-relaxed" style={{ color: "var(--text-muted)" }}>
                    {t(s.lKey)}
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </section>

        {/* ══ Detectors — 2×2 ══ */}
        <section id="detectors" className="section-pad max-w-[1200px] mx-auto px-5 scroll-mt-24">
          <Reveal>
            <h2 className="font-display font-bold tracking-tight text-[28px] md:text-[40px]" style={{ color: "var(--text)" }}>
              {t("sec1_title")}
            </h2>
            <p className="copy text-base lg:text-[17px] mt-3 max-w-2xl" style={{ color: "var(--text-muted)" }}>
              {t("sec1_sub")}
            </p>
          </Reveal>

          <div className="grid sm:grid-cols-2 gap-4 mt-10">
            {DETECTORS.map((d, i) => {
              const Icon = d.icon;
              return (
                <Reveal key={d.id} delay={i * 0.06}>
                  <div className="card p-6 h-full">
                    <div className="flex items-center gap-4">
                      <div className="icon-chip">
                        <Icon className="w-5 h-5" />
                      </div>
                      <h3 className="font-bold text-[20px] md:text-[22px] flex-1 min-w-0" style={{ color: "var(--text)" }}>
                        {t(d.nameKey)}
                      </h3>
                      <span className="badge-chip shrink-0">{t(d.badgeKey)}</span>
                    </div>
                    <p className="copy text-[15px] md:text-base leading-relaxed mt-4" style={{ color: "var(--text-muted)" }}>
                      {t(d.descKey)}
                    </p>
                  </div>
                </Reveal>
              );
            })}
          </div>
        </section>

        {/* ══ Pipeline — 5-step vertical stepper ══ */}
        <section id="pipeline" className="section-pad max-w-[1200px] mx-auto px-5 scroll-mt-24">
          <Reveal>
            <h2 className="font-display font-bold tracking-tight text-[28px] md:text-[40px]" style={{ color: "var(--text)" }}>
              {t("sec2_title")}
            </h2>
            <p className="copy text-base lg:text-[17px] mt-3 max-w-2xl" style={{ color: "var(--text-muted)" }}>
              {t("sec2_sub")}
            </p>
          </Reveal>

          <div className="relative max-w-2xl mt-12">
            {/* connecting hairline */}
            <div
              className="absolute top-6 bottom-6 w-px"
              style={{
                background: "var(--border-strong)",
                [isRtl ? "right" : "left"]: "21px",
              } as React.CSSProperties}
              aria-hidden="true"
            />
            <ol className="space-y-8">
              {PIPELINE.map((step, i) => (
                <li key={step.tKey}>
                  <Reveal delay={i * 0.05}>
                    <div className="flex gap-5">
                      <div className="step-dot">{i + 1}</div>
                      <div className="pt-1.5">
                        <h3 className="font-bold text-[20px] md:text-[22px]" style={{ color: "var(--text)" }}>
                          {t(step.tKey)}
                        </h3>
                        <p className="copy text-[15px] md:text-base mt-1.5" style={{ color: "var(--text-muted)" }}>
                          {t(step.dKey)}
                        </p>
                      </div>
                    </div>
                  </Reveal>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* ══ Verdict simulator ══ */}
        <section id="simulator" className="section-pad max-w-[1200px] mx-auto px-5 scroll-mt-24">
          <Reveal>
            <h2 className="font-display font-bold tracking-tight text-[28px] md:text-[40px]" style={{ color: "var(--text)" }}>
              {t("sec3_title")}
            </h2>
            <p className="copy text-base lg:text-[17px] mt-3 max-w-2xl" style={{ color: "var(--text-muted)" }}>
              {t("sec3_sub")}
            </p>
          </Reveal>
          <Reveal delay={0.08} className="mt-10">
            <VerdictSimulator />
          </Reveal>
        </section>

        {/* ══ FAQ ══ */}
        <section id="faq" className="section-pad max-w-[820px] mx-auto px-5 scroll-mt-24">
          <Reveal>
            <h2 className="font-display font-bold tracking-tight text-[28px] md:text-[40px]" style={{ color: "var(--text)" }}>
              {t("sec4_title")}
            </h2>
            <p className="copy text-base lg:text-[17px] mt-3" style={{ color: "var(--text-muted)" }}>
              {t("sec4_sub")}
            </p>
          </Reveal>

          <div className="space-y-3 mt-10">
            {FAQS.map((f, i) => (
              <Reveal key={f.qKey} delay={i * 0.04}>
                <FaqItem
                  index={i}
                  open={openFaq === i}
                  onToggle={() => setOpenFaq(openFaq === i ? null : i)}
                  q={t(f.qKey)}
                  a={t(f.aKey)}
                />
              </Reveal>
            ))}
          </div>
        </section>

        {/* ══ Final CTA ══ */}
        <section className="section-pad max-w-[1200px] mx-auto px-5 text-center">
          <Reveal>
            <h2 className="font-display font-bold tracking-tight text-[28px] md:text-[40px]" style={{ color: "var(--text)" }}>
              {t("cta_title")}
            </h2>
            <p
              className="copy text-base lg:text-[17px] mt-4 max-w-xl mx-auto"
              style={{ color: "var(--text-muted)" }}
            >
              {t("cta_sub")}
            </p>
            <Link
              href="/"
              className="btn-primary inline-flex items-center gap-2 px-8 py-3.5 text-base mt-8"
            >
              {t("cta_btn")}
              <ArrowChevron className="w-4 h-4" />
            </Link>
          </Reveal>
        </section>
      </main>

      {/* ══ Footer ══ */}
      <footer style={{ borderTop: "1px solid var(--border)" }}>
        <div className="max-w-[1200px] mx-auto px-5 py-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-sm" style={{ color: "var(--text-muted)" }}>
            <Shield className="w-4 h-4" style={{ color: ACCENT }} />
            {t("footer_tag")}
          </div>
          <div className="flex items-center gap-5">
            <span className="text-sm" style={{ color: "var(--text-muted)" }}>
              {t("footer_rights")}
            </span>
            <LanguageToggle />
          </div>
        </div>
      </footer>

      <style jsx global>{`
        input[type="range"] {
          -webkit-appearance: none;
          appearance: none;
          background: transparent;
          height: 24px;
        }
        input[type="range"]::-webkit-slider-thumb {
          -webkit-appearance: none;
          width: 22px;
          height: 22px;
          border-radius: 50%;
          background: var(--text);
          border: 3px solid #0a0f0d;
          box-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
          cursor: pointer;
        }
        input[type="range"]::-moz-range-thumb {
          width: 16px;
          height: 16px;
          border-radius: 50%;
          background: var(--text);
          border: 3px solid #0a0f0d;
          box-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
          cursor: pointer;
        }
      `}</style>
    </div>
  );
}
