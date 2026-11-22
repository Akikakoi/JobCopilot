export type Role = "seeker" | "employer";

export interface User {
  id: number;
  username: string;
  role: Role;
  display_name: string;
  company_name?: string | null;
}

export interface Job {
  id: number;
  company_id: number;
  company_name: string;
  company_industry: string;
  title: string;
  description: string;
  required_skills: string[];
  preferred_skills: string[];
  experience_min: number;
  experience_max: number;
  location: string;
  district: string;
  category: string;
  job_type: string;
  salary_min: number;
  salary_max: number;
  status: string;
  created_at?: string;
}

interface EducationItem {
  school: string;
  degree: string;
  major: string;
  period: string;
}

interface WorkItem {
  company: string;
  role: string;
  period: string;
  highlights: string[];
}

interface ResumeStructured {
  name: string;
  title: string;
  skills: string[];
  years_of_experience: number;
  education: EducationItem[];
  work_experience: WorkItem[];
  expectations: {
    locations: string[];
    salary_min?: number | null;
    salary_max?: number | null;
    job_types: string[];
  };
}

interface ResumeFileInfo {
  name: string;
  content_type: string;
  size: number;
  previewable: boolean;
}

export interface Resume {
  id: number;
  user_id: number;
  raw_text: string;
  structured: ResumeStructured;
  source: string;
  has_embedding: boolean;
  updated_at: string;
  file?: ResumeFileInfo | null;
}

interface SkillBreakdown {
  score: number;
  max: number;
  matched: string[];
  missing?: string[];
}

interface Breakdown {
  skills_required: SkillBreakdown;
  skills_preferred: SkillBreakdown;
  experience: { score: number; max: number; resume_years: number; required_years: number };
  location: { score: number; max: number; resume_locations: string[]; job_location: string };
  salary: { score: number; max: number; resume_range: (number | null)[]; job_range: number[] };
}

export interface MatchItem extends Job {
  similarity: number;
  match_score: number;
  rank_score: number;
  my_feedback: "dislike" | "save" | null;
  breakdown: Breakdown;
}

interface MatchExplanation {
  summary: string;
  reasons: string[];
  gaps: string[];
  suggestions: string[];
}

export interface MatchDetail {
  job: Job;
  match_score: number;
  breakdown: Breakdown;
  explanation: MatchExplanation;
  applied: boolean;
  application_id: number | null;
}

interface ApplicationEvent {
  id: number;
  application_id: number;
  from_status: string;
  from_status_label: string;
  to_status: string;
  to_status_label: string;
  note: string;
  created_at: string;
}

export interface InterviewInvite {
  id: number;
  application_id: number;
  job_id: number;
  round: number;
  scheduled_at: string;
  duration_minutes: number;
  mode: "onsite" | "video" | "phone";
  mode_label: string;
  location: string;
  note: string;
  status: "pending" | "confirmed" | "declined" | "cancelled" | "completed";
  status_label: string;
  candidate_note: string;
  created_at: string;
}

export interface Offer {
  id: number;
  application_id: number;
  job_id: number;
  salary_min: number;
  salary_max: number;
  start_date: string;
  expires_at: string | null;
  note: string;
  status: "pending" | "accepted" | "declined" | "expired";
  status_label: string;
  response_note: string;
  responded_at: string | null;
  created_at: string;
}

export interface Onboarding {
  date: string;
  confirmed: boolean;
  confirmed_at: string | null;
  result: "" | "hired" | "abandoned";
  result_label: string;
  result_at: string | null;
  note: string;
}

export interface Application {
  id: number;
  job_id: number;
  job_title: string;
  company_name: string;
  resume_id: number;
  status: string;
  status_label: string;
  status_note: string;
  match_score: number | null;
  match_explanation: MatchExplanation | null;
  cover_letter: string;
  offer: Offer | null;
  onboarding: Onboarding;
  interview_invites: InterviewInvite[];
  events: ApplicationEvent[];
  created_at: string;
  updated_at: string;
}

export interface Candidate {
  application_id: number;
  user_id: number;
  job_id: number;
  job_title: string;
  candidate_name: string;
  structured: ResumeStructured;
  status: string;
  status_label: string;
  status_note: string;
  onboarding: Onboarding;
  cover_letter: string;
  has_resume_file: boolean;
  resume_file_name: string;
  match_score: number;
  similarity: number;
  breakdown: Breakdown;
  match_explanation: MatchExplanation | null;
  offer: Offer | null;
  interview_invites: InterviewInvite[];
}

