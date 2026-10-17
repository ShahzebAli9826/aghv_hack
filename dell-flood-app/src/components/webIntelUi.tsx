import React from 'react';
import { Linking, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import type {
  CompactEvidence,
  Conflict,
  EvidenceCategory,
  FailedSource,
  FailureReason,
  Freshness,
  Grade,
  Measurement,
  RunState,
  TaskState,
  ValidationStatus,
} from '../services/webIntel';

export const C = {
  pageBg: '#f8fafc',
  card: '#ffffff',
  cardBorder: '#f1f5f9',
  line: '#e2e8f0',
  ink: '#0f172a',
  body: '#334155',
  sub: '#475569',
  muted: '#64748b',
  green: '#059669',
  greenBg: '#ecfdf5',
  greenLine: '#a7f3d0',
  blue: '#1d4ed8',
  blueBg: '#eff6ff',
  blueLine: '#bfdbfe',
  red: '#dc2626',
  redBg: '#fef2f2',
  redLine: '#fca5a5',
  amber: '#b45309',
  amberBg: '#fffbeb',
  amberLine: '#fcd34d',
  grey: '#64748b',
  greyBg: '#f1f5f9',
  mock: '#c2410c',
  console: '#090d16',
} as const;

export type Tone = 'green' | 'blue' | 'red' | 'amber' | 'grey' | 'mock';

const TONES: Record<Tone, { fg: string; bg: string; border: string }> = {
  green: { fg: C.green, bg: C.greenBg, border: C.greenLine },
  blue: { fg: C.blue, bg: C.blueBg, border: C.blueLine },
  red: { fg: C.red, bg: C.redBg, border: C.redLine },
  amber: { fg: C.amber, bg: C.amberBg, border: C.amberLine },
  grey: { fg: C.grey, bg: C.greyBg, border: C.line },
  mock: { fg: '#ffffff', bg: C.mock, border: C.mock },
};

export const GRADE: Record<Grade, { label: string; tone: Tone }> = {
  verified_official: { label: 'Verified official', tone: 'green' },
  credible_secondary: { label: 'Credible secondary', tone: 'blue' },
  unverified: { label: 'Unverified', tone: 'amber' },
  insufficient: { label: 'Insufficient', tone: 'grey' },
};

export const VALIDATION: Record<ValidationStatus, { label: string; tone: Tone }> = {
  verified: { label: 'Validated', tone: 'green' },
  partial: { label: 'Partly validated', tone: 'amber' },
  rejected: { label: 'Rejected by checks', tone: 'red' },
};

export const FRESHNESS: Record<Freshness, { label: string; tone: Tone }> = {
  fresh: { label: 'Fresh', tone: 'green' },
  stale: { label: 'Stale', tone: 'red' },
  unknown: { label: 'Age unknown', tone: 'grey' },
};

export const RUN_STATE: Record<RunState, { label: string; tone: Tone }> = {
  queued: { label: 'Queued', tone: 'grey' },
  running: { label: 'Running', tone: 'blue' },
  succeeded: { label: 'Succeeded', tone: 'green' },
  partial: { label: 'Partial', tone: 'amber' },
  failed: { label: 'Failed', tone: 'red' },
  disabled: { label: 'Disabled', tone: 'grey' },
  cancelled: { label: 'Cancelled', tone: 'grey' },
};

export const TASK_STATE: Record<TaskState, { label: string; tone: Tone }> = {
  queued: { label: 'queued', tone: 'grey' },
  running: { label: 'running', tone: 'blue' },
  succeeded: { label: 'done', tone: 'green' },
  failed: { label: 'failed', tone: 'red' },
  skipped: { label: 'skipped', tone: 'grey' },
  cancelled: { label: 'cancelled', tone: 'grey' },
};

export const FAILURE_TEXT: Record<FailureReason, string> = {
  login_wall: 'Portal requires a login. Aegis does not bypass logins.',
  anti_bot: 'Portal blocked automated access (CAPTCHA or bot wall).',
  timeout: 'Source did not respond in time.',
  goal_failure: 'The browser agent could not complete the lookup.',
  schema_invalid: 'The result did not match the expected structure.',
  stale: 'Latest data is older than the freshness limit for this source.',
  out_of_season: 'Not published outside the 15 Jun–15 Oct season.',
  http_error: 'Source returned an HTTP error.',
  billing: 'TinyFish billing or credit problem.',
  disabled: 'Web intelligence or this source is disabled.',
  budget_exceeded: 'Stopped at the per-request cost limit.',
  unverified_source: 'Source has not been verified for automated use yet.',
  interrupted: 'Run was interrupted by a backend restart.',
};

const DATA_QUALITY_TEXT: Record<string, string> = {
  mock_replay: 'Mock replay: recorded sample data, not a live lookup.',
  tinyfish_disabled: 'TinyFish is disabled on the backend, so no sources were checked.',
  imd_fallback_fetch: 'IMD warnings came from the labelled page fallback, not the IMD API.',
  conflicts_present: 'Sources disagree. See conflicts.',
  rejected_items_present: 'Some items failed validation and are marked rejected.',
};

export function dataQualityText(flag: string): string {
  return DATA_QUALITY_TEXT[flag] ?? flag;
}

export type CategoryGroup =
  | 'river'
  | 'warnings'
  | 'alerts'
  | 'bulletins'
  | 'mobility'
  | 'camps'
  | 'news'
  | 'helplines'
  | 'health_power'
  | 'brief'
  | 'other';

export const CATEGORY_GROUP: Record<EvidenceCategory, CategoryGroup> = {
  river_level: 'river',
  barrage_gate: 'river',
  embankment: 'river',
  official_warning: 'warnings',
  rainfall: 'warnings',
  official_alert: 'alerts',
  bulletin: 'bulletins',
  rail_disruption: 'mobility',
  road_closure: 'mobility',
  relief_camp: 'camps',
  news_report: 'news',
  helpline: 'helplines',
  hospital_capacity: 'health_power',
  power_outage: 'health_power',
  situation_brief: 'brief',
  other: 'other',
};

export const GROUP_ORDER: { id: CategoryGroup; label: string }[] = [
  { id: 'river', label: 'River levels' },
  { id: 'warnings', label: 'Weather warnings' },
  { id: 'alerts', label: 'Official alerts' },
  { id: 'bulletins', label: 'Bulletins' },
  { id: 'mobility', label: 'Rail and road disruptions' },
  { id: 'camps', label: 'Relief camps' },
  { id: 'news', label: 'News reports' },
  { id: 'helplines', label: 'Helplines' },
  { id: 'health_power', label: 'Hospital and power' },
  { id: 'brief', label: 'Situation brief' },
  { id: 'other', label: 'Other' },
];

// The backend html.escape()s page-derived strings for HTML sinks. <Text> never parses markup, so decoding
// these five entities for display cannot inject anything.
export function plain(text: string | null | undefined): string {
  if (!text) return '';
  return text
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#x27;/g, "'")
    .replace(/&amp;/g, '&');
}

export function domainOf(url: string): string | null {
  const m = /^https?:\/\/([^/?#:@\s]+)/i.exec(url);
  return m ? m[1].toLowerCase() : null;
}

export function openExternal(url: string): void {
  if (!/^https?:\/\//i.test(url)) return;
  Linking.openURL(url).catch(() => {});
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return 'not stated';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 'invalid time';
  const stamp = d.toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  return `${stamp} (${formatAge(Date.now() - d.getTime())})`;
}

function formatAge(ms: number): string {
  if (ms < 0) return 'in the future';
  const min = Math.round(ms / 60000);
  if (min < 1) return 'just now';
  if (min < 60) return `${min} min ago`;
  const h = Math.round(min / 60);
  if (h < 48) return `${h} h ago`;
  return `${Math.round(h / 24)} d ago`;
}

export function Badge({ label, tone, loud }: { label: string; tone: Tone; loud?: boolean }) {
  const t = TONES[tone];
  return (
    <View style={[ui.badge, { backgroundColor: t.bg, borderColor: t.border }, loud && ui.badgeLoud]}>
      <Text style={[ui.badgeText, { color: t.fg }, loud && ui.badgeTextLoud]}>{label}</Text>
    </View>
  );
}

export function MockBadge() {
  return <Badge label="MOCK" tone="mock" />;
}

function fmtLevel(v: number | null, unit: string): string | null {
  return v === null ? null : `${v} ${unit}`;
}

export function MeasurementRow({ m }: { m: Measurement }) {
  const over = m.danger_level !== null && m.value >= m.danger_level ? 'danger' :
    m.warning_level !== null && m.value >= m.warning_level ? 'warning' : null;
  const refs = [
    fmtLevel(m.warning_level, m.unit) && `warning ${fmtLevel(m.warning_level, m.unit)}`,
    fmtLevel(m.danger_level, m.unit) && `danger ${fmtLevel(m.danger_level, m.unit)}`,
    fmtLevel(m.hfl, m.unit) && `HFL ${fmtLevel(m.hfl, m.unit)}`,
  ].filter(Boolean);
  const where = [m.station, m.river].filter(Boolean).map((s) => plain(s)).join(', ');
  return (
    <View style={ui.measureRow}>
      <Text style={ui.measureValue}>
        {m.value} {m.unit}
      </Text>
      <View style={{ flex: 1 }}>
        {!!where && <Text style={ui.small}>{where}</Text>}
        <Text style={ui.small}>{refs.length ? `vs ${refs.join(' · ')}` : 'No warning or danger level published'}</Text>
      </View>
      {m.trend && <Badge label={m.trend} tone={m.trend === 'rising' ? 'red' : 'grey'} />}
      {over && <Badge label={over === 'danger' ? 'Above danger' : 'Above warning'} tone={over === 'danger' ? 'red' : 'amber'} />}
    </View>
  );
}

export function SourceLink({ name, url }: { name: string; url: string }) {
  const domain = domainOf(url);
  return (
    <TouchableOpacity disabled={!domain} onPress={() => openExternal(url)} accessibilityRole="link">
      <Text style={ui.sourceLine} numberOfLines={1}>
        {plain(name)}
        {domain ? <Text style={ui.link}>{`  ${domain} ↗`}</Text> : <Text style={ui.small}>  (no link)</Text>}
      </Text>
    </TouchableOpacity>
  );
}

type CardEvidence = CompactEvidence & { excerpt?: string | null; notes?: string[] };

export function EvidenceCard({ e }: { e: CardEvidence }) {
  const grade = GRADE[e.grade];
  const fresh = FRESHNESS[e.freshness];
  const valid = VALIDATION[e.validation_status];
  const issued = e.observed_at ? `Observed ${formatTime(e.observed_at)}` : `Published ${formatTime(e.published_at)}`;
  return (
    <View style={[ui.evCard, e.validation_status === 'rejected' && ui.evCardRejected]}>
      <View style={ui.badgeRow}>
        <Badge label={grade.label} tone={grade.tone} />
        <Badge label={valid.label} tone={valid.tone} />
        <Badge label={fresh.label} tone={fresh.tone} />
        {e.mock && <MockBadge />}
      </View>
      <Text style={ui.claim}>{plain(e.claim)}</Text>
      {e.measurement && <MeasurementRow m={e.measurement} />}
      <SourceLink name={e.source_name} url={e.source_url} />
      <Text style={ui.small}>
        {issued} · Retrieved {formatTime(e.retrieved_at)}
      </Text>
      <Text style={ui.small}>
        Location match: {e.location_match} · Quality score {e.quality_score.toFixed(2)}
      </Text>
      {!!e.excerpt && <Text style={ui.excerpt}>“{plain(e.excerpt)}”</Text>}
      {e.notes?.map((n, i) => (
        <Text key={i} style={ui.small}>
          • {plain(n)}
        </Text>
      ))}
    </View>
  );
}

export function ConflictList({ conflicts }: { conflicts: Conflict[] }) {
  if (!conflicts.length) return <Text style={ui.small}>No conflicts between sources were detected.</Text>;
  return (
    <>
      {conflicts.map((c, i) => (
        <View key={`${c.key}-${i}`} style={ui.conflict}>
          <Text style={ui.conflictTitle}>
            {c.kind === 'value_disagreement' ? 'Values disagree' : 'Official vs secondary'}: {plain(c.key)}
          </Text>
          <Text style={ui.small}>{plain(c.detail)}</Text>
        </View>
      ))}
    </>
  );
}

export function FailedSourceList({ failed, nameOf }: { failed: FailedSource[]; nameOf?: (sourceId: string) => string }) {
  if (!failed.length) return null;
  return (
    <>
      {failed.map((f, i) => (
        <View key={`${f.source_id}-${i}`} style={ui.failedRow}>
          <Text style={ui.failedName}>{nameOf ? nameOf(f.source_id) : f.source_id}</Text>
          <Text style={ui.small}>{FAILURE_TEXT[f.reason]}</Text>
          {!!f.detail && <Text style={ui.small}>{plain(f.detail)}</Text>}
          {f.retry_after_s !== null && <Text style={ui.small}>Retry after {Math.round(f.retry_after_s)} s.</Text>}
        </View>
      ))}
    </>
  );
}

export const ui = StyleSheet.create({
  badge: {
    borderRadius: 8,
    borderWidth: 1,
    paddingHorizontal: 6,
    paddingVertical: 2,
    alignSelf: 'flex-start',
  },
  badgeLoud: {
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  badgeText: {
    fontSize: 9.5,
    fontWeight: '700',
  },
  badgeTextLoud: {
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 0.6,
  },
  badgeRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 4,
    marginBottom: 6,
  },
  small: {
    fontSize: 10.5,
    color: C.muted,
    lineHeight: 15,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '800',
    color: C.ink,
    marginTop: 14,
    marginBottom: 8,
  },
  evCard: {
    backgroundColor: C.pageBg,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.line,
    padding: 10,
    marginBottom: 8,
  },
  evCardRejected: {
    opacity: 0.65,
    borderColor: C.redLine,
  },
  claim: {
    fontSize: 12.5,
    fontWeight: '600',
    color: C.ink,
    lineHeight: 17,
    marginBottom: 4,
  },
  measureRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 8,
    backgroundColor: C.card,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: C.line,
    padding: 8,
    marginVertical: 4,
  },
  measureValue: {
    fontSize: 15,
    fontWeight: '800',
    color: C.ink,
  },
  sourceLine: {
    fontSize: 11,
    fontWeight: '700',
    color: C.sub,
    marginTop: 2,
  },
  link: {
    color: C.blue,
    fontWeight: '600',
    textDecorationLine: 'underline',
  },
  excerpt: {
    fontSize: 10.5,
    color: C.sub,
    fontStyle: 'italic',
    lineHeight: 15,
    marginTop: 4,
  },
  conflict: {
    backgroundColor: C.amberBg,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: C.amberLine,
    padding: 8,
    marginBottom: 6,
  },
  conflictTitle: {
    fontSize: 11,
    fontWeight: '700',
    color: C.amber,
    marginBottom: 2,
  },
  failedRow: {
    borderLeftWidth: 3,
    borderLeftColor: C.redLine,
    paddingLeft: 8,
    marginBottom: 8,
  },
  failedName: {
    fontSize: 11,
    fontWeight: '700',
    color: C.ink,
  },
  disclaimer: {
    fontSize: 10.5,
    color: C.sub,
    fontWeight: '600',
    lineHeight: 15,
    backgroundColor: C.greyBg,
    borderRadius: 8,
    padding: 8,
    marginTop: 10,
  },
});
