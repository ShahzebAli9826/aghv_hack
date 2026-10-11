import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Modal,
  TextInput,
  Platform,
  Alert,
} from 'react-native';
import {
  ShieldAlert,
  Users,
  Home,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Sliders,
  FileSpreadsheet,
  Activity,
  ChevronRight,
  PlusCircle,
  XCircle,
  Zap,
} from 'lucide-react-native';
import { apiService } from '../services/api';

interface ClusterProfile {
  cluster_id: string;
  county_name: string;
  population: number;
  exposure: number;
  twi_risk_tier: string;
  elevation_safety: number;
  priority_score: number;
  rank: number;
  assigned_shelters: Array<{
    shelter_name: string;
    allocated_population: number;
    shelter_type: string;
    status: string;
  }>;
  unallocated_population: number;
}

interface ShelterProfile {
  shelter_id: string;
  name: string;
  county: string;
  capacity: number;
  remaining_capacity: number;
  shelter_type: string;
  status: string;
}

export const TriagePanel: React.FC = () => {
  const [threadId, setThreadId] = useState<string>('');
  const [clusters, setClusters] = useState<ClusterProfile[]>([]);
  const [shelters, setShelters] = useState<ShelterProfile[]>([]);
  const [unallocatedTotal, setUnallocatedTotal] = useState<number>(0);
  const [auditLogs, setAuditLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState<boolean>(false);

  // Override Modal States
  const [modalVisible, setModalVisible] = useState<boolean>(false);
  const [overrideAction, setOverrideAction] = useState<'SHELTER_FULL' | 'ROAD_CLOSED' | 'FORCE_PRIORITY'>('SHELTER_FULL');
  const [selectedShelterName, setSelectedShelterName] = useState<string>('Athens Community Center');
  const [overrideReason, setOverrideReason] = useState<string>('Operator field telemetry: capacity saturated');

  const fetchTriage = async () => {
    setLoading(true);
    try {
      const res = await apiService.runTriage('Athens County, Ohio');
      if (res && (res.status === 'AWAITING_OPERATOR_REVIEW' || res.status === 'SUCCESS' || res.priority_queue)) {
        setThreadId(res.thread_id || 'thread_athens');
        setClusters(res.priority_queue || []);
        setShelters(res.shelter_allocations || []);
        setUnallocatedTotal(res.unallocated_count || 0);
        setAuditLogs(res.audit_log || []);
      }
    } catch (e: any) {
      console.log('[Triage Fetch Error]', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTriage();
  }, []);

  const handleApplyOverride = async () => {
    if (!threadId) {
      Alert.alert('No Active Thread', 'Please run a triage cycle first.');
      return;
    }

    setLoading(true);
    setModalVisible(false);

    try {
      const overrides = [
        {
          action_type: overrideAction,
          target_id: selectedShelterName,
          reason: overrideReason,
        },
      ];

      const res = await apiService.applyTriageOverride(threadId, overrides);
      if (res && (res.status === 'COMPLETED' || res.priority_queue)) {
        setClusters(res.priority_queue || []);
        setShelters(res.shelter_allocations || []);
        setUnallocatedTotal(res.unallocated_count || 0);
        setAuditLogs(res.audit_log || []);
      }
    } catch (e: any) {
      console.log('[Triage Override Error]', e);
      Alert.alert('Override Error', e?.message || 'Failed to submit override.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <ShieldAlert size={20} color="#2563eb" />
          <View>
            <Text style={styles.headerTitle}>Multi-Criteria Disaster Triage Hub</Text>
            <Text style={styles.headerSubtitle}>
              LangGraph StateGraph   Thread: {threadId || 'Initial'}
            </Text>
          </View>
        </View>

        <TouchableOpacity style={styles.refreshBtn} onPress={fetchTriage} disabled={loading} activeOpacity={0.7}>
          {loading ? (
            <ActivityIndicator size="small" color="#2563eb" />
          ) : (
            <RotateCcw size={15} color="#2563eb" />
          )}
          <Text style={styles.refreshBtnText}>Re-Run Triage</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.kpiContainer}>
        <View style={[styles.kpiCard, { backgroundColor: '#fef2f2', borderColor: '#fee2e2' }]}>
          <Text style={styles.kpiLabel}>Rank #1 County</Text>
          <Text style={[styles.kpiValue, { color: '#dc2626' }]} numberOfLines={1}>
            {clusters[0]?.county_name ? clusters[0].county_name.split(',')[0] : 'Athens County'}
          </Text>
          <Text style={styles.kpiSub}>Score: {clusters[0]?.priority_score ? clusters[0].priority_score.toFixed(1) : '197.3'}</Text>
        </View>

        <View style={[styles.kpiCard, { backgroundColor: '#f0fdf4', borderColor: '#dcfce7' }]}>
          <Text style={styles.kpiLabel}>Monitored Clusters</Text>
          <Text style={[styles.kpiValue, { color: '#16a34a' }]}>{clusters.length || 30}</Text>
          <Text style={styles.kpiSub}>Across 30 Counties</Text>
        </View>

        <View style={[styles.kpiCard, { backgroundColor: '#eff6ff', borderColor: '#dbeafe' }]}>
          <Text style={styles.kpiLabel}>Shelter Network</Text>
          <Text style={[styles.kpiValue, { color: '#2563eb' }]}>{shelters.length || 71}</Text>
          <Text style={styles.kpiSub}>Active Facilities</Text>
        </View>

        <View style={[styles.kpiCard, { backgroundColor: '#f5f3ff', borderColor: '#ede9fe' }]}>
          <Text style={styles.kpiLabel}>Unallocated Pop</Text>
          <Text
            style={[
              styles.kpiValue,
              { color: unallocatedTotal === 0 ? '#7c3aed' : '#dc2626' },
            ]}
          >
            {unallocatedTotal}
          </Text>
          <Text style={styles.kpiSub}>{unallocatedTotal === 0 ? '100% Safe Placement' : 'Overflow Warning'}</Text>
        </View>
      </View>

      <View style={styles.actionBar}>
        <Text style={styles.actionPromptText}>Operator Mid-Run Overrides:</Text>
        <View style={styles.actionButtonsRow}>
          <TouchableOpacity
            style={[styles.actionBtn, { backgroundColor: '#fef2f2', borderColor: '#fee2e2' }]}
            onPress={() => {
              setOverrideAction('SHELTER_FULL');
              setSelectedShelterName('Athens Community Center');
              setModalVisible(true);
            }}
            activeOpacity={0.75}
          >
            <XCircle size={14} color="#dc2626" />
            <Text style={[styles.actionBtnText, { color: '#dc2626' }]}>Mark Shelter Full</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.actionBtn, { backgroundColor: '#fffbeb', borderColor: '#fef3c7' }]}
            onPress={() => {
              setOverrideAction('ROAD_CLOSED');
              setSelectedShelterName('Route Corridor US-33');
              setModalVisible(true);
            }}
            activeOpacity={0.75}
          >
            <AlertTriangle size={14} color="#d97706" />
            <Text style={[styles.actionBtnText, { color: '#d97706' }]}>Close Road Segment</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.actionBtn, { backgroundColor: '#f5f3ff', borderColor: '#ede9fe' }]}
            onPress={() => {
              setOverrideAction('FORCE_PRIORITY');
              setSelectedShelterName('Athens County, Ohio');
              setModalVisible(true);
            }}
            activeOpacity={0.75}
          >
            <Zap size={14} color="#7c3aed" />
            <Text style={[styles.actionBtnText, { color: '#7c3aed' }]}>Force Priority</Text>
          </TouchableOpacity>
        </View>
      </View>

      <ScrollView style={styles.contentScroll} showsVerticalScrollIndicator={false}>
        <Text style={styles.sectionHeading}>Priority Urgency Queue [P × (1+E) / E_safety]</Text>
        <View style={styles.clusterList}>
          {clusters.slice(0, 10).map((c, index) => {
            const isRank1 = c.rank === 1 || index === 0;
            return (
              <View
                key={c.cluster_id || index}
                style={[styles.clusterCard, isRank1 && styles.rank1Card]}
              >
                <View style={styles.clusterHeaderRow}>
                  <View style={[styles.rankBadge, isRank1 && { backgroundColor: '#fee2e2', borderColor: '#fecaca' }]}>
                    <Text style={[styles.rankText, isRank1 && { color: '#dc2626' }]}>#{c.rank || index + 1}</Text>
                  </View>
                  <View style={styles.clusterTitleCol}>
                    <Text style={styles.clusterCountyName}>{c.county_name}</Text>
                    <Text style={styles.clusterMetricsSummary}>
                      Pop: {c.population}   Exposure: {(c.exposure * 100).toFixed(0)}%   Safety: {c.elevation_safety}
                    </Text>
                  </View>
                  <View style={styles.scoreBadge}>
                    <Text style={[styles.scoreVal, isRank1 && { color: '#dc2626' }]}>{c.priority_score.toFixed(1)}</Text>
                    <Text style={styles.scoreLabel}>Priority</Text>
                  </View>
                </View>

                <View style={styles.shelterAssignWrap}>
                  <Text style={styles.assignedTitle}>Allocated Shelters & Placement:</Text>
                  {c.assigned_shelters && c.assigned_shelters.length > 0 ? (
                    c.assigned_shelters.map((as, aIdx) => (
                      <View key={aIdx} style={styles.assignedShelterItem}>
                        <CheckCircle2 size={13} color="#059669" />
                        <Text style={styles.assignedShelterName}>{as.shelter_name}</Text>
                        <Text style={styles.assignedShelterCount}>
                          +{as.allocated_population} citizens
                        </Text>
                      </View>
                    ))
                  ) : (
                    <Text style={styles.noShelterWarning}>Awaiting secondary rerouting</Text>
                  )}
                </View>
              </View>
            );
          })}
        </View>

        {auditLogs && auditLogs.length > 0 && (
          <View style={styles.auditSection}>
            <Text style={styles.sectionHeading}>Operator Audit Log & Course Corrections</Text>
            <View style={styles.auditBox}>
              {auditLogs.map((log, lIdx) => (
                <Text key={lIdx} style={styles.auditLogLine}>
                  {log}
                </Text>
              ))}
            </View>
          </View>
        )}
      </ScrollView>

      <Modal visible={modalVisible} transparent animationType="fade" onRequestClose={() => setModalVisible(false)}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Submit Operator Override</Text>
              <TouchableOpacity onPress={() => setModalVisible(false)}>
                <XCircle size={20} color="#64748b" />
              </TouchableOpacity>
            </View>

            <Text style={styles.inputLabel}>Action Type</Text>
            <View style={styles.actionTypeDisplay}>
              <Text style={styles.actionTypeText}>{overrideAction}</Text>
            </View>

            <Text style={styles.inputLabel}>Target Facility / Location</Text>
            <TextInput
              style={styles.modalInput}
              value={selectedShelterName}
              onChangeText={setSelectedShelterName}
              placeholder="e.g. Athens Community Center"
              placeholderTextColor="#94a3b8"
            />

            <Text style={styles.inputLabel}>Operational Reason</Text>
            <TextInput
              style={[styles.modalInput, { height: 70 }]}
              value={overrideReason}
              onChangeText={setOverrideReason}
              multiline
              placeholder="Reason for manual override"
              placeholderTextColor="#94a3b8"
            />

            <View style={styles.modalFooter}>
              <TouchableOpacity style={styles.cancelBtn} onPress={() => setModalVisible(false)}>
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.submitBtn} onPress={handleApplyOverride}>
                <Text style={styles.submitBtnText}>Execute Override</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8fafc',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    backgroundColor: '#ffffff',
    borderBottomWidth: 1,
    borderBottomColor: '#e2e8f0',
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  headerTitle: {
    color: '#0f172a',
    fontSize: 16,
    fontWeight: '800',
    letterSpacing: -0.3,
  },
  headerSubtitle: {
    color: '#64748b',
    fontSize: 11,
    fontWeight: '500',
    marginTop: 2,
  },
  refreshBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#eff6ff',
    borderWidth: 1,
    borderColor: '#bfdbfe',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
  },
  refreshBtnText: {
    color: '#1d4ed8',
    fontSize: 12,
    fontWeight: '700',
  },
  kpiContainer: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingVertical: 12,
    gap: 8,
    backgroundColor: '#ffffff',
    borderBottomWidth: 1,
    borderBottomColor: '#f1f5f9',
  },
  kpiCard: {
    flex: 1,
    borderRadius: 12,
    padding: 10,
    borderWidth: 1,
    shadowColor: '#0f172a',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.02,
    shadowRadius: 4,
    elevation: 1,
  },
  kpiLabel: {
    color: '#475569',
    fontSize: 9.5,
    textTransform: 'uppercase',
    fontWeight: '700',
    marginBottom: 2,
    letterSpacing: 0.3,
  },
  kpiValue: {
    color: '#0f172a',
    fontSize: 15,
    fontWeight: '800',
    letterSpacing: -0.3,
  },
  kpiSub: {
    color: '#64748b',
    fontSize: 9.5,
    fontWeight: '500',
    marginTop: 2,
  },
  actionBar: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    backgroundColor: '#ffffff',
    borderBottomWidth: 1,
    borderBottomColor: '#f1f5f9',
  },
  actionPromptText: {
    color: '#475569',
    fontSize: 10.5,
    fontWeight: '700',
    marginBottom: 8,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  actionButtonsRow: {
    flexDirection: 'row',
    gap: 8,
  },
  actionBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 7.5,
    borderRadius: 8,
    borderWidth: 1,
  },
  actionBtnText: {
    fontSize: 11,
    fontWeight: '700',
  },
  contentScroll: {
    flex: 1,
    paddingHorizontal: 16,
    paddingVertical: 14,
    backgroundColor: '#f8fafc',
  },
  sectionHeading: {
    color: '#0f172a',
    fontSize: 13,
    fontWeight: '800',
    marginBottom: 10,
    letterSpacing: -0.2,
  },
  clusterList: {
    gap: 10,
  },
  clusterCard: {
    backgroundColor: '#ffffff',
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    shadowColor: '#0f172a',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.03,
    shadowRadius: 6,
    elevation: 1,
  },
  rank1Card: {
    borderColor: '#fca5a5',
    backgroundColor: '#fffafb',
  },
  clusterHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  rankBadge: {
    backgroundColor: '#eff6ff',
    paddingHorizontal: 8,
    paddingVertical: 3.5,
    borderRadius: 6,
    marginRight: 10,
    borderWidth: 1,
    borderColor: '#dbeafe',
  },
  rankText: {
    color: '#1d4ed8',
    fontSize: 11.5,
    fontWeight: '800',
  },
  clusterTitleCol: {
    flex: 1,
  },
  clusterCountyName: {
    color: '#0f172a',
    fontSize: 13.5,
    fontWeight: '700',
  },
  clusterMetricsSummary: {
    color: '#64748b',
    fontSize: 10.5,
    fontWeight: '500',
    marginTop: 2,
  },
  scoreBadge: {
    alignItems: 'flex-end',
    backgroundColor: '#f8fafc',
    paddingHorizontal: 9,
    paddingVertical: 3.5,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  scoreVal: {
    color: '#0f172a',
    fontSize: 13.5,
    fontWeight: '800',
  },
  scoreLabel: {
    color: '#64748b',
    fontSize: 8.5,
    textTransform: 'uppercase',
    fontWeight: '700',
  },
  shelterAssignWrap: {
    backgroundColor: '#f8fafc',
    borderRadius: 10,
    padding: 10,
    borderWidth: 1,
    borderColor: '#f1f5f9',
    gap: 6,
  },
  assignedTitle: {
    color: '#64748b',
    fontSize: 10.5,
    fontWeight: '600',
    marginBottom: 2,
  },
  assignedShelterItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  assignedShelterName: {
    color: '#334155',
    fontSize: 11.5,
    fontWeight: '600',
    flex: 1,
    marginLeft: 6,
  },
  assignedShelterCount: {
    color: '#059669',
    fontSize: 11.5,
    fontWeight: '700',
  },
  noShelterWarning: {
    color: '#dc2626',
    fontSize: 11,
    fontWeight: '600',
  },
  auditSection: {
    marginTop: 18,
    marginBottom: 30,
  },
  auditBox: {
    backgroundColor: '#ffffff',
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    gap: 6,
  },
  auditLogLine: {
    color: '#475569',
    fontSize: 11,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
    lineHeight: 16,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(15, 23, 42, 0.45)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
  },
  modalContent: {
    width: '100%',
    maxWidth: 480,
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    shadowColor: '#0f172a',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 16,
    elevation: 5,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  modalTitle: {
    color: '#0f172a',
    fontSize: 16,
    fontWeight: '800',
  },
  inputLabel: {
    color: '#475569',
    fontSize: 11.5,
    fontWeight: '700',
    marginBottom: 6,
    marginTop: 10,
  },
  actionTypeDisplay: {
    backgroundColor: '#eff6ff',
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#bfdbfe',
  },
  actionTypeText: {
    color: '#1d4ed8',
    fontSize: 13,
    fontWeight: '700',
  },
  modalInput: {
    backgroundColor: '#f8fafc',
    borderRadius: 8,
    padding: 10,
    color: '#0f172a',
    fontSize: 13,
    borderWidth: 1,
    borderColor: '#cbd5e1',
  },
  modalFooter: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 10,
    marginTop: 20,
  },
  cancelBtn: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 8,
    backgroundColor: '#f1f5f9',
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  cancelBtnText: {
    color: '#475569',
    fontSize: 13,
    fontWeight: '600',
  },
  submitBtn: {
    paddingHorizontal: 18,
    paddingVertical: 10,
    borderRadius: 8,
    backgroundColor: '#2563eb',
  },
  submitBtnText: {
    color: '#ffffff',
    fontSize: 13,
    fontWeight: '700',
  },
});

