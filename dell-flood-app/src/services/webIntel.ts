import AsyncStorage from '@react-native-async-storage/async-storage';
import { apiService } from './api';

// Mirrors dell-flood-backend/app/intel/evidence.py (schema_version 1.1). Datetimes arrive as ISO-8601 strings.

export const SCHEMA_VERSION = '1.1';

export type IsoDateTime = string;

export type ProductId =
  | 'river_levels'
  | 'imd_warnings'
  | 'official_alerts'
  | 'state_bulletin'
  | 'mobility'
  | 'relief_camps'
  | 'district_brief'
  | 'news_corroboration'
  | 'helplines'
  | 'health_power';

export type EvidenceCategory =
  | 'official_warning'
  | 'river_level'
  | 'rainfall'
  | 'official_alert'
  | 'bulletin'
  | 'barrage_gate'
  | 'embankment'
  | 'rail_disruption'
  | 'road_closure'
  | 'relief_camp'
  | 'news_report'
  | 'helpline'
  | 'hospital_capacity'
  | 'power_outage'
  | 'situation_brief'
  | 'other';

export type RunState = 'queued' | 'running' | 'succeeded' | 'partial' | 'failed' | 'disabled' | 'cancelled';
export type TerminalRunState = Extract<RunState, 'succeeded' | 'partial' | 'failed' | 'disabled' | 'cancelled'>;
export type AccessMethod = 'api' | 'rss' | 'fetch' | 'agent' | 'search' | 'research';
export type SourceType = 'official' | 'secondary' | 'unknown';
export type LocationMatch = 'verified' | 'approximate' | 'uncertain';
export type Freshness = 'fresh' | 'stale' | 'unknown';
export type ValidationStatus = 'verified' | 'partial' | 'rejected';
export type Grade = 'verified_official' | 'credible_secondary' | 'unverified' | 'insufficient';
export type Signal = 'elevated' | 'normal' | 'unknown';
export type FailureReason =
  | 'login_wall'
  | 'anti_bot'
  | 'timeout'
  | 'goal_failure'
  | 'schema_invalid'
  | 'stale'
  | 'out_of_season'
  | 'http_error'
  | 'billing'
  | 'disabled'
  | 'budget_exceeded'
  | 'unverified_source'
  | 'interrupted';
export type TaskState = 'queued' | 'running' | 'succeeded' | 'failed' | 'skipped' | 'cancelled';
export type RunMode = 'live' | 'replay' | 'disabled';
export type MeasurementUnit = 'm' | 'mm' | 'm3/s';
export type Trend = 'rising' | 'falling' | 'steady';
export type ConflictKind = 'value_disagreement' | 'official_vs_secondary';
export type FreshnessStatus = 'ATTACHED' | 'STALE' | 'NONE_AVAILABLE';
export type MonitorKind = 'page' | 'topic';

const TERMINAL_STATES: ReadonlySet<RunState> = new Set<TerminalRunState>([
  'succeeded',
  'partial',
  'failed',
  'disabled',
  'cancelled',
]);

export function isTerminal(state: RunState): state is TerminalRunState {
  return TERMINAL_STATES.has(state);
}

export interface Measurement {
  station: string | null;
  river: string | null;
  value: number;
  unit: MeasurementUnit;
  danger_level: number | null;
  warning_level: number | null;
  hfl: number | null;
  trend: Trend | null;
}

export interface Evidence {
  evidence_id: string;
  claim: string;
  category: EvidenceCategory;
  product_id: ProductId;
  source_id: string;
  source_name: string;
  source_type: SourceType;
  source_url: string;
  retrieved_at: IsoDateTime;
  published_at: IsoDateTime | null;
  observed_at: IsoDateTime | null;
  district: string | null;
  location_match: LocationMatch;
  freshness: Freshness;
  validation_status: ValidationStatus;
  grade: Grade;
  signal: Signal;
  quality_score: number;
  measurement: Measurement | null;
  access_method: AccessMethod;
  tinyfish_run_id: string | null;
  excerpt: string | null;
  notes: string[];
  mock: boolean;
}

export interface FailedSource {
  source_id: string;
  product_id: ProductId | null;
  reason: FailureReason;
  detail: string | null;
  retry_after_s: number | null;
  tinyfish_run_id: string | null;
}

export interface Conflict {
  kind: ConflictKind;
  key: string;
  evidence_ids: string[];
  detail: string;
}

export interface LiveView {
  streaming_url: string;
  expires_at: IsoDateTime;
  tinyfish_run_id: string | null;
}

