import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  StyleSheet,
  Switch,
  Text,
  TouchableOpacity,
  useWindowDimensions,
  View,
} from 'react-native';
import { Check, Globe, Play, Square } from 'lucide-react-native';
import {
  cancelRun,
  Evidence,
  getConfig,
  getLatest,
  getProducts,
  isTerminal,
  LatestResponse,
  pollRun,
  ProductDescription,
  ProductId,
  ProductWithSources,
  RunMode,
  startRun,
  WebIntelConfig,
  WebIntelError,
  WebIntelRun,
} from '../services/webIntel';
import LiveBrowserView from './LiveBrowserView';
import WebIntelMonitors from './WebIntelMonitors';
import {
  Badge,
  C,
  CATEGORY_GROUP,
  CategoryGroup,
  ConflictList,
  dataQualityText,
  EvidenceCard,
  FailedSourceList,
  formatTime,
  GROUP_ORDER,
  MockBadge,
  plain,
  RUN_STATE,
  SourceLink,
  TASK_STATE,
  Tone,
  ui,
} from './webIntelUi';

export interface AegisSummary {
  severity?: string;
  area_sq_km?: number | null;
  gauge_status?: string;
  input_provenance?: string;
  depth_provenance?: string;
}

export interface WebIntelPanelProps {
  location: string;
  lat: number;
  lon: number;
  state?: string;
  district?: string;
  aegisSummary?: AegisSummary;
}

type Load<T> = { status: 'loading' } | { status: 'ready'; value: T } | { status: 'error'; error: WebIntelError };

type RunPhase =
  | { phase: 'idle' }
  | { phase: 'starting' }
  | { phase: 'rejected'; error: WebIntelError }
  | { phase: 'watching'; runId: string; run: WebIntelRun | null; cancelling: boolean; cancelError: string | null }
  | { phase: 'finished'; run: WebIntelRun }
  | { phase: 'lost'; runId: string; run: WebIntelRun | null; error: WebIntelError };

const MODE_BADGE: Record<RunMode, { label: string; tone: Tone; loud?: boolean }> = {
  live: { label: 'LIVE', tone: 'green' },
  replay: { label: 'MOCK REPLAY', tone: 'mock', loud: true },
  disabled: { label: 'DISABLED', tone: 'grey' },
};

const DISABLED_EXPLANATION =
  'The backend has TinyFish turned off. It runs only with TINYFISH_MODE=live and a TINYFISH_API_KEY, or ' +
  'TINYFISH_MODE=replay for recorded demo data. Ask an administrator to enable it. Stored runs, if any, are still shown below.';

const FLAGGED_PROVENANCE = new Set(['synthetic_input', 'heuristic']);

function shownRun(phase: RunPhase): WebIntelRun | null {
  return 'run' in phase ? phase.run : null;
}

function groupEvidence(evidence: Evidence[]): { id: CategoryGroup; label: string; items: Evidence[] }[] {
  const buckets = new Map<CategoryGroup, Evidence[]>();
  for (const e of evidence) {
    const g = CATEGORY_GROUP[e.category];
    buckets.set(g, [...(buckets.get(g) ?? []), e]);
  }
  return GROUP_ORDER.filter((g) => buckets.has(g.id)).map((g) => ({ ...g, items: buckets.get(g.id)! }));
}

function liveSourceLabel(run: WebIntelRun, nameOf: (id: string) => string): string {
  const rid = run.live_view?.tinyfish_run_id;
  const exact = rid ? run.source_tasks.find((t) => t.tinyfish_run_id === rid) : undefined;
  if (exact) return nameOf(exact.source_id);
  const agents = run.source_tasks.filter((t) => t.state === 'running' && t.access_method === 'agent');
  return agents.length ? agents.map((t) => nameOf(t.source_id)).join(', ') : 'TinyFish agent';
}