export interface CompanyInfo {
  id: number;
  name: string;
  industry: string;
  description: string;
}

export interface CompanyDetail extends CompanyInfo {
  open_job_count: number;
  jobs: Job[];
}

export interface AgentSession {
  id: number;
  agent_type: Role;
  title: string;
  created_at: string;
}

export interface AgentMessage {
  id: number;
  role: string;
  content: string;
  tool_calls: Array<{
    id: string;
    type: string;
    function: { name: string; arguments: string };
  }> | null;
  tool_call_id: string | null;
  created_at: string;
}

export interface ChatEvent {
  type: "token" | "tool_start" | "tool_end" | "done" | "error";
  content?: string;
  id?: string;
  name?: string;
  args?: Record<string, unknown>;
  result?: string;
  message?: string;
  session_title?: string;
  note?: string;
}

export interface ToolTrace {
  id: string;
  name: string;
  args: Record<string, unknown>;
  result?: string;
  status: "running" | "done";
}

type DuelSpeaker = "seeker" | "employer";

export interface DuelEvent {
  type:
    | "duel_start"
    | "speaker"
    | "token"
    | "tool_start"
    | "tool_end"
    | "turn_end"
    | "done"
    | "error";
  speaker?: DuelSpeaker;
  round?: number;
  rounds?: number;
  job?: string;
  content?: string;
  id?: string;
  name?: string;
  args?: Record<string, unknown>;
  result?: string;
  message?: string;
  turns?: number;
}

export interface DuelTurn {
  key: string;
  speaker: DuelSpeaker;
  round: number;
  content: string;
  traces: ToolTrace[];
  streaming: boolean;
}

interface InterviewQuestion {
  id: string;
  category: string;
  question: string;
  focus: string;
  reference_points: string[];
}

interface InterviewAnswer {
  question_id: string;
  answer: string;
  score?: number;
  rationale?: string;
}

interface InterviewReport {
  overall_score: number;
  dimensions: Record<string, number>;
  strengths: string[];
  risks: string[];
  suggestions: string[];
  summary: string;
  per_question: Array<{ question_id: string; score: number; rationale: string }>;
}

export interface Interview {
  id: number;
  user_id: number;
  job_id: number;
  job_title: string;
  company_name: string;
  application_id: number | null;
  status: "in_progress" | "completed" | "draft";
  plan: { questions: InterviewQuestion[] };
  answers: InterviewAnswer[];
  report: InterviewReport | null;
  overall_score: number | null;
  created_at: string;
  updated_at: string;
}

export interface InterviewSummary {
  id: number;
  job_id: number;
  job_title: string;
  company_name: string;
  status: string;
  overall_score: number | null;
  question_count: number;
  answered_count: number;
  created_at: string;
}

interface SubscriptionFilters {
  keywords: string;
  location: string;
  salary_min: number | null;
  skills: string[];
  match_score_min: number | null;
}

export interface Subscription {
  id: number;
  name: string;
  filters: SubscriptionFilters;
  active: boolean;
  last_checked_at: string | null;
  created_at: string;
}

export interface ConversationSummary {
  id: number;
  application_id: number;
  job_id: number;
  job_title: string;
  company_name: string;
  candidate_name: string;
  other_name: string;
  unread: number;
  last_message: {
    content: string;
    created_at: string;
    sender_user_id: number;
    mine: boolean;
  } | null;
}

export interface ChatMessage {
  id: number;
  conversation_id: number;
  content: string;
  sender_user_id: number;
  mine: boolean;
  created_at: string;
}

export interface AppNotification {
  id: number;
  type: string;
  title: string;
  payload: {
    job_id?: number;
    application_id?: number;
    status?: string;
    status_label?: string;
    note?: string;
    title?: string;
    company_name?: string;
    location?: string;
    salary_min?: number;
    salary_max?: number;
    match_score?: number | null;
    subscription_name?: string;
  };
  read: boolean;
  created_at: string;
}

export interface ResumeVersion {
  id: number;
  label: string;
  note: string;
  skills: string[];
  title: string;
  years_of_experience: number;
  created_at: string;
}

interface ResumeOptimizeRewrite {
  target: string;
  original: string;
  suggestion: string;
}

export interface ResumeOptimize {
  summary: string;
  missing_skills: string[];
  skills_to_add: string[];
  rewrites: ResumeOptimizeRewrite[];
  keywords: string[];
  suggestions: string[];
}