export interface LocationQuery {
  query: string;
  resolved_name: string | null;
  latitude: number;
  longitude: number;
  jurisdiction: string | null;
  state: string | null;
  district: string | null;
}

export interface SourceTaskStatus {
  source_id: string;
  product_id: ProductId;
  access_method: AccessMethod;
  state: TaskState;
  evidence_count: number;
  tinyfish_run_id: string | null;
}

export interface AgentMetadata {
  provider: 'TinyFish';
  tinyfish_run_ids: string[];
  run_statuses: Record<string, string>;
  result_statuses: Record<string, string>;
  num_of_steps: number | null;
  estimated_cost_usd: number | null;
  budget_usd: number | null;
}

export interface WebIntelRun {
  schema_version: typeof SCHEMA_VERSION;
  run_id: string;
  state: RunState;
  mode: RunMode;
  products: ProductId[];
  location: LocationQuery;
  created_at: IsoDateTime;
  started_at: IsoDateTime | null;
  finished_at: IsoDateTime | null;
  summary: string | null;
  evidence: Evidence[];
  source_tasks: SourceTaskStatus[];
  sources_checked: number;
  sources_succeeded: number;
  sources_failed: number;
  failed_sources: FailedSource[];
  conflicts: Conflict[];
  data_quality: string[];
  human_review_required: true;
  quality_score_note: string;
  disclaimer: string;
  agent_metadata: AgentMetadata;
  live_view: LiveView | null;
  error: string | null;
}

export interface ProductDescription {
  id: ProductId;
  title: string;
  description: string;
  feature: string;
  categories: EvidenceCategory[];
  source_ids: string[];
  operation: string;
  default: boolean;
}

export interface SourceDescription {
  id: string;
  name: string;
  authority: string;
  access_method: AccessMethod;
  source_type: SourceType;
  jurisdictions: string[];
  verified: boolean;
  in_season: boolean;
  allow_readonly_lookup: boolean;
  notes: string;
}

export interface ProductWithSources extends ProductDescription {
  sources: SourceDescription[];
}

export interface WebIntelLimits {
  max_concurrent_agent_runs: number;
  usd_per_step: number;
  max_usd_per_request: number;
  max_steps_per_run: number;
  run_timeout_s: number;
  allow_unverified_sources: boolean;
}

export interface WebIntelConfig {
  schema_version: string;
  mode: RunMode;
  enabled: boolean;
  products: ProductDescription[];
  default_products: ProductId[];
  limits: WebIntelLimits;
  monitors_available: boolean;
  disclaimer: string;
}

export interface StartRunBody {
  location: string;
  lat: number;
  lon: number;
  state?: string;
  district?: string;
  products?: ProductId[];
  stream?: boolean;
}

export interface StartRunResponse {
  run_id: string;
  state: RunState;
}

export interface CancelRunResponse {
  run_id: string;
  state: RunState;
  cancel_requested: true;
}

export interface LatestParams {
  district?: string;
  state?: string;
  lat?: number;
  lon?: number;
  max_age_s?: number;
}

export type LatestResponse =
  | { status: 'ATTACHED' | 'STALE'; run: WebIntelRun }
  | { status: 'NONE_AVAILABLE'; run: null };

export interface Monitor {
  monitor_id: string;
  kind: MonitorKind;
  target: string;
  source_id: string | null;
  district: string | null;
  state: string | null;
  products: ProductId[];
  schedule_cron: string;
  created_at: IsoDateTime;
  webhook_configured: boolean;
}

export interface CreateMonitorBody {
  kind: MonitorKind;
  source_id?: string;
  location: string;
  lat: number;
  lon: number;
  state?: string;
  district?: string;
  products?: ProductId[];
  schedule_cron?: string;
}

// Shape of routes.py::evidence_for_hitl, the compact evidence embedded in a HITL queue item.
export const HITL_EVIDENCE_FIELDS = [
  'evidence_id',
  'claim',
  'category',
  'grade',
  'source_id',
  'source_name',
  'source_type',
  'source_url',
  'retrieved_at',
  'published_at',
  'observed_at',
  'freshness',
  'validation_status',
  'location_match',
  'signal',
  'quality_score',
  'measurement',
  'tinyfish_run_id',
  'mock',
] as const;

export type CompactEvidence = Pick<Evidence, (typeof HITL_EVIDENCE_FIELDS)[number]>;

interface HitlEvidenceCommon {
  evidence: CompactEvidence[];
  conflicts: Conflict[];
  failed_sources: FailedSource[];
  data_quality: string[];
  disclaimer: string;
  quality_score_note: string;
}

