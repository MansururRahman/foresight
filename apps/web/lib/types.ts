// TypeScript mirrors of the API response shapes (services/api/app/schemas).

export type UserRef = { id: string; email: string; name: string };
export type WorkspaceRole = "owner" | "admin" | "member";
export type ProjectStatus = "planning" | "active" | "closed";
export type SessionPhase = "collect" | "merge" | "vote" | "sealed";
export type RiskOrigin = "participant" | "suggestion" | "surprise";
export type GradingOutcome = "yes" | "no" | "partial";

export type WorkspaceOut = { id: string; name: string; slug: string; my_role: WorkspaceRole; created_at: string };
export type MemberOut = { user: UserRef; role: WorkspaceRole; joined_at: string };
export type TagStat = { tag: string; project_count: number; risk_count: number };

export type SessionSummary = { id: string; phase: SessionPhase; sealed_at: string | null; fully_graded_at: string | null };
export type ProjectOut = {
  id: string;
  workspace_id: string;
  title: string;
  description: string;
  tags: string[];
  planned_start: string | null;
  planned_end: string | null;
  status: ProjectStatus;
  activated_at: string | null;
  closed_at: string | null;
  archived_at: string | null;
  created_by: UserRef;
  created_at: string;
  updated_at: string;
  session: SessionSummary | null;
};
export type ProjectPage = { items: ProjectOut[]; next_cursor: string | null };
export type TransitionResult = { project: ProjectOut; warnings: { code: string; count: number }[] };

export type SessionOut = {
  id: string;
  project_id: string;
  workspace_id: string;
  phase: SessionPhase;
  facilitator: UserRef;
  created_by: UserRef;
  phase_changed_at: string;
  sealed_at: string | null;
  fully_graded_at: string | null;
  participants: UserRef[];
  counts: { risks_total: number; risks_canonical: number; participants: number; voters_complete: number };
  me: { is_facilitator: boolean; is_participant: boolean; risks_submitted: number; votes_cast: number; votes_required: number };
};
export type SessionTransitionResult = { session: SessionOut; incomplete_voters: UserRef[] };

export type Aggregates = {
  vote_count: number;
  mean_probability: number;
  median_probability: number;
  probability_stddev: number;
  agreement: number;
  mean_impact: number;
  risk_score: number;
};
export type GradingOut = { outcome: GradingOutcome; note: string; graded_by: UserRef; updated_at: string };
export type RiskOut = {
  id: string;
  session_id: string | null;
  project_id: string;
  statement: string;
  tags: string[];
  origin: RiskOrigin;
  duplicate_of: string | null;
  source_risk_id: string | null;
  author: UserRef | null;
  created_at: string;
  updated_at: string;
  aggregates: Aggregates | null;
  merged_from: { id: string; statement: string }[];
  my_vote: { probability: number; impact: number } | null;
  grading: GradingOut | null;
};
export type RiskList = { phase: SessionPhase; items: RiskOut[]; submission_counts: { user: UserRef; count: number }[] | null };

export type MyVotes = { items: { risk_id: string; probability: number; impact: number; updated_at: string }[]; required: number };
export type ResultRisk = RiskOut & { histogram: number[] };
export type ResultsOut = {
  session: SessionOut;
  risks: ResultRisk[];
  participation: { participants: number; voters_complete: number; voters_partial: number; voters_none: number };
};

export type CloseoutOut = {
  project: ProjectOut;
  session: SessionOut | null;
  risks: RiskOut[];
  surprises: RiskOut[];
  ungraded_count: number;
  possible_duplicates: { surprise_id: string; risk_id: string; similarity: number }[];
};
export type ReportRisk = {
  risk_id: string;
  statement: string;
  tags: string[];
  mean_predicted: number | null;
  agreement: number | null;
  mean_impact: number | null;
  outcome: GradingOutcome | null;
  miss: number | null;
  note: string;
};
export type ProjectReport = {
  project: ProjectOut;
  session: SessionOut | null;
  summary: {
    n_canonical: number;
    n_graded: number;
    n_voters: number;
    expected_materialized: number;
    actual_materialized: number;
    project_brier: number | null;
    n_predictions: number;
  };
  risks: ReportRisk[];
  surprises: { risk_id: string; statement: string; tags: string[] }[];
  biggest_misses: ReportRisk[];
};

export type Bin = { index: number; range: [number, number]; n: number; mean_predicted: number | null; observed: number | null; reliable: boolean };
export type TrendPoint = {
  project_id: string;
  project_title: string | null;
  closed_at: string | null;
  n_project: number;
  brier_project: number;
  n_rolling: number;
  brier_rolling: number | null;
  brier_cumulative: number;
};
export type Trend = { direction: "improving" | "worsening" | "flat" | "insufficient_data"; slope: number | null; points: TrendPoint[] };
export type BiasLabel = "over_estimates_risk" | "under_estimates_risk" | "calibrated";
export type ConfidenceLabel = "overconfident" | "underconfident" | "calibrated";
type SummaryFields = {
  brier: number | null;
  brier_skill: number | null;
  base_rate: number;
  bias: number | null;
  bias_label: BiasLabel | null;
  ece: number | null;
  overconfidence: number | null;
  confidence_label: ConfidenceLabel | null;
  bins: Bin[];
  trend: Trend;
};
export type WorstCall = {
  risk_id: string;
  project_id: string;
  project_title: string | null;
  statement: string | null;
  probability: number;
  outcome: GradingOutcome;
  brier_contribution: number;
};
export type UserCalibration = SummaryFields & {
  sample: { n_graded: number; n_projects: number; needed: number; sufficient: boolean };
  user: UserRef;
  workspace_id: string;
  worst_calls: WorstCall[];
};
export type BlindSpot = {
  risk_id: string;
  project_id: string;
  project_title: string;
  statement: string;
  tags: string[];
  mean_predicted: number;
  outcome: GradingOutcome;
  miss: number;
};
export type TagCalibration = { tag: string; n: number; mean_predicted: number; observed: number; bias: number; brier: number; chronic: "under" | "over" | null };
export type WorkspaceCalibration = SummaryFields & {
  workspace_id: string;
  sample: { n_graded: number; n_projects_closed: number; n_projects_graded: number; n_voters: number; needed: number; sufficient: boolean };
  blind_spots: BlindSpot[];
  false_alarms: BlindSpot[];
  tags: TagCalibration[];
  surprises: {
    rate_per_project: number;
    share: number | null;
    n_surprises: number;
    n_projects: number;
    recent: { risk_id: string; project_id: string; project_title: string; statement: string; tags: string[] }[];
  };
  members: { user: UserRef; n_graded: number; brier: number | null; bias: number | null }[] | null;
};

export type SuggestionSource = {
  risk_id: string;
  project_id: string;
  project_title: string;
  project_similarity: number;
  outcome: GradingOutcome;
  mean_predicted_probability: number | null;
  origin: RiskOrigin;
  closed_at: string | null;
};
export type Suggestion = {
  statement: string;
  score: number;
  materialization_rate: number;
  occurrences: number;
  mean_predicted_probability: number | null;
  tags: string[];
  sources: SuggestionSource[];
};
export type SuggestionsOut = { query: { tags: string[]; matched_projects: number }; suggestions: Suggestion[] };
