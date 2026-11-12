export type ConfigId = 'bm25-smoke' | 'research-v0';
export type ReviewDecision = 'ACCEPT' | 'REJECT' | 'DEFER';

export interface SourceSpan {
  locator?: {
    page_label?: string | number | null;
    page_index?: number | null;
    section_path?: string[] | null;
  };
  page_label?: string | number | null;
  page_index?: number | null;
  matched_element_raw_start?: number;
  matched_element_raw_end?: number;
  element_raw_char_start?: number;
  element_raw_char_end?: number;
}

export interface EvidenceRange {
  text?: string;
  normalized_start?: number;
  normalized_end?: number;
  raw_start?: number | null;
  raw_end?: number | null;
  source_spans?: SourceSpan[];
}

export interface SimilarityMatch {
  query_id: string;
  report_chunk_id: string;
  source_document_id: string;
  source_name?: string | null;
  source_chunk_id: string;
  rank: number;
  similarity_type?: string | null;
  provisional_similarity_type?: string | null;
  classification_status: string;
  selected_for_document_coverage: boolean;
  selected_for_manual_review: boolean;
  review_group_id?: string;
  alignment?: {
    kind?: string;
    report?: EvidenceRange;
    source?: EvidenceRange;
  };
}

export interface SimilarityReviewSourceGroup {
  group_id: string;
  source_document_id: string;
  source_chunk_id: string;
  source_name?: string | null;
  report_chunk_ids: string[];
  report_chunk_count: number;
  classification_status: 'PROVISIONAL_REVIEW_REQUIRED';
  warning: 'REPEATED_SOURCE_CHUNK_NOT_INDEPENDENT_EVIDENCE' | null;
}

export interface SimilarityReport {
  research_status?: string;
  report_chunk_count?: number;
  source_chunk_count?: number;
  exact_match_coverage_percentage?: number;
  provisional_review_report_chunks?: number;
  provisional_review_passage_coverage_percentage?: number;
  calibrated_similarity_percentage?: number | null;
  source_summary?: Array<{
    source_document_id: string;
    source_name?: string | null;
    selected_report_passages: number;
  }>;
  matches?: SimilarityMatch[];
  review_source_groups?: SimilarityReviewSourceGroup[];
  disclaimer?: string;
}

export interface AssessmentEvidence {
  evidence_id: string;
  source_name?: string | null;
  excerpt?: string;
  source_spans?: SourceSpan[];
}

export interface AssessmentSpan {
  requirement_id?: string;
  matched_alternative?: string;
  evidence_id?: string;
  span?: EvidenceRange;
}

export interface ChecklistResult {
  checklist_id: string;
  criterion_id: string;
  statement: string;
  mode: string;
  importance?: string;
  checklist_outcome: 'MET' | 'UNMET' | 'CANNOT_ASSESS' | string;
  verification_relation?: string;
  reason_code?: string;
  rationale?: string;
  matched_evidence_spans?: AssessmentSpan[];
  negated_evidence_spans?: AssessmentSpan[];
  evidence_pack?: AssessmentEvidence[];
}

export interface AssessmentReport {
  proposed_total_score?: number | null;
  max_score?: number;
  checklist_outcome_counts?: Record<string, number>;
  checklist_results?: ChecklistResult[];
  criterion_results?: Array<{
    criterion_id: string;
    title: string;
    weight: number;
    proposed_score: number | null;
    score_reason?: string;
  }>;
  requires_lecturer_review?: boolean;
  limitations?: string[];
}

export interface RunSummary {
  pipeline1?: {
    report_chunks?: number;
    source_chunks?: number;
    exact_match_coverage_percentage?: number;
    provisional_review_report_chunks?: number;
    provisional_review_passage_coverage_percentage?: number;
    calibrated_similarity_percentage?: number | null;
  } | null;
  pipeline2?: {
    checklist_outcome_counts?: Record<string, number>;
    proposed_total_score?: number | null;
    max_score?: number;
    requires_lecturer_review?: boolean;
  } | null;
  timings_seconds?: Record<string, number>;
}

export interface LocalReview {
  decision?: ReviewDecision;
  comment?: string;
  reviewer_name?: string;
  reviewed_at?: string;
  reviewed_at_utc?: string;
}

export interface RunRecord {
  run_id: string;
  job_id?: string;
  status: string;
  config_id?: ConfigId;
  method_warning?: string | null;
  human_review_required?: boolean;
  inputs?: { report?: string; sources?: string[] };
  summary?: RunSummary | null;
  similarity_report?: SimilarityReport | null;
  assessment_report?: AssessmentReport | null;
  review?: LocalReview | null;
  revision?: number;
  error?: string | null;
}