export type HitlEvidence =
  | (HitlEvidenceCommon & { status: 'NONE_AVAILABLE'; run_id: null })
  | (HitlEvidenceCommon & {
      status: 'ATTACHED' | 'STALE';
      run_id: string;
      run_state: RunState;
      finished_at: IsoDateTime | null;
      summary: string | null;
    });

export type WebIntelErrorKind = 'network' | 'timeout' | 'aborted' | 'http' | 'contract';

export interface WebIntelError {
  kind: WebIntelErrorKind;
  message: string;
  status?: number;
}

export type Result<T> = { ok: true; value: T } | { ok: false; error: WebIntelError };

export const REQUEST_TIMEOUT_MS = 8000;
const TOKEN_KEY = 'aegis_jwt_token';

function baseUrl(): string {
  return `${apiService.apiUrl.replace(/\/$/, '')}/agent/web-intelligence`;
}

async function authHeader(): Promise<Record<string, string>> {
  try {
    const token = await AsyncStorage.getItem(TOKEN_KEY);
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}

function detailText(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object' || !('detail' in payload)) return null;
  const detail = (payload as { detail: unknown }).detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((d) => (d && typeof d === 'object' && 'msg' in d ? String((d as { msg: unknown }).msg) : null))
      .filter((m): m is string => !!m);
    return parts.length ? parts.join('; ') : null;
  }
  return null;
}

function httpMessage(status: number, payload: unknown): string {
  const detail = detailText(payload);
  if (status === 401) return detail ? `Sign in required: ${detail}` : 'Sign in as an official to use web intelligence.';
  if (status === 403) return detail ? `Not permitted: ${detail}` : 'Only officials can use web intelligence.';
  return detail ?? `Backend returned HTTP ${status}.`;
}

async function request<T>(
  method: 'GET' | 'POST' | 'DELETE',
  path: string,
  opts: { body?: unknown; signal?: AbortSignal; check?: (value: unknown) => string | null } = {},
): Promise<Result<T>> {
  if (opts.signal?.aborted) return { ok: false, error: { kind: 'aborted', message: 'Request cancelled.' } };
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, REQUEST_TIMEOUT_MS);
  const forwardAbort = () => controller.abort();
  opts.signal?.addEventListener('abort', forwardAbort);
  try {
    const headers: Record<string, string> = { Accept: 'application/json', ...(await authHeader()) };
    if (opts.body !== undefined) headers['Content-Type'] = 'application/json';
    const res = await fetch(`${baseUrl()}${path}`, {
      method,
      headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
      signal: controller.signal,
    });
    let payload: unknown = null;
    try {
      payload = await res.json();
    } catch {
      payload = null;
    }
    if (!res.ok) return { ok: false, error: { kind: 'http', status: res.status, message: httpMessage(res.status, payload) } };
    const problem = opts.check ? opts.check(payload) : null;
    if (problem) return { ok: false, error: { kind: 'contract', message: problem } };
    return { ok: true, value: payload as T };
  } catch (e) {
    if (timedOut) {
      return { ok: false, error: { kind: 'timeout', message: `Backend did not answer within ${REQUEST_TIMEOUT_MS / 1000} s.` } };
    }
    if (opts.signal?.aborted) return { ok: false, error: { kind: 'aborted', message: 'Request cancelled.' } };
    const reason = e instanceof Error ? e.message : String(e);
    return { ok: false, error: { kind: 'network', message: `Could not reach the Aegis backend at ${baseUrl()} (${reason}).` } };
  } finally {
    clearTimeout(timer);
    opts.signal?.removeEventListener('abort', forwardAbort);
  }
}

const RUN_STATES: ReadonlySet<string> = new Set<RunState>([
  'queued',
  'running',
  'succeeded',
  'partial',
  'failed',
  'disabled',
  'cancelled',
]);

function isRecord(v: unknown): v is Record<string, unknown> {
  return !!v && typeof v === 'object' && !Array.isArray(v);
}

function checkRun(v: unknown): string | null {
  if (!isRecord(v)) return 'Run response is not an object.';
  if (v.schema_version !== SCHEMA_VERSION) {
    return `Backend web-intel schema ${String(v.schema_version)} does not match this app (${SCHEMA_VERSION}).`;
  }
  if (typeof v.run_id !== 'string' || !RUN_STATES.has(String(v.state))) return 'Run response is missing run_id or state.';
  if (!Array.isArray(v.evidence) || !Array.isArray(v.source_tasks)) return 'Run response is missing evidence lists.';
  return null;
}

