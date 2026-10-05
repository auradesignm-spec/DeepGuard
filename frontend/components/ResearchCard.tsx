"use client";

import React from "react";
import { ExternalLink } from "lucide-react";
import { ReportSection } from "@/components/ReportShell";
import { useLang, type DictKey, type Lang } from "@/lib/i18n";
import type { AnalysisRecord, SectionCard } from "@/lib/analysis";

/* m5 — research sections.
 *
 * Everything rendered here is either a link the backend built from data the
 * record actually carries, or a guidance line the backend generated from a
 * rule. No claim about what a search returned is ever displayed: the cards
 * say plainly that nothing was crawled or fact-checked for the user.
 */

interface SearchLink {
  id: string;
  label: string;
  url: string;
}

interface BilingualStep {
  id: string;
  en: string;
  ar: string;
}

interface ResearchData {
  engines?: SearchLink[];
  links?: SearchLink[];
  query?: string;
  note_en?: string;
  note_ar?: string;
  steps?: BilingualStep[];
  rule?: string;
  lat?: number;
  lon?: number;
  reason_en?: string;
  reason_ar?: string;
}

const MISSING: SectionCard = {
  state: "error",
  error: "Section missing from the analysis record.",
};

function Notice({
  section,
  lang,
  t,
}: {
  section: SectionCard;
  lang: Lang;
  t: (k: DictKey) => string;
}) {
  if (section.state === "ok") return null;
  const data = (section.data || {}) as ResearchData;
  if (section.state === "skipped") {
    const msg =
      (lang === "ar" ? data.reason_ar : data.reason_en) ||
      section.reason ||
      t("state_skipped");
    return (
      <p className="text-xs text-[#7da291] leading-relaxed border border-[#12281f] bg-[#081210] px-3 py-2">
        {msg}
      </p>
    );
  }
  if (section.state === "error") {
    return (
      <p className="text-xs text-[#ff8fa3] leading-relaxed border border-[#ff4d6a]/35 bg-[#ff4d6a]/10 px-3 py-2">
        {section.error || t("state_error")}
      </p>
    );
  }
  return (
    <p className="text-xs text-[#7da291] leading-relaxed border border-[#12281f] bg-[#081210] px-3 py-2">
      {section.state === "not_applicable"
        ? t("state_not_applicable")
        : t("state_loading")}
    </p>
  );
}

function LinkList({ links, aria }: { links: SearchLink[]; aria: string }) {
  if (!links.length) return null;
  return (
    <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
      {links.map((l) => (
        <li key={l.id}>
          <a
            href={l.url}
            target="_blank"
            rel="noopener noreferrer nofollow"
            aria-label={`${l.label} — ${aria}`}
            className="group flex items-center justify-between gap-2 px-3 py-2 border border-[#1d4534] bg-[#0a1613]/70 text-[#8fffc9] text-xs font-mono hover:border-[#3dffa0]/70 hover:text-[#3dffa0] transition"
          >
            <span className="truncate">{l.label}</span>
            <ExternalLink
              className="w-3.5 h-3.5 flex-shrink-0 opacity-70 group-hover:opacity-100"
              aria-hidden="true"
            />
          </a>
        </li>
      ))}
    </ul>
  );
}

function Steps({ steps, lang }: { steps: BilingualStep[]; lang: Lang }) {
  if (!steps.length) return null;
  return (
    <ol className="space-y-2">
      {steps.map((s, i) => (
        <li
          key={s.id}
          className="flex gap-3 text-xs text-[#7da291] leading-relaxed"
        >
          <span
            className="font-mono text-[#3dffa0] flex-shrink-0"
            aria-hidden="true"
          >
            {String(i + 1).padStart(2, "0")}
          </span>
          <span>{lang === "ar" ? s.ar : s.en}</span>
        </li>
      ))}
    </ol>
  );
}

function Note({
  en,
  ar,
  lang,
}: {
  en?: string;
  ar?: string;
  lang: Lang;
}) {
  const text = lang === "ar" ? ar : en;
  if (!text) return null;
  return (
    <p className="text-[11px] text-[#5b7a6b] leading-relaxed border-t border-[#12281f] pt-2">
      {text}
    </p>
  );
}

function RuleLine({ rule, t }: { rule?: string; t: (k: DictKey) => string }) {
  if (!rule) return null;
  return (
    <p className="text-[10px] font-mono text-[#4b6759]" dir="auto">
      {t("res_rule")}: {rule}
    </p>
  );
}

