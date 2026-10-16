import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import type { FreshnessStatus, HitlEvidence } from '../services/webIntel';
import {
  Badge,
  C,
  ConflictList,
  GRADE,
  MockBadge,
  RUN_STATE,
  SourceLink,
  Tone,
  dataQualityText,
  formatTime,
  plain,
  ui,
} from './webIntelUi';

export interface HitlEvidenceSummaryProps {
  data: HitlEvidence;
  maxItems?: number;
}

const STATUS: Record<FreshnessStatus, { label: string; tone: Tone; text: string }> = {
  ATTACHED: { label: 'ATTACHED', tone: 'green', text: 'Official-source evidence from a recent run is attached.' },
  STALE: { label: 'STALE', tone: 'amber', text: 'The newest evidence for this area is older than the freshness window.' },
  NONE_AVAILABLE: { label: 'NONE AVAILABLE', tone: 'grey', text: 'No web-intelligence run exists for this area yet.' },
};

export default function HitlEvidenceSummary({ data, maxItems = 5 }: HitlEvidenceSummaryProps) {
  const status = STATUS[data.status];
  return (
    <View style={styles.box}>
      <View style={styles.statusRow}>
        <Text style={styles.heading}>Web evidence</Text>
        <Badge label={status.label} tone={status.tone} />
        {data.status !== 'NONE_AVAILABLE' && (
          <Badge label={RUN_STATE[data.run_state].label} tone={RUN_STATE[data.run_state].tone} />
        )}
      </View>
      <Text style={ui.small}>{status.text}</Text>
      {data.status !== 'NONE_AVAILABLE' && (
        <>
          <Text style={ui.small}>Run finished {formatTime(data.finished_at)}</Text>
          {!!data.summary && <Text style={styles.summary}>{plain(data.summary)}</Text>}
        </>
      )}

      {data.evidence.slice(0, maxItems).map((e) => (
        <View key={e.evidence_id} style={styles.line}>
          <View style={ui.badgeRow}>
            <Badge label={GRADE[e.grade].label} tone={GRADE[e.grade].tone} />
            {e.mock && <MockBadge />}
          </View>
          <Text style={styles.claim} numberOfLines={3}>
            {plain(e.claim)}
          </Text>
          <SourceLink name={e.source_name} url={e.source_url} />
        </View>
      ))}
      {data.evidence.length > maxItems && (
        <Text style={ui.small}>+{data.evidence.length - maxItems} more items in the full run.</Text>
      )}

      {data.conflicts.length > 0 && <ConflictList conflicts={data.conflicts} />}
      {data.failed_sources.length > 0 && (
        <Text style={ui.small}>{data.failed_sources.length} source(s) could not be read.</Text>
      )}
      {data.data_quality.map((f) => (
        <Text key={f} style={ui.small}>
          • {dataQualityText(f)}
        </Text>
      ))}
      <Text style={ui.disclaimer}>{data.disclaimer}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    backgroundColor: C.pageBg,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: C.line,
    padding: 10,
    marginTop: 8,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 4,
  },
  heading: {
    fontSize: 11.5,
    fontWeight: '800',
    color: C.ink,
  },
  summary: {
    fontSize: 11,
    color: C.body,
    lineHeight: 15,
    marginVertical: 4,
  },
  line: {
    borderTopWidth: 1,
    borderTopColor: C.line,
    paddingTop: 6,
    marginTop: 6,
  },
  claim: {
    fontSize: 11.5,
    fontWeight: '600',
    color: C.ink,
    lineHeight: 15,
  },
});
