import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { ChevronDown, ChevronRight, Trash2 } from 'lucide-react-native';
import {
  createMonitor,
  deleteMonitor,
  listMonitors,
  Monitor,
  MonitorKind,
  ProductWithSources,
  SourceDescription,
  WebIntelError,
} from '../services/webIntel';
import { Badge, C, formatTime, ui } from './webIntelUi';

export interface WebIntelMonitorsProps {
  products: ProductWithSources[] | null;
  monitorsAvailable: boolean;
  location: string;
  lat: number;
  lon: number;
  state?: string;
  district?: string;
}

type ListState =
  | { status: 'closed' }
  | { status: 'loading' }
  | { status: 'ready'; monitors: Monitor[] }
  | { status: 'error'; error: WebIntelError };

// Search and Research sources have no fixed page to watch, so they cannot back a Page monitor.
const PAGE_ACCESS = new Set(['api', 'rss', 'fetch', 'agent']);

function pageSources(products: ProductWithSources[] | null): SourceDescription[] {
  const byId = new Map<string, SourceDescription>();
  for (const p of products ?? []) for (const s of p.sources) if (PAGE_ACCESS.has(s.access_method)) byId.set(s.id, s);
  return [...byId.values()];
}

export default function WebIntelMonitors(props: WebIntelMonitorsProps) {
  const { products, monitorsAvailable, location, lat, lon, state, district } = props;
  const [list, setList] = useState<ListState>({ status: 'closed' });
  const [kind, setKind] = useState<MonitorKind>('page');
  const [sourceId, setSourceId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  const load = useCallback(async () => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setList({ status: 'loading' });
    const res = await listMonitors(ctrl.signal);
    if (ctrl.signal.aborted) return;
    setList(res.ok ? { status: 'ready', monitors: res.value } : { status: 'error', error: res.error });
  }, []);

  const toggle = () => {
    if (list.status === 'closed') load();
    else {
      abortRef.current?.abort();
      setList({ status: 'closed' });
    }
  };

  const sources = pageSources(products);
  const topicPlace = district || state;
  const canCreate = !busy && (kind === 'page' ? !!sourceId : !!topicPlace);

  const create = async () => {
    setBusy(true);
    setActionError(null);
    const res = await createMonitor({
      kind,
      source_id: kind === 'page' ? sourceId ?? undefined : undefined,
      location,
      lat,
      lon,
      state: state || undefined,
      district: district || undefined,
    });
    setBusy(false);
    if (!res.ok) return setActionError(res.error.message);
    setList((cur) => (cur.status === 'ready' ? { status: 'ready', monitors: [res.value, ...cur.monitors] } : cur));
  };

  const remove = async (id: string) => {
    setBusy(true);
    setActionError(null);
    const res = await deleteMonitor(id);
    setBusy(false);
    if (!res.ok) return setActionError(res.error.message);
    setList((cur) => (cur.status === 'ready' ? { status: 'ready', monitors: cur.monitors.filter((m) => m.monitor_id !== id) } : cur));
  };

  const open = list.status !== 'closed';
  return (
    <View style={styles.box}>
      <TouchableOpacity style={styles.header} onPress={toggle} accessibilityRole="button">
        {open ? <ChevronDown size={16} color={C.ink} /> : <ChevronRight size={16} color={C.ink} />}
        <Text style={styles.title}>Bulletin watchers (TinyFish monitors)</Text>
        <Badge label="F2" tone="blue" />
      </TouchableOpacity>
      {open && (
        <View style={{ marginTop: 8 }}>
          <Text style={ui.small}>
            A monitor re-checks a page or a news topic on a schedule. A confirmed change starts a new evidence run for
            human review. It never sends an alert.
          </Text>
          {!monitorsAvailable && (
            <Text style={[ui.small, { color: C.amber }]}>
              The backend reports monitors as unavailable in its current mode. Creating one will return its reason.
            </Text>
          )}

          {list.status === 'loading' && <ActivityIndicator style={{ marginVertical: 10 }} color={C.green} />}
          {list.status === 'error' && (
            <View style={styles.errorBox}>
              <Text style={styles.errorText}>{list.error.message}</Text>
              <TouchableOpacity onPress={load}>
                <Text style={ui.link}>Retry</Text>
              </TouchableOpacity>
            </View>
          )}
          {list.status === 'ready' && list.monitors.length === 0 && (
            <Text style={[ui.small, { marginVertical: 8 }]}>No monitors yet.</Text>
          )}
          {list.status === 'ready' &&
            list.monitors.map((m) => (
              <View key={m.monitor_id} style={styles.monitorRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.monitorTarget} numberOfLines={2}>
                    {m.kind === 'page' ? 'Page' : 'Topic'}: {m.target}
                  </Text>
                  <Text style={ui.small}>
                    {[m.district, m.state].filter(Boolean).join(', ') || 'No area'} · cron {m.schedule_cron} · created{' '}
                    {formatTime(m.created_at)}
                  </Text>
                  {!m.webhook_configured && (
                    <Text style={[ui.small, { color: C.amber }]}>No webhook configured, so changes are not pushed to Aegis.</Text>
                  )}
                </View>
                <TouchableOpacity disabled={busy} onPress={() => remove(m.monitor_id)} accessibilityLabel="Delete monitor">
                  <Trash2 size={16} color={C.red} />
                </TouchableOpacity>
              </View>
            ))}

          <Text style={ui.sectionTitle}>New monitor</Text>
          <View style={styles.kindRow}>
            {(['page', 'topic'] as const).map((k) => (
              <TouchableOpacity key={k} style={[styles.pill, kind === k && styles.pillActive]} onPress={() => setKind(k)}>
                <Text style={[styles.pillText, kind === k && styles.pillTextActive]}>
                  {k === 'page' ? 'Page monitor' : 'Topic monitor'}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          {kind === 'page' ? (
            sources.length ? (
              <View style={styles.kindRow}>
                {sources.map((s) => (
                  <TouchableOpacity
                    key={s.id}
                    style={[styles.pill, sourceId === s.id && styles.pillActive, !s.verified && { opacity: 0.55 }]}
                    onPress={() => setSourceId(s.id)}
                  >
                    <Text style={[styles.pillText, sourceId === s.id && styles.pillTextActive]}>
                      {s.name}
                      {s.verified ? '' : ' (unverified)'}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            ) : (
              <Text style={ui.small}>Source list unavailable. Load the product catalogue first.</Text>
            )
          ) : (
            <Text style={ui.small}>
              {topicPlace ? `Watches news for “${topicPlace} flood”, at most every 30 minutes.` : 'Needs a district or state for this location.'}
            </Text>
          )}
          <TouchableOpacity style={[styles.createBtn, !canCreate && { opacity: 0.5 }]} disabled={!canCreate} onPress={create}>
            {busy ? <ActivityIndicator color="#fff" size="small" /> : <Text style={styles.createText}>Create monitor</Text>}
          </TouchableOpacity>
          {!!actionError && <Text style={styles.errorText}>{actionError}</Text>}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    borderTopWidth: 1,
    borderTopColor: C.line,
    marginTop: 14,
    paddingTop: 10,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  title: {
    fontSize: 13,
    fontWeight: '800',
    color: C.ink,
    flex: 1,
  },
  monitorRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: C.pageBg,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: C.line,
    padding: 8,
    marginTop: 6,
  },
  monitorTarget: {
    fontSize: 11.5,
    fontWeight: '700',
    color: C.ink,
  },
  kindRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 8,
  },
  pill: {
    backgroundColor: C.greyBg,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: C.line,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  pillActive: {
    backgroundColor: '#1e40af',
    borderColor: '#1e40af',
  },
  pillText: {
    fontSize: 10.5,
    color: C.sub,
    fontWeight: '600',
  },
  pillTextActive: {
    color: '#ffffff',
  },
  createBtn: {
    backgroundColor: '#1e40af',
    borderRadius: 10,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 4,
  },
  createText: {
    color: '#ffffff',
    fontSize: 12,
    fontWeight: '700',
  },
  errorBox: {
    backgroundColor: C.redBg,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: C.redLine,
    padding: 8,
    marginVertical: 8,
    gap: 4,
  },
  errorText: {
    fontSize: 11,
    color: C.red,
    fontWeight: '600',
    marginTop: 4,
  },
});