function QueryLine({
  query,
  t,
}: {
  query?: string;
  t: (k: DictKey) => string;
}) {
  if (!query) return null;
  return (
    <p className="text-[11px] font-mono text-[#7da291]">
      {t("res_query")}:{" "}
      <span className="text-[#8fffc9]" dir="auto">
        {query}
      </span>
    </p>
  );
}

/* ------------------------------------------------------------------ */

export default function ResearchCard({ record }: { record: AnalysisRecord }) {
  const { t, lang } = useLang();
  const sections = record.sections || {};
  const get = (id: string): SectionCard => sections[id] || MISSING;

  const reverse = get("reverse_search");
  const reverseData = (reverse.data || {}) as ResearchData;
  const links = get("links_on_web");
  const linksData = (links.data || {}) as ResearchData;
  const fact = get("fact_check_monitor");
  const factData = (fact.data || {}) as ResearchData;
  const further = get("further_investigation");
  const furtherData = (further.data || {}) as ResearchData;
  const location = get("location");
  const locationData = (location.data || {}) as ResearchData;
  const todo = get("what_to_do_next");
  const todoData = (todo.data || {}) as ResearchData;

  return (
    <>
      <ReportSection
        id="reverse-search"
        titleKey="sec_reverse_search"
        state={reverse.state}
      >
        <Notice section={reverse} lang={lang} t={t} />
        {reverse.state === "ok" && (
          <>
            <LinkList
              links={reverseData.engines || []}
              aria={t("sec_reverse_search")}
            />
            <Note
              en={reverseData.note_en}
              ar={reverseData.note_ar}
              lang={lang}
            />
          </>
        )}
      </ReportSection>

      <ReportSection
        id="links-on-web"
        titleKey="sec_links_web"
        state={links.state}
      >
        <Notice section={links} lang={lang} t={t} />
        {links.state === "ok" && (
          <>
            <QueryLine query={linksData.query} t={t} />
            <LinkList links={linksData.links || []} aria={t("res_query")} />
            <Note en={linksData.note_en} ar={linksData.note_ar} lang={lang} />
          </>
        )}
      </ReportSection>

      <ReportSection
        id="fact-check-monitor"
        titleKey="sec_fact_check"
        state={fact.state}
      >
        <Notice section={fact} lang={lang} t={t} />
        {fact.state === "ok" && (
          <>
            <QueryLine query={factData.query} t={t} />
            <LinkList links={factData.links || []} aria={t("sec_fact_check")} />
            <Note en={factData.note_en} ar={factData.note_ar} lang={lang} />
          </>
        )}
      </ReportSection>

      <ReportSection
        id="further-investigation"
        titleKey="sec_further"
        state={further.state}
      >
        <Notice section={further} lang={lang} t={t} />
        {further.state === "ok" && (
          <>
            <Steps steps={furtherData.steps || []} lang={lang} />
            {furtherData.links && (
              <div className="pt-2">
                <LinkList
                  links={furtherData.links}
                  aria={t("sec_further")}
                />
              </div>
            )}
            <RuleLine rule={furtherData.rule} t={t} />
          </>
        )}
      </ReportSection>

      <ReportSection
        id="location"
        titleKey="sec_location"
        state={location.state}
      >
        <Notice section={location} lang={lang} t={t} />
        {location.state === "ok" && (
          <>
            <p className="text-[11px] font-mono text-[#7da291]">
              {t("res_coords")}:{" "}
              <span className="text-[#8fffc9]" dir="ltr">
                {locationData.lat}, {locationData.lon}
              </span>
            </p>
            <LinkList
              links={locationData.links || []}
              aria={t("sec_location")}
            />
            <Note
              en={locationData.note_en}
              ar={locationData.note_ar}
              lang={lang}
            />
          </>
        )}
      </ReportSection>

      <ReportSection
        id="what-to-do-next"
        titleKey="sec_what_to_do"
        state={todo.state}
      >
        <Notice section={todo} lang={lang} t={t} />
        {todo.state === "ok" && (
          <>
            <Steps steps={todoData.steps || []} lang={lang} />
            <RuleLine rule={todoData.rule} t={t} />
          </>
        )}
      </ReportSection>
    </>
  );
}
