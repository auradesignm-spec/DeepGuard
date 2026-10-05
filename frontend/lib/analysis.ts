/* Unified analysis schema types — mirrors backend/app/analysis_schema.py.
 * Every string that can be localized arrives as { en, ar } from the engine. */

export type SectionState = "loading" | "ok" | "not_applicable" | "skipped" | "error";
export type ModelStatus = "ok" | "error" | "skipped";

export interface Bilingual {
  en: string;
  ar: string;
}

export interface ReportAxis {
  id: "ai_generation" | "editing_check" | "source_check";
  label_en?: string;
  label_ar?: string;
  state: SectionState;
  summary?: Bilingual;
  reason?: Bilingual;
}

export interface VerdictCardData {
  state: SectionState;
  label: string | null;
  confidence: number | null;
  axes: ReportAxis[];
  why_rule: Bilingual | null;
  reasoning: Bilingual | null;
  human_line: Bilingual | null;
  disagreement: { id: string; prob_fake: number; call: string }[];
  rule_id?: string;
  counts?: Record<string, number>;
  models_banded?: { id: string; prob_fake: number; call: string }[];
  fused_prob?: number | null;
  error?: string;
}

export interface ModelEntry {
  id: string;
  label_en: string;
  label_ar: string;
  kind: string;
  source?: string;
  weight?: number;
  role?: string;
  status: ModelStatus;
  prob_fake?: number;
  reason?: string;
  error?: string;
}

export interface ForensicCheck {
  id: string;
  name_en: string;
  name_ar: string;
  status: SectionState;
  flag: boolean | null;
  vote_capable: boolean;
  axes: string[];
  why_en: string;
  why_ar: string;
  data?: Record<string, any>;
  reason?: string;
  error?: string;
}

export interface SectionCard {
  state: SectionState;
  reason?: string;
  error?: string;
  data?: any;
}

export interface PipelineStep {
  name: string;
  status: SectionState;
  duration_ms: number;
  summary: string;
}

export interface AnalysisRecord {
  schema_version: string;
  id: string;
  created_at: string;
  image: {
    name: string;
    sha256?: string | null;
    size_bytes?: number | null;
    width?: number;
    height?: number;
    format?: string;
  };
  verdict: VerdictCardData;
  models: ModelEntry[];
  forensics: {
    state: SectionState;
    checks: ForensicCheck[];
    durations_ms?: Record<string, number>;
    total_ms?: number;
    error?: string;
  };
  external?: Record<string, any>;
  pipeline: PipelineStep[];
  technical_info: {
    state: SectionState;
    data?: {
      dimensions?: { width: number; height: number };
      format?: string;
      size_bytes?: number | null;
      exif?: Record<string, string>;
      exif_present?: boolean;
      jpeg_quality_estimate?: number | null;
      color_profile?: string;
      aspect_ratio?: string;
    };
    error?: string;
  };
  sections: Record<string, SectionCard>;
  multi_aspect_scores?: Record<string, number>;
  quality?: Record<string, any>;
  provenance?: string;
  arbiter_audit?: string[];
}

/* Engine verdict labels — fixed set from the backend. */
export const VERDICT_LABELS = [
  "AI Detected",
  "Possible Edits",
  "Investigate",
  "No AI Detected",
] as const;