function checkConfig(v: unknown): string | null {
  if (!isRecord(v)) return 'Config response is not an object.';
  if (v.schema_version !== SCHEMA_VERSION) {
    return `Backend web-intel schema ${String(v.schema_version)} does not match this app (${SCHEMA_VERSION}).`;
  }
  if (!Array.isArray(v.products) || !Array.isArray(v.default_products)) return 'Config response is missing products.';
  return null;
}

function checkLatest(v: unknown): string | null {
  if (!isRecord(v)) return 'Latest response is not an object.';
  if (v.status === 'NONE_AVAILABLE') return v.run === null ? null : 'NONE_AVAILABLE response carried a run.';
  if (v.status !== 'ATTACHED' && v.status !== 'STALE') return `Unknown latest status ${String(v.status)}.`;
  return checkRun(v.run);
}

const checkField = (field: string) => (v: unknown) =>
  isRecord(v) && Array.isArray(v[field]) ? null : `Response is missing ${field}.`;

export function getConfig(signal?: AbortSignal): Promise<Result<WebIntelConfig>> {
  return request('GET', '/config', { signal, check: checkConfig });
}

export async function getProducts(signal?: AbortSignal): Promise<Result<ProductWithSources[]>> {
  const res = await request<{ products: ProductWithSources[] }>('GET', '/products', { signal, check: checkField('products') });
  return res.ok ? { ok: true, value: res.value.products } : res;
}

export function startRun(body: StartRunBody, signal?: AbortSignal): Promise<Result<StartRunResponse>> {
  return request('POST', '/run', { body, signal });
}

export function getRun(runId: string, signal?: AbortSignal): Promise<Result<WebIntelRun>> {
  return request('GET', `/${encodeURIComponent(runId)}`, { signal, check: checkRun });
}

export function cancelRun(runId: string, signal?: AbortSignal): Promise<Result<CancelRunResponse>> {
  return request('POST', `/${encodeURIComponent(runId)}/cancel`, { signal });
}

export function getLatest(params: LatestParams, signal?: AbortSignal): Promise<Result<LatestResponse>> {
  const q = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join('&');
  return request('GET', `/latest?${q}`, { signal, check: checkLatest });
}

export async function listMonitors(signal?: AbortSignal): Promise<Result<Monitor[]>> {
  const res = await request<{ monitors: Monitor[] }>('GET', '/monitors', { signal, check: checkField('monitors') });
  return res.ok ? { ok: true, value: res.value.monitors } : res;
}

export function createMonitor(body: CreateMonitorBody, signal?: AbortSignal): Promise<Result<Monitor>> {
  return request('POST', '/monitors', { body, signal });
}

export function deleteMonitor(monitorId: string, signal?: AbortSignal): Promise<Result<{ deleted: true; monitor_id: string }>> {
  return request('DELETE', `/monitors/${encodeURIComponent(monitorId)}`, { signal });
}

export interface PollOptions {
  intervalMs?: number;
  signal?: AbortSignal;
  // Consecutive failed polls tolerated before giving up; one dropped request should not end the watch.
  maxConsecutiveErrors?: number;
  maxDurationMs?: number;
}

function wait(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (signal?.aborted) return resolve();
    const done = () => {
      clearTimeout(timer);
      signal?.removeEventListener('abort', done);
      resolve();
    };
    const timer = setTimeout(done, ms);
    signal?.addEventListener('abort', done);
  });
}

export async function pollRun(
  runId: string,
  onUpdate: (run: WebIntelRun) => void,
  { intervalMs = 2500, signal, maxConsecutiveErrors = 3, maxDurationMs = 20 * 60 * 1000 }: PollOptions = {},
): Promise<Result<WebIntelRun>> {
  const deadline = Date.now() + maxDurationMs;
  let failures = 0;
  for (;;) {
    const res = await getRun(runId, signal);
    if (res.ok) {
      failures = 0;
      onUpdate(res.value);
      if (isTerminal(res.value.state)) return res;
    } else {
      const fatal = res.error.kind === 'aborted' || res.error.kind === 'contract' || res.error.status === 404 ||
        res.error.status === 401 || res.error.status === 403;
      failures += 1;
      if (fatal || failures >= maxConsecutiveErrors) return res;
    }
    if (Date.now() >= deadline) {
      return {
        ok: false,
        error: { kind: 'timeout', message: `Run ${runId} did not finish within ${Math.round(maxDurationMs / 60000)} min. It may still be running on the backend.` },
      };
    }
    await wait(intervalMs, signal);
    if (signal?.aborted) return { ok: false, error: { kind: 'aborted', message: 'Stopped watching the run.' } };
  }
}