export default function WebIntelPanel({ location, lat, lon, state, district, aegisSummary }: WebIntelPanelProps) {
  const { width } = useWindowDimensions();
  const stacked = width < 760;

  const [config, setConfig] = useState<Load<WebIntelConfig>>({ status: 'loading' });
  const [catalogue, setCatalogue] = useState<Load<ProductWithSources[]>>({ status: 'loading' });
  const [latest, setLatest] = useState<Load<LatestResponse>>({ status: 'loading' });
  const [selected, setSelected] = useState<Set<ProductId>>(new Set());
  const [stream, setStream] = useState(false);
  const [phase, setPhase] = useState<RunPhase>({ phase: 'idle' });
  const watchRef = useRef<AbortController | null>(null);

  const loadMeta = useCallback(async (signal: AbortSignal) => {
    setConfig({ status: 'loading' });
    setCatalogue({ status: 'loading' });
    const [cfg, prods] = await Promise.all([getConfig(signal), getProducts(signal)]);
    if (signal.aborted) return;
    setConfig(cfg.ok ? { status: 'ready', value: cfg.value } : { status: 'error', error: cfg.error });
    setCatalogue(prods.ok ? { status: 'ready', value: prods.value } : { status: 'error', error: prods.error });
    if (cfg.ok) setSelected(new Set(cfg.value.default_products));
  }, []);

  const [metaNonce, setMetaNonce] = useState(0);
  useEffect(() => {
    const ctrl = new AbortController();
    loadMeta(ctrl.signal);
    return () => ctrl.abort();
  }, [loadMeta, metaNonce]);

  useEffect(() => {
    const ctrl = new AbortController();
    setLatest({ status: 'loading' });
    getLatest({ lat, lon, district: district || undefined, state: state || undefined }, ctrl.signal).then((res) => {
      if (ctrl.signal.aborted) return;
      setLatest(res.ok ? { status: 'ready', value: res.value } : { status: 'error', error: res.error });
    });
    watchRef.current?.abort();
    setPhase({ phase: 'idle' });
    return () => ctrl.abort();
  }, [location, lat, lon, state, district]);

  useEffect(() => () => watchRef.current?.abort(), []);

  const watch = useCallback(async (runId: string, initial: WebIntelRun | null) => {
    watchRef.current?.abort();
    const ctrl = new AbortController();
    watchRef.current = ctrl;
    setPhase({ phase: 'watching', runId, run: initial, cancelling: false, cancelError: null });
    const res = await pollRun(
      runId,
      (run) => setPhase((p) => (p.phase === 'watching' && p.runId === runId ? { ...p, run } : p)),
      { signal: ctrl.signal },
    );
    if (ctrl.signal.aborted) return;
    if (res.ok) setPhase({ phase: 'finished', run: res.value });
    else setPhase((p) => ({ phase: 'lost', runId, run: shownRun(p), error: res.error }));
  }, []);

  const run = async () => {
    setPhase({ phase: 'starting' });
    const res = await startRun({
      location,
      lat,
      lon,
      state: state || undefined,
      district: district || undefined,
      products: [...selected],
      stream,
    });
    if (!res.ok) return setPhase({ phase: 'rejected', error: res.error });
    watch(res.value.run_id, null);
  };

  const cancel = async () => {
    if (phase.phase !== 'watching') return;
    const runId = phase.runId;
    setPhase((p) => (p.phase === 'watching' ? { ...p, cancelling: true, cancelError: null } : p));
    const res = await cancelRun(runId);
    if (!res.ok) {
      setPhase((p) => (p.phase === 'watching' && p.runId === runId ? { ...p, cancelling: false, cancelError: res.error.message } : p));
    }
  };

  const nameOf = useMemo(() => {
    const names = new Map<string, string>();
    if (catalogue.status === 'ready') for (const p of catalogue.value) for (const s of p.sources) names.set(s.id, s.name);
    return (id: string) => names.get(id) ?? id;
  }, [catalogue]);

  const current = shownRun(phase);
  const stored = latest.status === 'ready' && latest.value.status !== 'NONE_AVAILABLE' ? latest.value : null;
  const display = current ?? stored?.run ?? null;
  const busy = phase.phase === 'starting' || phase.phase === 'watching';

  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <Globe size={18} color={C.green} />
        <Text style={styles.headerTitle}>Live Web Intelligence (TinyFish)</Text>
        {config.status === 'ready' && <Badge {...MODE_BADGE[config.value.mode]} />}
      </View>

      {config.status === 'loading' && (
        <View style={styles.centerRow}>
          <ActivityIndicator color={C.green} />
          <Text style={ui.small}>Loading web-intelligence configuration…</Text>
        </View>
      )}
      {config.status === 'error' && (
        <ErrorBox
          title={config.error.kind === 'http' ? 'Web intelligence is unavailable' : 'Web intelligence is unreachable'}
          error={config.error}
          onRetry={() => setMetaNonce((n) => n + 1)}
        />
      )}

      {config.status === 'ready' && config.value.mode === 'replay' && (
        <View style={styles.mockBanner}>
          <Text style={styles.mockBannerText}>
            MOCK REPLAY: results are recorded sample data, not a live lookup. Do not act on them.
          </Text>
        </View>
      )}
      {config.status === 'ready' && !config.value.enabled && <Text style={styles.disabledText}>{DISABLED_EXPLANATION}</Text>}

      {config.status === 'ready' && config.value.enabled && (
        <>
          <ProductPicker
            products={config.value.products}
            catalogue={catalogue}
            selected={selected}
            disabled={busy}
            onToggle={(id) =>
              setSelected((cur) => {
                const next = new Set(cur);
                if (next.has(id)) next.delete(id);
                else next.add(id);
                return next;
              })
            }
          />
          <View style={styles.streamRow}>
            <Switch value={stream} onValueChange={setStream} disabled={busy} />
            <Text style={styles.streamText}>Show live browser (streams the TinyFish browser while agent sources run)</Text>
          </View>
          <View style={styles.actionRow}>
            <TouchableOpacity
              style={[styles.runBtn, (busy || selected.size === 0) && styles.btnDisabled]}
              disabled={busy || selected.size === 0}
              onPress={run}
              accessibilityRole="button"
            >
              {phase.phase === 'starting' ? <ActivityIndicator color="#fff" size="small" /> : <Play size={14} color="#fff" />}
              <Text style={styles.runText}>Run Live Web Intelligence</Text>
            </TouchableOpacity>
            {phase.phase === 'watching' && (
              <TouchableOpacity
                style={[styles.cancelBtn, phase.cancelling && styles.btnDisabled]}
                disabled={phase.cancelling}
                onPress={cancel}
                accessibilityRole="button"
              >
                <Square size={12} color={C.red} />
                <Text style={styles.cancelText}>{phase.cancelling ? 'Cancelling…' : 'Cancel'}</Text>
              </TouchableOpacity>
            )}
          </View>
          {phase.phase === 'watching' && !!phase.cancelError && (
            <Text style={styles.errorText}>Cancel failed: {phase.cancelError}</Text>
          )}
          {selected.size === 0 && <Text style={ui.small}>Select at least one product.</Text>}
          <Text style={ui.small}>
            Cost limit per request: ${config.value.limits.max_usd_per_request.toFixed(2)} · up to{' '}
            {config.value.limits.max_steps_per_run} browser steps per source.
          </Text>
        </>
      )}

      {phase.phase === 'rejected' && <ErrorBox title="Run was not started" error={phase.error} />}
      {phase.phase === 'watching' && !phase.run && (
        <View style={styles.centerRow}>
          <ActivityIndicator color={C.blue} />
          <Text style={ui.small}>Run {phase.runId} accepted. Waiting for its first status…</Text>
        </View>
      )}
      {phase.phase === 'lost' && (
        <ErrorBox
          title={phase.error.kind === 'timeout' ? 'Stopped waiting for the run' : 'Lost contact with the run'}
          error={phase.error}
          retryLabel="Check again"
          onRetry={() => watch(phase.runId, phase.run)}
        />
      )}

      {!current && latest.status === 'loading' && (
        <View style={styles.centerRow}>
          <ActivityIndicator color={C.green} />
          <Text style={ui.small}>Looking for stored evidence for this area…</Text>
        </View>
      )}
      {!current && latest.status === 'error' && <ErrorBox title="Could not load stored evidence" error={latest.error} />}
      {!current && latest.status === 'ready' && latest.value.status === 'NONE_AVAILABLE' && (
        <Text style={styles.emptyText}>No web-intelligence run exists for {location} yet.</Text>
      )}
      {!current && stored && (
        <View style={styles.storedRow}>
          <Badge label={stored.status} tone={stored.status === 'ATTACHED' ? 'green' : 'amber'} />
          <Text style={ui.small}>
            Showing the stored run from {formatTime(stored.run.finished_at ?? stored.run.created_at)}
            {stored.status === 'STALE' ? '. It is older than the freshness window.' : '.'}
          </Text>
        </View>
      )}

      {display && <RunView run={display} nameOf={nameOf} stacked={stacked} aegisSummary={aegisSummary} />}

      {config.status === 'ready' && (
        <WebIntelMonitors
          products={catalogue.status === 'ready' ? catalogue.value : null}
          monitorsAvailable={config.value.monitors_available}
          location={location}
          lat={lat}
          lon={lon}
          state={state}
          district={district}
        />
      )}

      {config.status === 'ready' && !display && <Text style={ui.disclaimer}>{config.value.disclaimer}</Text>}
    </View>
  );
}

function ErrorBox({ title, error, onRetry, retryLabel = 'Retry' }: {
  title: string;
  error: WebIntelError;
  onRetry?: () => void;
  retryLabel?: string;
}) {
  return (
    <View style={styles.errorBox}>
      <Text style={styles.errorTitle}>{title}</Text>
      <Text style={styles.errorText}>{error.message}</Text>
      {onRetry && (
        <TouchableOpacity onPress={onRetry} accessibilityRole="button">
          <Text style={ui.link}>{retryLabel}</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

function ProductPicker({ products, catalogue, selected, disabled, onToggle }: {
  products: ProductDescription[];
  catalogue: Load<ProductWithSources[]>;
  selected: Set<ProductId>;
  disabled: boolean;
  onToggle: (id: ProductId) => void;
}) {
  const sourcesOf = (id: ProductId) =>
    catalogue.status === 'ready' ? catalogue.value.find((p) => p.id === id)?.sources ?? [] : [];
  const groups = [
    { label: 'Core', items: products.filter((p) => p.default) },
    { label: 'Extra features', items: products.filter((p) => !p.default) },
  ];
  return (
    <View>
      {catalogue.status === 'error' && (
        <Text style={[ui.small, { color: C.amber }]}>Source status unavailable: {catalogue.error.message}</Text>
      )}
      {groups.map((g) => (
        <View key={g.label}>
          <Text style={ui.sectionTitle}>{g.label}</Text>
          {g.items.map((p) => {
            const on = selected.has(p.id);
            return (
              <TouchableOpacity
                key={p.id}
                style={styles.productRow}
                disabled={disabled}
                onPress={() => onToggle(p.id)}
                accessibilityRole="checkbox"
                accessibilityState={{ checked: on, disabled }}
              >
                <View style={[styles.checkbox, on && styles.checkboxOn]}>{on && <Check size={12} color="#fff" />}</View>
                <View style={{ flex: 1 }}>
                  <View style={styles.productTitleRow}>
                    <Text style={styles.productTitle}>{p.title}</Text>
                    {p.feature !== 'core' && <Badge label={p.feature} tone="blue" />}
                  </View>
                  <Text style={ui.small}>{p.description}</Text>
                  <View style={styles.sourceChips}>
                    {sourcesOf(p.id).map((s) => {
                      const reason = !s.verified ? 'unverified' : !s.in_season ? 'out of season' : null;
                      return (
                        <Text key={s.id} style={[styles.sourceChip, reason !== null && styles.sourceChipOff]}>
                          {s.name}
                          {reason ? ` · ${reason}` : ''}
                        </Text>
                      );
                    })}
                  </View>
                </View>
              </TouchableOpacity>
            );
          })}
        </View>
      ))}
    </View>
  );
}

function RunView({ run, nameOf, stacked, aegisSummary }: {
  run: WebIntelRun;
  nameOf: (id: string) => string;
  stacked: boolean;
  aegisSummary?: AegisSummary;
}) {
  const state = RUN_STATE[run.state];
  const groups = groupEvidence(run.evidence);
  const official = run.evidence.filter((e) => e.grade === 'verified_official' && e.validation_status !== 'rejected');
  const meta = run.agent_metadata;
  return (
    <View style={{ marginTop: 12 }}>
      <View style={styles.statusRow}>
        <Badge label={state.label} tone={state.tone} />
        {run.mode === 'replay' && <MockBadge />}
        <Text style={ui.small}>
          Run {run.run_id} · {run.sources_succeeded} of {run.sources_checked} sources succeeded, {run.sources_failed} failed
        </Text>
        {!isTerminal(run.state) && <ActivityIndicator size="small" color={C.blue} />}
      </View>
      {run.source_tasks.length > 0 && (
        <View style={styles.taskList}>
          {run.source_tasks.map((t) => (
            <View key={`${t.product_id}-${t.source_id}`} style={styles.taskRow}>
              <Text style={styles.taskName} numberOfLines={1}>
                {nameOf(t.source_id)}
              </Text>
              <Text style={ui.small}>{t.access_method}</Text>
              <Badge label={TASK_STATE[t.state].label} tone={TASK_STATE[t.state].tone} />
              <Text style={ui.small}>{t.evidence_count} items</Text>
            </View>
          ))}
        </View>
      )}
      {!!run.error && <Text style={styles.errorText}>{run.error}</Text>}

      <LiveBrowserView liveView={run.live_view} runState={run.state} sourceLabel={liveSourceLabel(run, nameOf)} />

      <View style={[styles.columns, stacked && styles.columnsStacked]}>
        <View style={[styles.column, !stacked && styles.columnWide]}>
          <Text style={styles.columnTitle}>Aegis measured</Text>
          <AegisColumn summary={aegisSummary} />
        </View>
        <View style={[styles.column, !stacked && styles.columnWide]}>
          <Text style={styles.columnTitle}>Official sources say</Text>
          {official.length === 0 ? (
            <Text style={ui.small}>No verified official evidence in this run.</Text>
          ) : (
            official.map((e) => (
              <View key={e.evidence_id} style={{ marginBottom: 8 }}>
                <Text style={styles.columnClaim}>{plain(e.claim)}</Text>
                <SourceLink name={e.source_name} url={e.source_url} />
              </View>
            ))
          )}
        </View>
        <View style={[styles.column, !stacked && styles.columnWide]}>
          <Text style={styles.columnTitle}>Combined — for human review</Text>
          {run.human_review_required && <Badge label="Human review required" tone="red" />}
          {!!run.summary && <Text style={[styles.columnClaim, { marginTop: 6 }]}>{plain(run.summary)}</Text>}
          <View style={{ marginTop: 6 }}>
            <ConflictList conflicts={run.conflicts} />
          </View>
        </View>
      </View>

      {groups.length === 0 && isTerminal(run.state) && (
        <Text style={styles.emptyText}>This run returned no evidence items.</Text>
      )}
      {groups.map((g) => (
        <View key={g.id}>
          <Text style={ui.sectionTitle}>
            {g.label} ({g.items.length})
          </Text>
          {g.items.map((e) => (
            <EvidenceCard key={e.evidence_id} e={e} />
          ))}
        </View>
      ))}

      {run.failed_sources.length > 0 && (
        <>
          <Text style={ui.sectionTitle}>Sources that could not be read ({run.failed_sources.length})</Text>
          <FailedSourceList failed={run.failed_sources} nameOf={nameOf} />
        </>
      )}
      {run.data_quality.length > 0 && (
        <>
          <Text style={ui.sectionTitle}>Data quality</Text>
          {run.data_quality.map((f) => (
            <Text key={f} style={ui.small}>
              • {dataQualityText(f)}
            </Text>
          ))}
        </>
      )}
      <Text style={ui.sectionTitle}>Cost</Text>
      <Text style={ui.small}>
        {meta.estimated_cost_usd === null ? 'Estimated cost not reported' : `Estimated $${meta.estimated_cost_usd.toFixed(3)}`}
        {meta.budget_usd !== null ? ` of $${meta.budget_usd.toFixed(2)} budget` : ''}
        {meta.num_of_steps !== null ? ` · ${meta.num_of_steps} browser steps` : ''}
        {meta.tinyfish_run_ids.length ? ` · ${meta.tinyfish_run_ids.length} TinyFish runs` : ''}
      </Text>
      <Text style={[ui.small, { marginTop: 6 }]}>{run.quality_score_note}</Text>
      <Text style={ui.disclaimer}>{run.disclaimer}</Text>
    </View>
  );
}

function AegisColumn({ summary }: { summary?: AegisSummary }) {
  if (!summary) return <Text style={ui.small}>No Aegis cycle result for this location yet.</Text>;
  const rows: [string, string | undefined][] = [
    ['Severity', summary.severity],
    ['Flooded area', summary.area_sq_km == null ? undefined : `${summary.area_sq_km.toFixed(2)} km²`],
    ['Gauge status', summary.gauge_status],
  ];
  return (
    <View>
      {rows.map(([k, v]) => (
        <Text key={k} style={styles.columnClaim}>
          {k}: <Text style={{ fontWeight: '800' }}>{v ?? 'not reported'}</Text>
        </Text>
      ))}
      <View style={[ui.badgeRow, { marginTop: 6 }]}>
        {(
          [
            ['input', summary.input_provenance],
            ['depth', summary.depth_provenance],
          ] as const
        ).map(([k, v]) =>
          v ? <Badge key={k} label={`${k}: ${v}`} tone={FLAGGED_PROVENANCE.has(v) ? 'amber' : 'grey'} /> : null,
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: C.card,
    borderRadius: 22,
    padding: 16,
    borderWidth: 1,
    borderColor: C.cardBorder,
    marginBottom: 16,
    shadowColor: C.ink,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 10,
  },
  headerTitle: {
    color: C.ink,
    fontSize: 15,
    fontWeight: '700',
    flex: 1,
  },
  centerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginVertical: 10,
  },
  mockBanner: {
    backgroundColor: C.mock,
    borderRadius: 10,
    padding: 10,
    marginBottom: 8,
  },
  mockBannerText: {
    color: '#ffffff',
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 0.3,
  },
  disabledText: {
    fontSize: 11.5,
    color: C.sub,
    lineHeight: 16,
    backgroundColor: C.greyBg,
    borderRadius: 10,
    padding: 10,
  },
  productRow: {
    flexDirection: 'row',
    gap: 10,
    paddingVertical: 6,
  },
  checkbox: {
    width: 18,
    height: 18,
    borderRadius: 5,
    borderWidth: 1.5,
    borderColor: '#94a3b8',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 1,
  },
  checkboxOn: {
    backgroundColor: C.green,
    borderColor: C.green,
  },
  productTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  productTitle: {
    fontSize: 12.5,
    fontWeight: '700',
    color: C.ink,
  },
  sourceChips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 4,
    marginTop: 4,
  },
  sourceChip: {
    fontSize: 9.5,
    color: C.sub,
    backgroundColor: C.greyBg,
    borderRadius: 6,
    paddingHorizontal: 6,
    paddingVertical: 2,
    overflow: 'hidden',
  },
  sourceChipOff: {
    color: '#94a3b8',
    textDecorationLine: 'line-through',
  },
  streamRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 12,
  },
  streamText: {
    fontSize: 11,
    color: C.sub,
    flex: 1,
  },
  actionRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 12,
    marginBottom: 6,
  },
  runBtn: {
    backgroundColor: C.green,
    borderRadius: 14,
    height: 46,
    paddingHorizontal: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    shadowColor: C.green,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 2,
  },
  runText: {
    color: '#ffffff',
    fontSize: 13,
    fontWeight: '700',
  },
  btnDisabled: {
    opacity: 0.6,
  },
  cancelBtn: {
    borderRadius: 14,
    height: 46,
    paddingHorizontal: 14,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    borderWidth: 1.5,
    borderColor: C.redLine,
    backgroundColor: C.redBg,
  },
  cancelText: {
    color: C.red,
    fontSize: 13,
    fontWeight: '700',
  },
  errorBox: {
    backgroundColor: C.redBg,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: C.redLine,
    padding: 10,
    marginVertical: 8,
    gap: 4,
  },
  errorTitle: {
    fontSize: 12,
    fontWeight: '800',
    color: C.red,
  },
  errorText: {
    fontSize: 11,
    color: C.red,
    lineHeight: 15,
  },
  emptyText: {
    fontSize: 11.5,
    color: C.muted,
    marginVertical: 10,
  },
  storedRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 6,
    marginTop: 10,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 6,
  },
  taskList: {
    marginTop: 8,
    backgroundColor: C.pageBg,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: C.line,
    padding: 8,
    gap: 4,
  },
  taskRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  taskName: {
    fontSize: 11,
    fontWeight: '700',
    color: C.ink,
    flex: 1,
  },
  columns: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 12,
  },
  columnsStacked: {
    flexDirection: 'column',
  },
  column: {
    backgroundColor: C.pageBg,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.line,
    padding: 10,
  },
  columnWide: {
    flex: 1,
  },
  columnTitle: {
    fontSize: 12,
    fontWeight: '800',
    color: C.ink,
    marginBottom: 6,
  },
  columnClaim: {
    fontSize: 11.5,
    color: C.body,
    lineHeight: 16,
  },
});
