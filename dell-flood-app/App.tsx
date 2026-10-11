import React, { useState, useEffect, useRef } from 'react';
import { StyleSheet, View, Text, StatusBar, SafeAreaView, TouchableOpacity, TextInput, ScrollView, ActivityIndicator, Alert, Dimensions, Platform, Linking, Animated, ImageBackground, Image, Modal } from 'react-native';
import { Map, AlertOctagon, Cpu, Settings as SettingsIcon, Shield, Users, LogOut, Lock, User, Plus, Filter, CheckSquare, MessageSquare, PhoneCall, Bell, Mail, Compass, Eye, EyeOff, ShieldAlert, Check, PlusCircle, FileText, Home, Activity, Phone, ChevronRight, ChevronUp, ArrowLeft, MapPin, CheckCircle2, Waves, Globe } from 'lucide-react-native';
import { LinearGradient } from 'expo-linear-gradient';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Speech from 'expo-speech';
import * as Notifications from 'expo-notifications';
import { MapView } from './src/components/MapView';
import { ReportForm } from './src/components/ReportForm';
import { AgentPanel } from './src/components/AgentPanel';
import { SettingsPanel } from './src/components/SettingsPanel';
import { ChatbotPanel } from './src/components/ChatbotPanel';
import { TriagePanel } from './src/components/TriagePanel';
import { NowcastPanel } from './src/components/NowcastPanel';
import { ReportViewerModal } from './src/components/ReportViewerModal';
import { apiService, DEFAULT_API_URL, DetectionResult, CrowdReport, ShelterInfo } from './src/services/api';
import { AppLanguage, t, DEFAULT_DEMO_PHONE_E164 } from './src/utils/i18n';

type TabType = 'map' | 'report' | 'raise' | 'agent' | 'nowcast' | 'triage' | 'settings';


type UserRole = 'none' | 'citizen' | 'official';
type ScreenMode = 'login' | 'signup';

const { width } = Dimensions.get('window');

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

export default function App() {
  const [role, setRole] = useState<UserRole>('none');
  const [screenMode, setScreenMode] = useState<ScreenMode>('login');
  const [activeTab, setActiveTab] = useState<TabType>('report');
  const [appLanguage, setAppLanguage] = useState<AppLanguage>('en');
  const [showLangModal, setShowLangModal] = useState<boolean>(true);
  
  // Track seen complaint IDs to prevent notification loops
  const seenComplaintIdsRef = useRef<Set<number>>(new Set());
  const isInitialDashboardFetchRef = useRef<boolean>(true);
  
  // Report Viewer Modal State
  const [showReportModal, setShowReportModal] = useState<boolean>(false);
  
  // Auth Form State
  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [phone, setPhone] = useState<string>('');
  const [authRole, setAuthRole] = useState<string>('citizen');
  const [loadingAuth, setLoadingAuth] = useState<boolean>(false);
  const [currentUser, setCurrentUser] = useState<string>('');
  const [authError, setAuthError] = useState<string>('');
  const [serverUrl, setServerUrl] = useState<string>(DEFAULT_API_URL);
  const [showServerConfig, setShowServerConfig] = useState<boolean>(false);
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState<boolean>(false);
  const [confirmPassword, setConfirmPassword] = useState<string>('');
  const [rememberMe, setRememberMe] = useState<boolean>(false);
  const [agreeTerms, setAgreeTerms] = useState<boolean>(false);
  const authScrollRef = useRef<ScrollView>(null);
  const [isPulledUp, setIsPulledUp] = useState<boolean>(false);

  const handlePullUpToggle = () => {
    if (!isPulledUp) {
      authScrollRef.current?.scrollTo({ y: 250, animated: true });
      setIsPulledUp(true);
    } else {
      authScrollRef.current?.scrollTo({ y: 0, animated: true });
      setIsPulledUp(false);
    }
  };

  // App Global states
  const [lastResult, setLastResult] = useState<DetectionResult | null>(null);
  const [activeLat, setActiveLat] = useState<number>(20.5937);
  const [activeLon, setActiveLon] = useState<number>(78.9629);

  
  // Dashboard complaints & stats states
  const [complaints, setComplaints] = useState<CrowdReport[]>([]);
  const [stats, setStats] = useState<any>({ total_active: 0, total_resolved: 0, location_groups: {} });
  const [loadingDashboard, setLoadingDashboard] = useState<boolean>(false);

  // Filters for Official Panel
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [severityFilter, setSeverityFilter] = useState<string>('all');

  const sevRank = (s: string) => {
    const up = (s || '').toUpperCase();
    if (up === 'CRITICAL' || up === 'SEVERE') return 4;
    if (up === 'HIGH') return 3;
    if (up === 'MODERATE' || up === 'MEDIUM') return 2;
    if (up === 'LOW' || up === 'MINOR') return 1;
    return 0;
  };

  const filteredComplaints = React.useMemo(() => {
    return complaints
      .filter(c => {
        const statusMatch = statusFilter === 'all' || c.status === statusFilter;
        const severityMatch = severityFilter === 'all' || c.severity === severityFilter;
        return statusMatch && severityMatch;
      })
      .sort((a, b) => {
        const diff = sevRank(b.severity) - sevRank(a.severity);
        if (diff !== 0) return diff;
        return (b.timestamp || 0) - (a.timestamp || 0);
      });
  }, [complaints, statusFilter, severityFilter]);

  // Shared Chatbot states
  const [chatQuery, setChatQuery] = useState<string>('');
  const [chatHistory, setChatHistory] = useState<{ q: string; a: string }[]>([]);
  const [chatLoading, setChatLoading] = useState<boolean>(false);

  // Live Toast & Push Token states
  const [notification, setNotification] = useState<{ title: string; message: string; type: 'emergency' | 'warning' | 'info' } | null>(null);
  const [pushToken, setPushToken] = useState<string>('');
  
  // SMTP recipient is controlled by Reciever_email in the backend .env file.
  const [recipientEmail] = useState<string>('');

  const [expandedComplaintId, setExpandedComplaintId] = useState<number | null>(null);

  // Assam report preview states
  const [assamHotspots, setAssamHotspots] = useState<any[]>([]);
  const [loadingAssamPreview, setLoadingAssamPreview] = useState<boolean>(false);
  const [showAssamPreview, setShowAssamPreview] = useState<boolean>(false);

  const handlePreviewAssamReport = async () => {
    if (showAssamPreview) {
      setShowAssamPreview(false);
      return;
    }
    
    if (assamHotspots.length > 0) {
      setShowAssamPreview(true);
      return;
    }

    setLoadingAssamPreview(true);
    try {
      const res = await apiService.getAssamTop10Preview();
      if (res.status === 'SUCCESS') {
        setAssamHotspots(res.hotspots);
        setShowAssamPreview(true);
      } else {
        Alert.alert('Error', 'Failed to retrieve state flood preview.');
      }
    } catch (e) {
      Alert.alert('Error', 'Assam report preview request failed.');
    } finally {
      setLoadingAssamPreview(false);
    }
  };

  const handleSelectLanguage = async (selected: AppLanguage) => {
    setAppLanguage(selected);
    setShowLangModal(false);
    try {
      await AsyncStorage.setItem('aegis_app_language', selected);
      if (Platform.OS === 'web') {
        localStorage.setItem('aegis_app_language', selected);
      }
    } catch (e) {}
  };

  useEffect(() => {
    // Initialize API Service (load custom API URL/mock state from storage)
    apiService.init().catch(err => console.log('API Service initialization failed:', err));

    // Check saved language preference (P35: First-launch language modal)
    AsyncStorage.getItem('aegis_app_language')
      .then(savedLang => {
        if (savedLang === 'en' || savedLang === 'hi') {
          setAppLanguage(savedLang);
        }
        // Always show language modal on startup as requested by user ("before starting the app ask the user to select any language")
        setShowLangModal(true);
      })
      .catch(() => setShowLangModal(true));

    // Restore session on page refresh
    try {
      if (Platform.OS === 'web') {
        const savedUser = localStorage.getItem('user_username');
        const savedRole = localStorage.getItem('user_role');
        if (savedUser && savedRole) {
          setCurrentUser(savedUser);
          setRole(savedRole as any);
          setActiveTab('report');
        }
      }
    } catch (e) {}

    apiService.init();

    registerForPushNotificationsAsync().then(token => {
      if (token) setPushToken(token);
    });
  }, []);

  useEffect(() => {
    if (role !== 'none') {
      fetchDashboardData(true);
    }
  }, [role]);

  async function registerForPushNotificationsAsync() {
    if (Platform.OS === 'web') return '';
    try {
      if (Platform.OS === 'android') {
        await Notifications.setNotificationChannelAsync('default', {
          name: 'default',
          importance: Notifications.AndroidImportance.MAX,
          vibrationPattern: [0, 250, 250, 250],
          lightColor: '#2563eb',
        }).catch(err => console.log('Notification channel setup error:', err));
      }
      const { status: existingStatus } = await Notifications.getPermissionsAsync().catch(() => ({ status: 'denied' }));
      let finalStatus = existingStatus;
      if (existingStatus !== 'granted') {
        const { status } = await Notifications.requestPermissionsAsync().catch(() => ({ status: 'denied' }));
        finalStatus = status;
      }
      if (finalStatus !== 'granted') {
        return '';
      }
      const token = (await Notifications.getExpoPushTokenAsync().catch(() => ({ data: '' }))).data;
      console.log('Expo Push Token Registered:', token);
      return token || '';
    } catch (e) {
      console.log('Error obtaining expo push token:', e);
      return '';
    }
  }

  const speakAlert = (text: string) => {
    // Voice assistant removed
  };

  const triggerNotification = (title: string, message: string, type: 'emergency' | 'warning' | 'info') => {
    try {
      setNotification({ title, message, type });
      speakAlert(`${title}. ${message}`);
      
      if (Platform.OS !== 'web') {
        Notifications.scheduleNotificationAsync({
          content: {
            title: `🚨 ${title.toUpperCase()}`,
            body: message,
            sound: true,
          },
          trigger: null,
        }).catch(err => console.log('[Notification schedule err]:', err));
      }

      // Trigger backend SMTP email alert to the configured recipient email
      if (type === 'emergency' || type === 'warning') {
        apiService.triggerEmailAlert(recipientEmail, title, message)
          .then(res => console.log('[SMTP Email Alert] Dispatched successfully to the backend-configured recipient:', res))
          .catch(err => console.log('[SMTP Email Alert] Dispatch failed:', err));
      }
      
      setTimeout(() => setNotification(null), 6000);
    } catch (err) {
      console.log('[triggerNotification caught error]:', err);
    }
  };

  const fetchDashboardData = async (isInitial = false) => {
    if (isInitial && complaints.length === 0) {
      setLoadingDashboard(true);
    }
    try {
      const data = await apiService.getComplaintsAndShelters();
      const currentList: CrowdReport[] = data.complaints || [];
      
      if (isInitialDashboardFetchRef.current) {
        // Seed seen IDs on first load so pre-existing complaints don't trigger notification storm
        currentList.forEach(c => {
          if (c.id) seenComplaintIdsRef.current.add(c.id);
        });
        isInitialDashboardFetchRef.current = false;
      } else if (role === 'official') {
        // Only alert if a genuinely new high-severity complaint arrived during this live session
        const unseenSevere = currentList.filter(
          c => c.id && !seenComplaintIdsRef.current.has(c.id) && (c.severity === 'SEVERE' || c.severity === 'CRITICAL')
        );
        
        if (unseenSevere.length > 0) {
          const newest = unseenSevere[0];
          triggerNotification(
            "New Critical Report",
            `Severe incident reported at ${newest.location_name || `${newest.lat.toFixed(2)}°N, ${newest.lon.toFixed(2)}°E`}`,
            "emergency"
          );
        }
        
        currentList.forEach(c => {
          if (c.id) seenComplaintIdsRef.current.add(c.id);
        });
      }
      
      // Update complaints state only if items actually differ to prevent unnecessary UI re-rendering
      setComplaints(prev => {
        if (prev.length === currentList.length && prev.every((p, i) => p.id === currentList[i]?.id && p.status === currentList[i]?.status)) {
          return prev;
        }
        return currentList;
      });

      if (data.stats) {
        setStats(data.stats);
      }
    } catch (e) {
      console.log("Error fetching complaints: ", e);
    } finally {
      if (isInitial) {
        setLoadingDashboard(false);
      }
    }
  };

  const handleLocationSelected = (result: DetectionResult, lat: number, lon: number) => {
    setLastResult(result);
    setActiveLat(lat);
    setActiveLon(lon);
    
    // Only alert on meaningful, confirmed high/critical flood inundation (never for normal dry ground)
    if (result.area_sq_km >= 0.5 && (result.severity === 'CRITICAL' || result.severity === 'HIGH')) {
      triggerNotification(
        `Active ${result.classification} Confirmed`,
        `Severity rated as ${result.severity} over an area of ${result.area_sq_km.toFixed(2)} sq km.`,
        "emergency"
      );
    }
  };

  const handleLogout = () => {
    seenComplaintIdsRef.current.clear();
    isInitialDashboardFetchRef.current = true;
    setRole('none');
    setUsername('');
    setPassword('');
    setPhone('');
    setCurrentUser('');
    setActiveTab('report');
    setChatHistory([]);
    setNotification(null);
    setShowLangModal(true);
    try {
      if (Platform.OS === 'web') {
        localStorage.removeItem('user_username');
        localStorage.removeItem('user_role');
      }
    } catch(e) {}
  };

  const handleAuthSubmit = async () => {
    setAuthError('');
    if (!username.trim() || !password.trim()) {
      setAuthError('Please complete all form fields.');
      return;
    }
    if (screenMode === 'signup' && password !== confirmPassword) {
      setAuthError('Passwords do not match.');
      return;
    }
    if (screenMode === 'signup' && !agreeTerms) {
      setAuthError('Please agree to the Terms & Privacy Policy.');
      return;
    }
    setLoadingAuth(true);
    try {
      if (screenMode === 'signup') {
        const res = await apiService.register(username, password, authRole, phone, pushToken);
        if (res.status === 'SUCCESS') {
          Alert.alert('Account Created', 'Please login with your new account.');
          setScreenMode('login');
          setUsername('');
          setPassword('');
          setConfirmPassword('');
          setPhone('');
        } else {
          setAuthError(res.detail || 'Registration failed.');
        }
      } else {
        const res = await apiService.login(username, password, pushToken);
        if (res.status === 'SUCCESS') {
          setCurrentUser(res.username);
          setRole(res.role);
          setActiveTab('report');
          setUsername('');
          setPassword('');
          setPhone('');
          setAuthError('');
          try {
            if (Platform.OS === 'web') {
              localStorage.setItem('user_username', res.username);
              localStorage.setItem('user_role', res.role);
            }
          } catch(e) {}
        } else {
          setAuthError('Invalid credentials.');
        }
      }
    } catch (e: any) {
      setAuthError(e.message || 'Credentials not found / Wrong password.');
    } finally {
      setLoadingAuth(false);
    }
  };

  const handleResolveComplaint = async (id: number) => {
    try {
      // Optimistic update in place to preserve scroll position
      setComplaints(prev => prev.map(c => c.id === id ? { ...c, status: 'resolved' } : c));
      setStats((prev: any) => ({
        ...prev,
        total_active: Math.max(0, (prev.total_active || 1) - 1),
        total_resolved: (prev.total_resolved || 0) + 1
      }));
      setExpandedComplaintId(null);
      const res = await apiService.resolveComplaint(id);
      if (res.status === 'SUCCESS') {
        triggerNotification("Report Resolved", "Ground report status marked resolved in SQL.", "info");
      }
    } catch (e) {
      Alert.alert('Error', 'Unable to update status.');
    }
  };

  const handleVoiceCallTrigger = async (phoneNum: string, severity: string, locationName?: string) => {
    const targetNumber = phoneNum || DEFAULT_DEMO_PHONE_E164;
    const alertMessage = `Emergency Alert: Active ${severity} water levels verified near your location. Route paths are updated. Please evacuate to the nearest safe shelter immediately.`;
    try {
      const res = await apiService.triggerVoiceCall(
        targetNumber,
        alertMessage,
        {
          location: locationName || `${activeLat.toFixed(2)}N, ${activeLon.toFixed(2)}E`,
          severity,
          language: appLanguage,
          max_depth_m: 1.1,
        }
      );
      if (res.status === 'SUCCESS') {
        setExpandedComplaintId(null);
        triggerNotification(
          "Twilio Voice Call Outbound",
          `Automated ${appLanguage === 'hi' ? 'Hindi (Polly.Aditi)' : 'English (alice)'} warning call dialed to ${targetNumber}.`,
          "info"
        );
      }
    } catch (e) {
      Alert.alert('Error', 'Voice gateway request failed.');
    }
  };

  const handleEmailReportTrigger = async (c: CrowdReport) => {
    triggerNotification("Compiling RAG Report", "Invoking Gemini RAG compiler for situation brief...", "info");
    try {
      const seed = Math.abs(c.lat + c.lon);
      const isSevere = c.severity === 'SEVERE' || c.severity === 'HIGH' || c.severity === 'CRITICAL';
      const area = Math.round((isSevere ? 2.0 + (seed % 3) * 1.2 : 0.5 + (seed % 3) * 0.4) * 100) / 100;
      const pop = Math.round(area * 1150);
      const bld = Math.round(area * 40);
      const fac = area > 0 ? Math.max(1, Math.round(area * 0.4)) : 0;

      const locName = c.location_name || `${c.lat.toFixed(2)}°N, ${c.lon.toFixed(2)}°E District`;
      const payload = {
        to_email: recipientEmail,
        location: locName,
        lat: c.lat,
        lon: c.lon,
        area_sq_km: area,
        classification: "Flood Inundation",
        severity: c.severity,
        population_affected: pop,
        buildings_damaged: bld,
        facilities_at_risk: fac
      };
      
      const res = await apiService.triggerEmailReport(payload);
      if (res.status === 'SUCCESS') {
        setExpandedComplaintId(null);
        triggerNotification("Email Alert Sent", "LLM Situation brief sent to the configured .env recipient.", "info");
        Alert.alert('RAG Email Dispatched', `The following LLM report was sent successfully:\n\n${res.report}`);
      }
    } catch (e: any) {
      Alert.alert('Error', e?.message || 'Direct SMTP dispatch request failed.');
    }
  };

  const handleBroadcastNotification = async (c: CrowdReport) => {
    triggerNotification("Broadcasting Push Alerts", "Publishing emergency push notifications to all users...", "info");
    try {
      const location = c.location_name || `${c.lat.toFixed(2)}°N, ${c.lon.toFixed(2)}°E District`;
      const seed = Math.abs(c.lat + c.lon);
      const isSevere = c.severity === 'SEVERE' || c.severity === 'HIGH' || c.severity === 'CRITICAL';
      const area = Math.round((isSevere ? 2.0 + (seed % 3) * 1.2 : 0.5 + (seed % 3) * 0.4) * 100) / 100;
      
      const res = await apiService.broadcastNotification(location, c.severity, area);
      if (res.status === 'SUCCESS') {
        setExpandedComplaintId(null);
        triggerNotification("Push Alert Broadcasted", res.message, "info");
        Alert.alert('Broadcast Dispatched', `Title: ${res.title}\nBody: ${res.body}\n\n${res.message}`);
      } else {
        Alert.alert('Broadcast Failed', res.message || 'Error occurred.');
      }
    } catch (e) {
      Alert.alert('Error', 'Push broadcast request failed.');
    }
  };

  const handleDeploySDRF = (location: string) => {
    setExpandedComplaintId(null);
    triggerNotification(
      "SDRF Dispatched", 
      `Rescue rafts and medical assets sent to coordinates near: ${location}`, 
      "emergency"
    );
  };

  const renderRegionalImpactReport = () => {
    if (!lastResult) {
      return (
        <View style={styles.panelCard}>
          <View style={styles.cardHeader}>
            <FileText size={18} color="#64748b" />
            <Text style={styles.cardTitle}>Active Regional Disaster Brief</Text>
          </View>
          <Text style={styles.noDataText}>💡 Select a village or run satellite inference on the map to generate the spatial impact report.</Text>
        </View>
      );
    }

    const popPerc = Math.min(100, (lastResult.impact.population / 15000) * 100);
    const bldPerc = Math.min(100, (lastResult.impact.buildings / 500) * 100);

    return (
      <View style={styles.panelCard}>
        <View style={styles.cardHeader}>
          <FileText size={18} color="#ef4444" />
          <Text style={styles.cardTitle}>📑 Active Disaster Impact Brief (Full Report)</Text>
        </View>
        <View style={styles.reportBulletin}>
          <Text style={styles.reportSummaryTitle}>
            📍 Target Area: {lastResult.classification} ({lastResult.severity} RISK)
          </Text>
          <Text style={styles.reportSummaryMeta}>
            Coordinates: {activeLat.toFixed(4)}° N, {activeLon.toFixed(4)}° E • Confidence: {lastResult.confidence_score}%
          </Text>

          <View style={styles.reportDivider} />

          {/* Section 1: Human Population Impact */}
          <View style={styles.reportSectionRow}>
            <View style={styles.reportSectionIconBg}>
              <Users size={16} color="#d97706" />
            </View>
            <View style={{ flex: 1, marginLeft: 10 }}>
              <Text style={styles.reportSectionLabel}>👥 Human Population Impact</Text>
              <Text style={styles.reportSectionValue}>{lastResult.impact.population.toLocaleString()} residents affected</Text>
              <View style={styles.reportProgressBarBg}>
                <View style={[styles.reportProgressBar, { width: `${popPerc}%`, backgroundColor: '#f59e0b' }]} />
              </View>
            </View>
          </View>

          {/* Section 2: Residential Structures */}
          <View style={styles.reportSectionRow}>
            <View style={styles.reportSectionIconBg}>
              <Home size={16} color="#dc2626" />
            </View>
            <View style={{ flex: 1, marginLeft: 10 }}>
              <Text style={styles.reportSectionLabel}>🏠 Residential Structures Compromised</Text>
              <Text style={styles.reportSectionValue}>{lastResult.impact.buildings} homes damaged</Text>
              <View style={styles.reportProgressBarBg}>
                <View style={[styles.reportProgressBar, { width: `${bldPerc}%`, backgroundColor: '#ef4444' }]} />
              </View>
            </View>
          </View>

          {/* Section 3: Critical Facilities */}
          <View style={styles.reportSectionRow}>
            <View style={styles.reportSectionIconBg}>
              <Activity size={16} color="#059669" />
            </View>
            <View style={{ flex: 1, marginLeft: 10 }}>
              <Text style={styles.reportSectionLabel}>🏫 Critical Facilities & Lifelines</Text>
              <View style={styles.infraStatusRow}>
                <Text style={styles.infraStatusDot}>🏥 Sadar Hospital: {lastResult.area_sq_km > 0 ? '🛑 FLOODED' : '🟢 SAFE'}</Text>
                <Text style={styles.infraStatusDot}>🏫 Government School: {lastResult.area_sq_km > 0 ? '🛑 INUNDATED' : '🟢 SAFE'}</Text>
                <Text style={styles.infraStatusDot}>🔌 Grid Powerlines: {lastResult.area_sq_km > 0 ? '🛑 DISCONNECTED' : '🟢 ACTIVE'}</Text>
              </View>
            </View>
          </View>

          {/* Recommendations block */}
          <View style={styles.recommendationsBlock}>
            <Text style={styles.recommendationsTitle}>💡 Recommended Actions:</Text>
            <Text style={styles.recommendationsText}>
              {lastResult.severity === 'CRITICAL' || lastResult.severity === 'HIGH'
                ? "Immediate emergency alerts have been triggered. Mobilize rescue boats, dispatch warnings via Twilio/SMS channels, and route affected residents to the nearest green shelter."
                : "Continuous satellite radar monitoring is active. No immediate evacuation is ordered, but municipal drain clearings are advised."}
            </Text>
          </View>
        </View>
      </View>
    );
  };

  const handleChatQuery = async () => {
    if (!chatQuery.trim()) return;
    setChatLoading(true);
    const userQ = chatQuery;
    setChatQuery('');
    try {
      const answer = await apiService.askQuestion(userQ, lastResult || undefined);
      setChatHistory(prev => [...prev, { q: userQ, a: answer }]);
    } catch (e) {
      setChatHistory(prev => [...prev, { q: userQ, a: "RAG service offline. Please try again later." }]);
    } finally {
      setChatLoading(false);
    }
  };

  const toggleScreenMode = () => {
    setScreenMode(screenMode === 'login' ? 'signup' : 'login');
    setUsername('');
    setPassword('');
    setConfirmPassword('');
    setPhone('');
    setAuthError('');
    setShowPassword(false);
    setShowConfirmPassword(false);
    setAgreeTerms(false);
  };

  // First-Launch / Pre-Login Language Selection Gate (P35: Ask user to select English or Hindi before login/starting the app)
  const renderLanguageModal = () => (
    <Modal visible={showLangModal} transparent animationType="fade">
      <View style={{ flex: 1, backgroundColor: 'rgba(15, 23, 42, 0.72)', justifyContent: 'center', alignItems: 'center', padding: 20 }}>
        <View style={{ width: '100%', maxWidth: 400, backgroundColor: '#ffffff', borderRadius: 24, padding: 26, borderWidth: 1, borderColor: '#e2e8f0', alignItems: 'center' }}>
          <View style={{ width: 56, height: 56, borderRadius: 28, backgroundColor: '#eff6ff', justifyContent: 'center', alignItems: 'center', marginBottom: 12, borderWidth: 1, borderColor: '#bfdbfe' }}>
            <Globe size={28} color="#2563eb" />
          </View>
          <View style={{ backgroundColor: '#ecfdf5', borderWidth: 1, borderColor: '#a7f3d0', paddingHorizontal: 10, paddingVertical: 3, borderRadius: 999, marginBottom: 8 }}>
            <Text style={{ fontSize: 10, fontWeight: '800', color: '#059669' }}>STEP 1 OF 2 • BEFORE LOGIN</Text>
          </View>
          <Text style={{ fontSize: 18, fontWeight: '800', color: '#0f172a', textAlign: 'center', marginBottom: 6 }}>
            {t(appLanguage, 'langModalTitle')}
          </Text>
          <Text style={{ fontSize: 12, color: '#64748b', textAlign: 'center', lineHeight: 18, marginBottom: 18 }}>
            {t(appLanguage, 'langModalSubtitle')}
          </Text>

          <View style={{ width: '100%', gap: 10 }}>
            <TouchableOpacity
              style={{
                flexDirection: 'row',
                alignItems: 'center',
                justifyContent: 'space-between',
                paddingVertical: 14,
                paddingHorizontal: 16,
                borderRadius: 14,
                borderWidth: 2,
                borderColor: appLanguage === 'en' ? '#2563eb' : '#e2e8f0',
                backgroundColor: appLanguage === 'en' ? '#eff6ff' : '#f8fafc',
              }}
              onPress={() => handleSelectLanguage('en')}
              activeOpacity={0.85}
            >
              <View>
                <Text style={{ fontSize: 15, fontWeight: '800', color: '#0f172a' }}>🇬🇧 English</Text>
                <Text style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>Full App, Alerts & Voice Calls in English</Text>
              </View>
              <Text style={{ fontSize: 12, fontWeight: '800', color: '#2563eb' }}>Continue →</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={{
                flexDirection: 'row',
                alignItems: 'center',
                justifyContent: 'space-between',
                paddingVertical: 14,
                paddingHorizontal: 16,
                borderRadius: 14,
                borderWidth: 2,
                borderColor: appLanguage === 'hi' ? '#059669' : '#e2e8f0',
                backgroundColor: appLanguage === 'hi' ? '#ecfdf5' : '#f8fafc',
              }}
              onPress={() => handleSelectLanguage('hi')}
              activeOpacity={0.85}
            >
              <View>
                <Text style={{ fontSize: 15, fontWeight: '800', color: '#0f172a' }}>🇮🇳 हिन्दी (Hindi)</Text>
                <Text style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>पूरा ऐप, अलर्ट और वॉयस कॉल हिंदी में</Text>
              </View>
              <Text style={{ fontSize: 12, fontWeight: '800', color: '#059669' }}>आगे बढ़ें →</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );

  if (role === 'none') {
    return (
      <View style={{ flex: 1, backgroundColor: '#8bbfe8' }}>
        <StatusBar barStyle="dark-content" backgroundColor="transparent" translucent />
        {renderLanguageModal()}
        <ImageBackground
          source={require('./assets/flood-auth-background.png')}
          resizeMode="cover"
          style={authStyles.backgroundImage}
          imageStyle={authStyles.backgroundImageLayer}
        >
          <View style={authStyles.backgroundWash}>
            <ScrollView 
              ref={authScrollRef}
              contentContainerStyle={authStyles.scrollContent}
              keyboardShouldPersistTaps="handled"
              showsVerticalScrollIndicator={false}
              onScroll={(e) => {
                const y = e.nativeEvent.contentOffset.y;
                if (y > 80 && !isPulledUp) {
                  setIsPulledUp(true);
                } else if (y <= 40 && isPulledUp) {
                  setIsPulledUp(false);
                }
              }}
              scrollEventThrottle={16}
            >
              <View style={authStyles.brandingSection} />

              {/* Auth Card */}
              <View style={authStyles.card}>
                {/* Top-Left Arrow Button: Positioned in the clear sky gap, never overlapping 'Welcome Back!' */}
                <TouchableOpacity 
                  style={authStyles.backButton} 
                  onPress={toggleScreenMode} 
                  accessibilityLabel={screenMode === 'signup' ? "Back to Login" : "Switch to Sign Up"}
                  activeOpacity={0.7}
                >
                  <ArrowLeft size={22} color="#0c1e5a" />
                </TouchableOpacity>

                {/* Pull-up handle */}
                <TouchableOpacity 
                  style={authStyles.handleArea} 
                  onPress={handlePullUpToggle} 
                  activeOpacity={0.7}
                  accessibilityLabel={isPulledUp ? "Collapse sign-in form" : "Pull up to fill details"}
                >
                  <View style={authStyles.handleBar} />
                  {!isPulledUp && (
                    <ChevronUp size={18} color="#7d96b8" style={{ marginTop: 2 }} />
                  )}
                </TouchableOpacity>

                {/* Pre-Login Language Switcher Pill on Auth Card */}
                <View style={{ alignItems: 'center', marginBottom: 8 }}>
                  <TouchableOpacity
                    style={{
                      flexDirection: 'row',
                      alignItems: 'center',
                      backgroundColor: '#eff6ff',
                      borderWidth: 1,
                      borderColor: '#bfdbfe',
                      paddingHorizontal: 12,
                      paddingVertical: 5,
                      borderRadius: 999,
                      gap: 6,
                    }}
                    onPress={() => setShowLangModal(true)}
                    activeOpacity={0.8}
                  >
                    <Globe size={13} color="#2563eb" />
                    <Text style={{ fontSize: 11.5, fontWeight: '800', color: '#1d4ed8' }}>
                      {appLanguage === 'hi' ? '🇮🇳 भाषा: हिन्दी (बदलें)' : '🇬🇧 Language: English (Change)'}
                    </Text>
                  </TouchableOpacity>
                </View>

                {/* Title */}
              <Text style={authStyles.formTitle}>
                {screenMode === 'login' ? t(appLanguage, 'loginTitle') : t(appLanguage, 'signupTitle')}
              </Text>
              <Text style={authStyles.formSubtitle}>
                {screenMode === 'login' ? t(appLanguage, 'loginSubtitle') : t(appLanguage, 'signupSubtitle')}
              </Text>

              {/* Error */}
              {authError ? (
                <View style={authStyles.errorBox}>
                  <Text style={authStyles.errorText}>⚠️ {authError}</Text>
                </View>
              ) : null}

              {/* Email / Username */}
              <Text style={authStyles.fieldLabel}>{t(appLanguage, 'emailLabel')}</Text>
              <View style={authStyles.inputRow}>
                <Mail size={16} color="#a0a0b8" style={{ marginRight: 10 }} />
                <TextInput
                  style={authStyles.input}
                  placeholder="you@example.com"
                  placeholderTextColor="#c0c0d0"
                  value={username}
                  onChangeText={setUsername}
                  autoCapitalize="none"
                  keyboardType="email-address"
                />
              </View>

              {/* Password */}
              <Text style={authStyles.fieldLabel}>{t(appLanguage, 'passwordLabel')}</Text>
              <View style={authStyles.inputRow}>
                <Lock size={16} color="#a0a0b8" style={{ marginRight: 10 }} />
                <TextInput
                  style={authStyles.input}
                  placeholder="••••••••"
                  placeholderTextColor="#c0c0d0"
                  secureTextEntry={!showPassword}
                  value={password}
                  onChangeText={setPassword}
                  autoCapitalize="none"
                />
                <TouchableOpacity onPress={() => setShowPassword(!showPassword)} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
                  {showPassword ? <EyeOff size={18} color="#a0a0b8" /> : <Eye size={18} color="#a0a0b8" />}
                </TouchableOpacity>
              </View>

              {/* Signup-only fields */}
              {screenMode === 'signup' && (
                <>
                  {/* Confirm Password */}
                  <Text style={authStyles.fieldLabel}>{t(appLanguage, 'confirmPasswordLabel')}</Text>
                  <View style={authStyles.inputRow}>
                    <Lock size={16} color="#a0a0b8" style={{ marginRight: 10 }} />
                    <TextInput
                      style={authStyles.input}
                      placeholder="••••••••"
                      placeholderTextColor="#c0c0d0"
                      secureTextEntry={!showConfirmPassword}
                      value={confirmPassword}
                      onChangeText={setConfirmPassword}
                      autoCapitalize="none"
                    />
                    <TouchableOpacity onPress={() => setShowConfirmPassword(!showConfirmPassword)} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
                      {showConfirmPassword ? <EyeOff size={18} color="#a0a0b8" /> : <Eye size={18} color="#a0a0b8" />}
                    </TouchableOpacity>
                  </View>

                  {/* Phone */}
                  <Text style={authStyles.fieldLabel}>{t(appLanguage, 'phoneLabel')}</Text>
                  <View style={authStyles.inputRow}>
                    <Phone size={16} color="#a0a0b8" style={{ marginRight: 10 }} />
                    <TextInput
                      style={authStyles.input}
                      placeholder="+91 98765 43210"
                      placeholderTextColor="#c0c0d0"
                      keyboardType="phone-pad"
                      value={phone}
                      onChangeText={setPhone}
                    />
                  </View>

                  {/* Role Selector */}
                  <Text style={authStyles.fieldLabel}>{t(appLanguage, 'roleSelectLabel')}</Text>
                  <View style={authStyles.roleRow}>
                    <TouchableOpacity
                      style={[authStyles.roleBtn, authRole === 'citizen' && authStyles.roleBtnActive]}
                      onPress={() => setAuthRole('citizen')}
                      activeOpacity={0.7}
                    >
                      <Users size={14} color={authRole === 'citizen' ? '#ffffff' : '#8b7bc8'} style={{ marginRight: 6 }} />
                      <Text style={[authStyles.roleBtnText, authRole === 'citizen' && authStyles.roleBtnTextActive]}>
                        {t(appLanguage, 'roleCitizen')}
                      </Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={[authStyles.roleBtn, authRole === 'official' && authStyles.roleBtnActiveBlue]}
                      onPress={() => setAuthRole('official')}
                      activeOpacity={0.7}
                    >
                      <Shield size={14} color={authRole === 'official' ? '#ffffff' : '#8b7bc8'} style={{ marginRight: 6 }} />
                      <Text style={[authStyles.roleBtnText, authRole === 'official' && authStyles.roleBtnTextActive]}>
                        {t(appLanguage, 'roleOfficial')}
                      </Text>
                    </TouchableOpacity>
                  </View>

                  {/* Terms Checkbox */}
                  <TouchableOpacity 
                    style={authStyles.checkRow} 
                    onPress={() => setAgreeTerms(!agreeTerms)}
                    activeOpacity={0.7}
                  >
                    <View style={[authStyles.checkbox, agreeTerms && authStyles.checkboxChecked]}>
                      {agreeTerms && <Check size={12} color="#ffffff" />}
                    </View>
                    <Text style={authStyles.checkLabel}>
                      Agree to <Text style={authStyles.linkText}>Terms</Text> & <Text style={authStyles.linkText}>Privacy</Text>
                    </Text>
                  </TouchableOpacity>
                </>
              )}

              {/* Login-only: Remember Me & Forgot Password */}
              {screenMode === 'login' && (
                <View style={authStyles.rememberRow}>
                  <TouchableOpacity 
                    style={authStyles.checkRow} 
                    onPress={() => setRememberMe(!rememberMe)}
                    activeOpacity={0.7}
                  >
                    <View style={[authStyles.checkbox, rememberMe && authStyles.checkboxChecked]}>
                      {rememberMe && <Check size={12} color="#ffffff" />}
                    </View>
                    <Text style={authStyles.checkLabel}>{t(appLanguage, 'rememberMe')}</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    activeOpacity={0.7}
                    onPress={() => Alert.alert('Password recovery', 'Contact your Aegis system administrator to reset your password.')}
                  >
                    <Text style={authStyles.forgotText}>{t(appLanguage, 'forgotPassword')}</Text>
                  </TouchableOpacity>
                </View>
              )}

              {/* Submit Button */}
              <TouchableOpacity
                style={authStyles.submitBtn}
                onPress={handleAuthSubmit}
                disabled={loadingAuth}
                activeOpacity={0.85}
              >
                <LinearGradient
                  colors={['#6f98f7', '#5f78ef', '#45c5df']}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 1, y: 0 }}
                  style={authStyles.submitGradient}
                >
                  {loadingAuth ? (
                    <ActivityIndicator size="small" color="#ffffff" />
                  ) : (
                    <Text style={authStyles.submitText}>
                      {screenMode === 'login' ? t(appLanguage, 'loginBtn') : t(appLanguage, 'signupBtn')}
                    </Text>
                  )}
                </LinearGradient>
              </TouchableOpacity>

              {/* Divider */}
              <View style={authStyles.dividerRow}>
                <View style={authStyles.dividerLine} />
                <Text style={authStyles.dividerText}>{t(appLanguage, 'orContinueWith')}</Text>
                <View style={authStyles.dividerLine} />
              </View>

              {/* Social Buttons */}
              <View style={authStyles.socialRow}>
                <TouchableOpacity
                  style={authStyles.socialBtn}
                  activeOpacity={0.7}
                  onPress={() => Alert.alert('Google sign-in', 'Google authentication can be connected from the backend settings.')}
                >
                  <Image source={require('./assets/google-sign-in.png')} style={authStyles.socialImage} resizeMode="contain" />
                  <Text style={authStyles.socialBtnText}>Google</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={authStyles.socialBtn}
                  activeOpacity={0.7}
                  onPress={() => Alert.alert('Apple sign-in', 'Apple authentication can be connected from the backend settings.')}
                >
                  <Image source={require('./assets/apple-sign-in.png')} style={authStyles.socialImage} resizeMode="contain" />
                  <Text style={authStyles.socialBtnText}>Apple</Text>
                </TouchableOpacity>
              </View>

              {/* Toggle Link */}
              <View style={authStyles.toggleRow}>
                <Text style={authStyles.toggleText}>
                  {screenMode === 'login' ? t(appLanguage, 'noAccountText') : t(appLanguage, 'haveAccountText')}
                </Text>
                <TouchableOpacity onPress={toggleScreenMode} activeOpacity={0.7}>
                  <Text style={authStyles.toggleLink}>
                    {screenMode === 'login' ? t(appLanguage, 'signupBtn') : t(appLanguage, 'loginBtn')}
                  </Text>
                </TouchableOpacity>
              </View>

              {/* Server Config Toggle */}
              <TouchableOpacity
                style={authStyles.serverToggle}
                onPress={() => setShowServerConfig(!showServerConfig)}
                activeOpacity={0.7}
              >
                <SettingsIcon size={12} color="#a0a0b8" style={{ marginRight: 4 }} />
                <Text style={authStyles.serverToggleText}>
                  {showServerConfig ? t(appLanguage, 'serverSettingsHide') : t(appLanguage, 'serverSettingsShow')}
                </Text>
              </TouchableOpacity>

              {showServerConfig && (
                <View style={authStyles.serverConfigBox}>
                  <Text style={authStyles.serverConfigLabel}>Backend API URL</Text>
                  <View style={authStyles.inputRow}>
                    <TextInput
                      style={[authStyles.input, { marginLeft: 0 }]}
                      value={serverUrl}
                      onChangeText={(text) => {
                        setServerUrl(text);
                        apiService.setApiUrl(text);
                      }}
                      autoCapitalize="none"
                      placeholder="http://192.168.1.7:8000/api"
                      placeholderTextColor="#c0c0d0"
                    />
                  </View>
                </View>
              )}
            </View>
          </ScrollView>
          </View>
        </ImageBackground>
      </View>
    );
  }

  const renderChatbot = () => (
    <View style={{ height: 530, marginBottom: 16, borderRadius: 20, overflow: 'hidden', borderWidth: 1, borderColor: '#e2e8f0', backgroundColor: '#ffffff', shadowColor: '#0f172a', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.04, shadowRadius: 8, elevation: 2 }}>
      <ChatbotPanel 
        lastResult={lastResult} 
        activeLocationName={lastResult ? `${activeLat.toFixed(2)}°N, ${activeLon.toFixed(2)}°E Scan Zone` : undefined}
        onNavigateToCoords={(clat, clon) => {
          setActiveLat(clat);
          setActiveLon(clon);
          setActiveTab('map');
        }}
        onOpenReportModal={() => setShowReportModal(true)}
      />
    </View>
  );



  return (
    <SafeAreaView style={styles.safeContainer}>
      <StatusBar barStyle="dark-content" backgroundColor="#ffffff" />
      {renderLanguageModal()}
      
      {/* Slide-Down glassmorphic banner */}
      {notification && (
        <View style={[
          styles.notificationToast,
          { 
            borderColor: notification.type === 'emergency' ? '#ef4444' : notification.type === 'warning' ? '#f59e0b' : '#2563eb',
            backgroundColor: notification.type === 'emergency' ? '#fef2f2' : '#f8fafc'
          }
        ]}>
          <Bell size={18} color={notification.type === 'emergency' ? '#ef4444' : '#2563eb'} style={{ marginRight: 10 }} />
          <View style={{ flex: 1 }}>
            <Text style={[styles.toastTitle, { color: '#0f172a' }]}>{notification.title}</Text>
            <Text style={[styles.toastMessage, { color: '#475569' }]}>{notification.message}</Text>
          </View>
        </View>
      )}

      {/* Redesigned Modern App Header (Image 1 Inspiration) */}
      <View style={dashStyles.header}>
        <View style={dashStyles.headerLeft}>
          <View style={dashStyles.headerLogoBadge}>
            <Shield size={20} color="#ffffff" />
          </View>
          <View style={{ marginLeft: 10 }}>
            <Text style={dashStyles.headerBrand}>{t(appLanguage, 'appTitle')}</Text>
            <Text style={dashStyles.headerSlogan}>{t(appLanguage, 'appSlogan')}</Text>
          </View>
        </View>
        <View style={dashStyles.headerRight}>
          {/* Language Switcher Pill (P35) */}
          <TouchableOpacity
            style={[dashStyles.rolePill, { borderColor: '#cbd5e1', backgroundColor: '#f8fafc', marginRight: 6 }]}
            onPress={() => handleSelectLanguage(appLanguage === 'en' ? 'hi' : 'en')}
            activeOpacity={0.75}
          >
            <Text style={[dashStyles.rolePillText, { color: '#0f172a' }]}>
              {appLanguage === 'en' ? '🇬🇧 EN | हिं' : '🇮🇳 हिं | EN'}
            </Text>
          </TouchableOpacity>
          <View style={[dashStyles.rolePill, { borderColor: role === 'citizen' ? '#10b981' : '#2563eb', backgroundColor: role === 'citizen' ? '#ecfdf5' : '#eff6ff' }]}>
            <Text style={[dashStyles.rolePillText, { color: role === 'citizen' ? '#059669' : '#2563eb' }]}>
              {role === 'citizen' ? t(appLanguage, 'roleCitizen') : t(appLanguage, 'roleOfficial')}
            </Text>
          </View>
          <TouchableOpacity 
            style={dashStyles.headerIconBtn} 
            onPress={() => Alert.alert('Notifications', 'You have 3 active flood alerts in your region.')}
            activeOpacity={0.7}
          >
            <Bell size={18} color="#0f172a" />
          </TouchableOpacity>
          <TouchableOpacity 
            style={dashStyles.avatarBtn} 
            onPress={handleLogout}
            activeOpacity={0.7}
            accessibilityLabel="Logout"
          >
            <View style={dashStyles.avatarCircle}>
              <Text style={dashStyles.avatarInitial}>{currentUser ? currentUser[0].toUpperCase() : 'A'}</Text>
            </View>
          </TouchableOpacity>
        </View>
      </View>

      <View style={styles.contentBody}>
        {activeTab === 'map' && (
          <MapView
            lastDetection={lastResult}
            onLocationSelected={handleLocationSelected}
            initialLat={activeLat}
            initialLon={activeLon}
            language={appLanguage}
          />
        )}

        {/* Dedicated Page to Raise Ground Issues ONLY */}
        {activeTab === 'raise' && (
          <ReportForm username={currentUser} onReported={fetchDashboardData} language={appLanguage} />
        )}

        {activeTab === 'report' && (
          role === 'citizen' ? (
            <ScrollView 
              style={styles.dashboardContainer} 
              contentContainerStyle={{ paddingBottom: 60 }}
              keyboardShouldPersistTaps="handled"
              removeClippedSubviews={false}
              showsVerticalScrollIndicator={true}
            >
              <View style={dashStyles.dashboardInnerContainer}>
                {/* 1. Hero Safety Banner (Clean Card, No Duplicate Text) */}
                <TouchableOpacity 
                  style={dashStyles.heroBanner} 
                  onPress={() => setActiveTab('map')}
                  activeOpacity={0.9}
                >
                  <Image
                    source={require('./assets/dashboard-hero-banner.jpg')}
                    style={dashStyles.heroBg}
                    resizeMode="cover"
                  />
                </TouchableOpacity>

              {/* 2. Quick Metrics Row: Active Regions, Active Alerts, People at Risk */}
              <View style={dashStyles.metricsRow}>
                <View style={[dashStyles.metricCard, { backgroundColor: '#f0fdf4', borderColor: '#dcfce7' }]}>
                  <View style={[dashStyles.metricIconBadge, { backgroundColor: '#dcfce7' }]}>
                    <Map size={15} color="#16a34a" />
                  </View>
                  <Text style={dashStyles.metricLabel}>{t(appLanguage, 'activeRegions')}</Text>
                  <Text style={dashStyles.metricValue}>{Object.keys(stats.location_groups).length || 12}</Text>
                  <Text style={[dashStyles.metricTrend, { color: '#16a34a' }]}>↑ +2 new</Text>
                </View>

                <View style={[dashStyles.metricCard, { backgroundColor: '#fef2f2', borderColor: '#fee2e2' }]}>
                  <View style={[dashStyles.metricIconBadge, { backgroundColor: '#fee2e2' }]}>
                    <AlertOctagon size={15} color="#ef4444" />
                  </View>
                  <Text style={dashStyles.metricLabel}>{t(appLanguage, 'activeAlerts')}</Text>
                  <Text style={dashStyles.metricValue}>{stats.total_active || 3}</Text>
                  <Text style={[dashStyles.metricTrend, { color: '#dc2626' }]}>↑ +1</Text>
                </View>

                <View style={[dashStyles.metricCard, { backgroundColor: '#f5f3ff', borderColor: '#ede9fe' }]}>
                  <View style={[dashStyles.metricIconBadge, { backgroundColor: '#ede9fe' }]}>
                    <Shield size={15} color="#7c3aed" />
                  </View>
                  <Text style={dashStyles.metricLabel}>{t(appLanguage, 'peopleAtRisk')}</Text>
                  <Text style={dashStyles.metricValue}>
                    {lastResult?.impact?.population ? lastResult.impact.population.toLocaleString() : '2,480'}
                  </Text>
                  <Text style={[dashStyles.metricTrend, { color: '#7c3aed' }]}>↓ -12%</Text>
                </View>
              </View>

              {/* 3. Asymmetric Grid: Interactive Map Card on Left, Action Cards on Right */}
              <View style={dashStyles.gridRow}>
                {/* Left: Interactive Map Card */}
                <TouchableOpacity 
                  style={dashStyles.mapCard} 
                  onPress={() => setActiveTab('map')}
                  activeOpacity={0.9}
                >
                  <View style={dashStyles.mapCardHeader}>
                    <View style={[dashStyles.gridIconBadge, { backgroundColor: '#e0f2fe' }]}>
                      <Map size={15} color="#0284c7" />
                    </View>
                    <View style={{ flex: 1, marginLeft: 8 }}>
                      <Text style={dashStyles.mapCardTitle}>{t(appLanguage, 'interactiveMapTitle')}</Text>
                      <Text style={dashStyles.mapCardDesc} numberOfLines={2}>
                        {t(appLanguage, 'interactiveMapDesc')}
                      </Text>
                    </View>
                    <View style={dashStyles.miniArrowBtn}>
                      <ChevronRight size={13} color="#0284c7" />
                    </View>
                  </View>
                  <View style={dashStyles.mapPreviewContainer}>
                    <Image
                      source={require('./assets/dashboard-map-cropped.jpg')}
                      style={dashStyles.mapPreviewImg}
                      resizeMode="cover"
                    />
                    <View style={dashStyles.mapUpdatedPill}>
                      <Text style={dashStyles.mapUpdatedText}>{t(appLanguage, 'lastUpdated2m')}</Text>
                    </View>
                  </View>
                </TouchableOpacity>

                {/* Right: Stacked Action Cards */}
                <View style={dashStyles.rightCol}>
                  {/* Raise Ground Issue */}
                  <TouchableOpacity 
                    style={dashStyles.actionCardRed} 
                    onPress={() => setActiveTab('raise')}
                    activeOpacity={0.85}
                  >
                    <View style={dashStyles.actionIconBadgeRed}>
                      <AlertOctagon size={16} color="#ef4444" />
                    </View>
                    <Text style={dashStyles.actionTitle}>{t(appLanguage, 'raiseGroundIssueTitle')}</Text>
                    <Text style={dashStyles.actionDesc} numberOfLines={2}>
                      {t(appLanguage, 'raiseGroundIssueDesc')}
                    </Text>
                    <View style={dashStyles.actionBtnRed}>
                      <Text style={dashStyles.actionBtnText}>{t(appLanguage, 'reportNowBtn')}</Text>
                    </View>
                  </TouchableOpacity>

                  {/* Aegis AI Assistant */}
                  <TouchableOpacity 
                    style={dashStyles.actionCardGreen} 
                    onPress={() => setActiveTab('agent')}
                    activeOpacity={0.85}
                  >
                    <View style={dashStyles.actionIconBadgeGreen}>
                      <Activity size={16} color="#10b981" />
                    </View>
                    <Text style={dashStyles.actionTitle}>{t(appLanguage, 'aiAssistantTitle')}</Text>
                    <Text style={dashStyles.actionDesc} numberOfLines={2}>
                      {t(appLanguage, 'aiAssistantDesc')}
                    </Text>
                    <View style={dashStyles.actionBtnGreen}>
                      <Text style={dashStyles.actionBtnText}>{t(appLanguage, 'chatNowBtn')}</Text>
                    </View>
                  </TouchableOpacity>
                </View>
              </View>

              {/* 4. Active Regional Disaster Brief (Expandable Banner Card) */}
              <TouchableOpacity 
                style={dashStyles.briefCard} 
                onPress={() => setShowReportModal(true)}
                activeOpacity={0.85}
              >
                <View style={dashStyles.briefIconBadge}>
                  <FileText size={18} color="#2563eb" />
                </View>
                <View style={dashStyles.briefTextCol}>
                  <Text style={dashStyles.briefTitle}>{t(appLanguage, 'regionalBriefTitle')}</Text>
                  <Text style={dashStyles.briefDesc}>
                    {t(appLanguage, 'regionalBriefDesc')}
                  </Text>
                </View>
                <ChevronRight size={18} color="#94a3b8" />
              </TouchableOpacity>

              {renderChatbot()}

              {/* Personal Alert Warning Logs */}
              <View style={dashStyles.panelCard}>
                <View style={dashStyles.panelCardHeader}>
                  <View style={dashStyles.panelCardHeaderLeft}>
                    <View style={[dashStyles.panelIconBadge, { backgroundColor: '#fef2f2', borderColor: '#fee2e2' }]}>
                      <AlertOctagon size={16} color="#ef4444" />
                    </View>
                    <View style={dashStyles.panelCardTextCol}>
                      <Text style={dashStyles.panelCardTitle} numberOfLines={1}>{t(appLanguage, 'personalAlertLogsTitle')}</Text>
                      <Text style={dashStyles.panelCardSubtitle} numberOfLines={1}>{t(appLanguage, 'personalAlertLogsSub')}</Text>
                    </View>
                  </View>
                  <View style={[dashStyles.panelBadgePill, { backgroundColor: (lastResult && (lastResult.severity === 'CRITICAL' || lastResult.severity === 'HIGH')) ? '#fef2f2' : '#ecfdf5', borderColor: (lastResult && (lastResult.severity === 'CRITICAL' || lastResult.severity === 'HIGH')) ? '#fecaca' : '#a7f3d0' }]}>
                    <Text style={[dashStyles.panelBadgeText, { color: (lastResult && (lastResult.severity === 'CRITICAL' || lastResult.severity === 'HIGH')) ? '#dc2626' : '#059669' }]}>
                      {(lastResult && (lastResult.severity === 'CRITICAL' || lastResult.severity === 'HIGH')) ? 'CRITICAL' : t(appLanguage, 'allClearBadge')}
                    </Text>
                  </View>
                </View>

                {lastResult && (lastResult.severity === 'CRITICAL' || lastResult.severity === 'HIGH') ? (
                  <View style={dashStyles.activeAlertCard}>
                    <View style={dashStyles.alertCardTop}>
                      <View style={dashStyles.alertPulsePill}>
                        <Text style={dashStyles.alertPulseText}>⚠️ IMMEDIATE ADVISORY</Text>
                      </View>
                      <Text style={dashStyles.alertTimeText}>Active Now</Text>
                    </View>
                    <Text style={dashStyles.alertCardMsg}>
                      {lastResult.severity}: Elevated flood risk verified near {activeLat.toFixed(2)}°N, {activeLon.toFixed(2)}°E. Evacuation paths and shelters are active on the interactive map.
                    </Text>
                    <TouchableOpacity 
                      style={dashStyles.alertActionBtn}
                      onPress={() => setActiveTab('map')}
                      activeOpacity={0.85}
                    >
                      <Text style={dashStyles.alertActionBtnText}>View Evacuation Path on Map →</Text>
                    </TouchableOpacity>
                  </View>
                ) : (
                  <View style={dashStyles.emptyCardState}>
                    <Shield size={22} color="#10b981" />
                    <Text style={dashStyles.emptyStateTitle}>{t(appLanguage, 'allClearTitle')}</Text>
                    <Text style={dashStyles.emptyStateDesc}>
                      {t(appLanguage, 'allClearDesc')}
                    </Text>
                  </View>
                )}
              </View>

              {/* Personal Ground Warning Log */}
              <View style={dashStyles.panelCard}>
                <View style={dashStyles.panelCardHeader}>
                  <View style={dashStyles.panelCardHeaderLeft}>
                    <View style={[dashStyles.panelIconBadge, { backgroundColor: '#eff6ff', borderColor: '#dbeafe' }]}>
                      <CheckSquare size={16} color="#2563eb" />
                    </View>
                    <View style={dashStyles.panelCardTextCol}>
                      <Text style={dashStyles.panelCardTitle} numberOfLines={1}>{t(appLanguage, 'personalGroundLogTitle')}</Text>
                      <Text style={dashStyles.panelCardSubtitle} numberOfLines={1}>{t(appLanguage, 'personalGroundLogSub')}</Text>
                    </View>
                  </View>
                  <TouchableOpacity 
                    style={dashStyles.newReportLink}
                    onPress={() => setActiveTab('raise')}
                    activeOpacity={0.8}
                  >
                    <Text style={dashStyles.newReportLinkText}>{t(appLanguage, 'fileReportBtn')}</Text>
                  </TouchableOpacity>
                </View>

                {loadingDashboard ? (
                  <View style={{ paddingVertical: 18, alignItems: 'center' }}>
                    <ActivityIndicator size="small" color="#059669" />
                  </View>
                ) : complaints.filter(c => {
                    const normUser = (currentUser || '').trim().toLowerCase();
                    const cUser = (c.username || '').trim().toLowerCase();
                    if (!normUser) return true;
                    return cUser === normUser || cUser === 'citizen_reporter' || cUser === 'citizen';
                  }).length === 0 ? (
                  <View style={dashStyles.emptyCardState}>
                    <FileText size={22} color="#94a3b8" />
                    <Text style={dashStyles.emptyStateTitle}>{t(appLanguage, 'noReportsTitle')}</Text>
                    <Text style={dashStyles.emptyStateDesc}>
                      {t(appLanguage, 'noReportsDesc')}
                    </Text>
                  </View>
                ) : (
                  complaints.filter(c => {
                    const normUser = (currentUser || '').trim().toLowerCase();
                    const cUser = (c.username || '').trim().toLowerCase();
                    if (!normUser) return true;
                    return cUser === normUser || cUser === 'citizen_reporter' || cUser === 'citizen';
                  }).map((c, index) => (
                    <View key={index} style={dashStyles.modernLogRow}>
                      <View style={dashStyles.modernLogLeft}>
                        <View style={dashStyles.modernLogLocBadge}>
                          <MapPin size={11} color="#0284c7" />
                          <Text style={dashStyles.modernLogLocText}>{c.lat.toFixed(4)}°N, {c.lon.toFixed(4)}°E</Text>
                        </View>
                        <Text style={dashStyles.modernLogDesc}>{c.description}</Text>
                      </View>
                      <View style={dashStyles.modernLogRight}>
                        <View style={[dashStyles.statusPill, { backgroundColor: c.status === 'resolved' ? '#ecfdf5' : '#f5f3ff', borderColor: c.status === 'resolved' ? '#a7f3d0' : '#ddd6fe' }]}>
                          <Text style={[dashStyles.statusPillText, { color: c.status === 'resolved' ? '#059669' : '#7c3aed' }]}>
                            {c.status === 'resolved' ? 'RESOLVED' : 'UNDER REVIEW'}
                          </Text>
                        </View>
                        <Text style={[dashStyles.aiVerifyTag, { color: c.model_confirmed === 1 ? '#059669' : '#64748b' }]}>
                          {c.model_confirmed === 1 ? '✓ AI CONFIRMED' : '⏱ SCAN PENDING'}
                        </Text>
                      </View>
                    </View>
                  ))
                )}
              </View>

              {/* Active Community Reports Feed */}
              <View style={dashStyles.panelCard}>
                <View style={dashStyles.panelCardHeader}>
                  <View style={dashStyles.panelCardHeaderLeft}>
                    <View style={[dashStyles.panelIconBadge, { backgroundColor: '#f5f3ff', borderColor: '#ede9fe' }]}>
                      <Users size={16} color="#7c3aed" />
                    </View>
                    <View style={dashStyles.panelCardTextCol}>
                      <Text style={dashStyles.panelCardTitle} numberOfLines={1}>{t(appLanguage, 'communityFeedTitle')}</Text>
                      <Text style={dashStyles.panelCardSubtitle} numberOfLines={1}>{t(appLanguage, 'communityFeedSub')}</Text>
                    </View>
                  </View>
                  <View style={[dashStyles.panelBadgePill, { backgroundColor: '#f5f3ff', borderColor: '#ddd6fe' }]}>
                    <Text style={[dashStyles.panelBadgeText, { color: '#7c3aed' }]}>{t(appLanguage, 'liveFeedBadge')}</Text>
                  </View>
                </View>

                {loadingDashboard && complaints.length === 0 ? (
                  <View style={{ paddingVertical: 18, alignItems: 'center' }}>
                    <ActivityIndicator size="small" color="#059669" />
                  </View>
                ) : complaints.filter(c => c.status !== 'resolved').length === 0 ? (
                  <View style={dashStyles.emptyCardState}>
                    <Users size={22} color="#94a3b8" />
                    <Text style={dashStyles.emptyStateTitle}>No active community alerts nearby</Text>
                    <Text style={dashStyles.emptyStateDesc}>All reported incidents in this quadrant have been cleared or resolved.</Text>
                  </View>
                ) : (
                  complaints.filter(c => c.status !== 'resolved').slice(0, 5).map((c, index) => (
                    <View key={c.id ? `feed-${c.id}` : `feed-${index}`} style={dashStyles.modernLogRow}>
                      <View style={dashStyles.modernLogLeft}>
                        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                          <View style={dashStyles.modernLogLocBadge}>
                            <MapPin size={11} color="#0284c7" />
                            <Text style={dashStyles.modernLogLocText}>{c.lat.toFixed(4)}°N, {c.lon.toFixed(4)}°E</Text>
                          </View>
                          <View style={[dashStyles.severityPill, { backgroundColor: c.severity === 'high' ? '#fee2e2' : c.severity === 'medium' ? '#fef3c7' : '#f1f5f9' }]}>
                            <Text style={[dashStyles.severityPillText, { color: c.severity === 'high' ? '#dc2626' : c.severity === 'medium' ? '#d97706' : '#475569' }]}>
                              {(c.severity || 'normal').toUpperCase()}
                            </Text>
                          </View>
                        </View>
                        <Text style={dashStyles.modernLogDesc}>{c.description}</Text>
                      </View>
                      <View style={dashStyles.modernLogRight}>
                        <View style={[dashStyles.statusPill, { backgroundColor: '#ecfdf5', borderColor: '#a7f3d0' }]}>
                          <Text style={[dashStyles.statusPillText, { color: '#059669' }]}>ACTIVE</Text>
                        </View>
                      </View>
                    </View>
                  ))
                )}
              </View>
            </View>
            </ScrollView>
          ) : (
            <ScrollView 
              style={styles.dashboardContainer} 
              contentContainerStyle={{ paddingBottom: 60 }}
              keyboardShouldPersistTaps="handled"
              removeClippedSubviews={false}
              showsVerticalScrollIndicator={true}
            >
              <View style={dashStyles.dashboardInnerContainer}>
                {/* 1. Hero Safety Banner (Clean Card, Matching Citizen Design) */}
                <TouchableOpacity 
                  style={dashStyles.heroBanner} 
                  onPress={() => setActiveTab('map')}
                  activeOpacity={0.9}
                >
                  <Image
                    source={require('./assets/dashboard-hero-banner.jpg')}
                    style={dashStyles.heroBg}
                    resizeMode="cover"
                  />
                </TouchableOpacity>

                {/* 2. Quick Metrics Row: Active Regions, Active Alerts, Actioned Warnings */}
                <View style={dashStyles.metricsRow}>
                  <View style={[dashStyles.metricCard, { backgroundColor: '#f0fdf4', borderColor: '#dcfce7' }]}>
                    <View style={[dashStyles.metricIconBadge, { backgroundColor: '#dcfce7' }]}>
                      <Map size={15} color="#16a34a" />
                    </View>
                    <Text style={dashStyles.metricLabel}>{t(appLanguage, 'activeRegions')}</Text>
                    <Text style={dashStyles.metricValue}>{Object.keys(stats.location_groups).length || 12}</Text>
                    <Text style={[dashStyles.metricTrend, { color: '#16a34a' }]}>↑ +2 new</Text>
                  </View>

                  <View style={[dashStyles.metricCard, { backgroundColor: '#fef2f2', borderColor: '#fee2e2' }]}>
                    <View style={[dashStyles.metricIconBadge, { backgroundColor: '#fee2e2' }]}>
                      <AlertOctagon size={15} color="#ef4444" />
                    </View>
                    <Text style={dashStyles.metricLabel}>{t(appLanguage, 'activeWarnings')}</Text>
                    <Text style={dashStyles.metricValue}>{stats.total_active || 3}</Text>
                    <Text style={[dashStyles.metricTrend, { color: '#dc2626' }]}>↑ +1 pending</Text>
                  </View>

                  <View style={[dashStyles.metricCard, { backgroundColor: '#eff6ff', borderColor: '#dbeafe' }]}>
                    <View style={[dashStyles.metricIconBadge, { backgroundColor: '#dbeafe' }]}>
                      <CheckCircle2 size={15} color="#2563eb" />
                    </View>
                    <Text style={dashStyles.metricLabel}>{t(appLanguage, 'actionedLabel')}</Text>
                    <Text style={dashStyles.metricValue}>{stats.total_resolved || 0}</Text>
                    <Text style={[dashStyles.metricTrend, { color: '#2563eb' }]}>✓ Resolved</Text>
                  </View>
                </View>

                {/* 3. Asymmetric Grid: Interactive Map Card on Left, Action Cards on Right */}
                <View style={dashStyles.gridRow}>
                  {/* Left: Interactive Map Card */}
                  <TouchableOpacity 
                    style={dashStyles.mapCard} 
                    onPress={() => setActiveTab('map')}
                    activeOpacity={0.9}
                  >
                    <View style={dashStyles.mapCardHeader}>
                      <View style={[dashStyles.gridIconBadge, { backgroundColor: '#e0f2fe' }]}>
                        <Map size={15} color="#0284c7" />
                      </View>
                      <View style={{ flex: 1, marginLeft: 8 }}>
                        <Text style={dashStyles.mapCardTitle}>{t(appLanguage, 'interactiveMapTitle')}</Text>
                        <Text style={dashStyles.mapCardDesc} numberOfLines={2}>
                          {t(appLanguage, 'interactiveMapDesc')}
                        </Text>
                      </View>
                      <View style={dashStyles.miniArrowBtn}>
                        <ChevronRight size={13} color="#0284c7" />
                      </View>
                    </View>
                    <View style={dashStyles.mapPreviewContainer}>
                      <Image
                        source={require('./assets/dashboard-map-cropped.jpg')}
                        style={dashStyles.mapPreviewImg}
                        resizeMode="cover"
                      />
                      <View style={dashStyles.mapUpdatedPill}>
                        <Text style={dashStyles.mapUpdatedText}>{t(appLanguage, 'lastUpdated2m')}</Text>
                      </View>
                    </View>
                  </TouchableOpacity>

                  {/* Right: Stacked Official Action Cards (NO RAISE ISSUE) */}
                  <View style={dashStyles.rightCol}>
                    {/* Action Taken / Incident Triage */}
                    <TouchableOpacity 
                      style={dashStyles.actionCardBlue} 
                      onPress={() => setActiveTab('triage')}
                      activeOpacity={0.85}
                    >
                      <View style={dashStyles.actionIconBadgeBlue}>
                        <CheckCircle2 size={16} color="#2563eb" />
                      </View>
                      <Text style={dashStyles.actionTitle}>{t(appLanguage, 'actionTakenQueueTitle')}</Text>
                      <Text style={dashStyles.actionDesc} numberOfLines={2}>
                        {t(appLanguage, 'actionTakenQueueDesc')}
                      </Text>
                      <View style={dashStyles.actionBtnBlue}>
                        <Text style={dashStyles.actionBtnText}>{t(appLanguage, 'takeActionBtn')}</Text>
                      </View>
                    </TouchableOpacity>

                    {/* AI Agent Panel */}
                    <TouchableOpacity 
                      style={dashStyles.actionCardGreen} 
                      onPress={() => setActiveTab('agent')}
                      activeOpacity={0.85}
                    >
                      <View style={dashStyles.actionIconBadgeGreen}>
                        <Cpu size={16} color="#10b981" />
                      </View>
                      <Text style={dashStyles.actionTitle}>{t(appLanguage, 'aiAgentPanelTitle')}</Text>
                      <Text style={dashStyles.actionDesc} numberOfLines={2}>
                        {t(appLanguage, 'aiAgentPanelDesc')}
                      </Text>
                      <View style={dashStyles.actionBtnGreen}>
                        <Text style={dashStyles.actionBtnText}>{t(appLanguage, 'launchAgentBtn')}</Text>
                      </View>
                    </TouchableOpacity>
                  </View>
                </View>

                {/* 4. Active Regional Disaster Brief (Expandable Banner Card) */}
                <TouchableOpacity 
                  style={dashStyles.briefCard} 
                  onPress={() => setShowReportModal(true)}
                  activeOpacity={0.85}
                >
                  <View style={dashStyles.briefIconBadge}>
                    <FileText size={18} color="#2563eb" />
                  </View>
                  <View style={dashStyles.briefTextCol}>
                    <Text style={dashStyles.briefTitle}>{t(appLanguage, 'regionalBriefTitle')}</Text>
                    <Text style={dashStyles.briefDesc}>
                      {t(appLanguage, 'regionalBriefDesc')}
                    </Text>
                  </View>
                  <ChevronRight size={18} color="#94a3b8" />
                </TouchableOpacity>

                {/* 5. Aegis Intelligent Assistant */}
                {renderChatbot()}

                {/* 6. Official Action Center: Ranked Incident Queue & Field Reports */}
                <View style={dashStyles.panelCard}>
                  <View style={dashStyles.panelCardHeader}>
                    <View style={dashStyles.panelCardHeaderLeft}>
                      <View style={[dashStyles.panelIconBadge, { backgroundColor: '#eff6ff', borderColor: '#bfdbfe' }]}>
                        <ShieldAlert size={16} color="#2563eb" />
                      </View>
                      <View style={dashStyles.panelCardTextCol}>
                        <Text style={dashStyles.panelCardTitle} numberOfLines={1}>{t(appLanguage, 'fieldTriageTitle')}</Text>
                        <Text style={dashStyles.panelCardSubtitle} numberOfLines={1}>{t(appLanguage, 'fieldTriageSub')}</Text>
                      </View>
                    </View>
                    <TouchableOpacity 
                      style={{ backgroundColor: '#eff6ff', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8, borderWidth: 1, borderColor: '#bfdbfe' }}
                      onPress={() => fetchDashboardData(true)}
                      activeOpacity={0.7}
                    >
                      <Text style={{ color: '#1e40af', fontSize: 10.5, fontWeight: '700' }}>🔄 Refresh</Text>
                    </TouchableOpacity>
                  </View>

                  {/* District Chips Summary */}
                  {Object.keys(stats.location_groups).length > 0 && (
                    <View style={dashStyles.districtsRow}>
                      {Object.entries(stats.location_groups).map(([loc, count], idx) => (
                        <View key={idx} style={dashStyles.districtChip}>
                          <Text style={dashStyles.districtChipText}>{loc}</Text>
                          <View style={dashStyles.districtCountBadge}>
                            <Text style={dashStyles.districtCountText}>{(count as number)}</Text>
                          </View>
                        </View>
                      ))}
                    </View>
                  )}

                  {/* Queue Status Filter Pills */}
                  <View style={dashStyles.queueFilterRow}>
                    <Text style={{ fontSize: 10.5, color: '#64748b', fontWeight: '600', marginRight: 4 }}>{t(appLanguage, 'filterStatusLabel')}</Text>
                    {['all', 'pending', 'resolved'].map(st => (
                      <TouchableOpacity 
                        key={st} 
                        style={[dashStyles.queueFilterPill, statusFilter === st && dashStyles.queueFilterPillActive]}
                        onPress={() => setStatusFilter(st)}
                        activeOpacity={0.7}
                      >
                        <Text style={[dashStyles.queueFilterText, statusFilter === st && dashStyles.queueFilterTextActive]}>
                          {st.toUpperCase()}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>

                  {/* Incident List */}
                  {loadingDashboard && complaints.length === 0 ? (
                    <View style={{ paddingVertical: 20, alignItems: 'center' }}>
                      <ActivityIndicator size="small" color="#2563eb" />
                    </View>
                  ) : filteredComplaints.length === 0 ? (
                    <View style={dashStyles.emptyCardState}>
                      <Users size={22} color="#94a3b8" />
                      <Text style={dashStyles.emptyStateTitle}>No warnings match active filter</Text>
                      <Text style={dashStyles.emptyStateDesc}>All incidents in this queue are currently cleared or resolved.</Text>
                    </View>
                  ) : (
                    filteredComplaints.map((c, index) => {
                      const matchPercent = c.score 
                        ? Math.round(c.score) 
                        : (c.severity === 'SEVERE' || c.severity === 'CRITICAL' ? 96 : c.severity === 'HIGH' ? 86 : c.severity === 'MODERATE' ? 78 : 55);
                      const formattedTime = c.timestamp 
                        ? `${new Date(c.timestamp * 1000).toLocaleDateString([], { month: 'short', day: 'numeric' })}, ${new Date(c.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` 
                        : 'Just now';
                      const displayPlace = c.location_name ? c.location_name : `${c.lat.toFixed(4)}°N, ${c.lon.toFixed(4)}°E`;

                      return (
                        <View key={c.id ? `ranked-${c.id}` : `ranked-${index}`} style={dashStyles.rankedCardModern}>
                          <View style={dashStyles.rankedTopRow}>
                            <View style={dashStyles.rankedMatchBadge}>
                              <Text style={dashStyles.rankedMatchText}>{matchPercent}% Match</Text>
                            </View>
                            <View style={dashStyles.modernLogLocBadge}>
                              <MapPin size={11} color="#0284c7" />
                              <Text style={dashStyles.modernLogLocText}>{displayPlace}</Text>
                            </View>
                            <View style={[dashStyles.severityPill, { backgroundColor: c.severity === 'SEVERE' || c.severity === 'CRITICAL' ? '#fee2e2' : c.severity === 'HIGH' ? '#ffedd5' : '#fef3c7' }]}>
                              <Text style={[dashStyles.severityPillText, { color: c.severity === 'SEVERE' || c.severity === 'CRITICAL' ? '#dc2626' : c.severity === 'HIGH' ? '#ea580c' : '#d97706' }]}>
                                {c.severity}
                              </Text>
                            </View>
                          </View>

                           <Text style={[dashStyles.modernLogDesc, { fontSize: 11.5, color: '#334155', marginBottom: 4 }]}>{c.description}</Text>
                          {c.image_b64 ? (
                            <View style={{ marginBottom: 8, borderRadius: 10, overflow: 'hidden', borderWidth: 1, borderColor: '#cbd5e1' }}>
                              <Image source={{ uri: c.image_b64 }} style={{ width: '100%', height: 120 }} resizeMode="cover" />
                              <View style={{ backgroundColor: 'rgba(15, 23, 42, 0.72)', paddingHorizontal: 8, paddingVertical: 3 }}>
                                <Text style={{ color: '#ffffff', fontSize: 9.5, fontWeight: '700' }}>📷 Attached Ground Photo Verification</Text>
                              </View>
                            </View>
                          ) : null}
                          <Text style={{ fontSize: 9.5, color: '#64748b', marginBottom: 8 }}>
                            👤 Reporter: @{c.username} • 🕒 {formattedTime} • Status: <Text style={{ fontWeight: '700', color: c.status === 'resolved' ? '#059669' : '#d97706' }}>{c.status?.toUpperCase()}</Text>
                          </Text>

                          {c.status === 'pending' ? (
                            <View style={{ marginTop: 4 }}>
                              <TouchableOpacity 
                                style={[styles.actionSelectorBtn, { backgroundColor: '#f1f5f9', borderColor: '#cbd5e1' }]}
                                onPress={() => setExpandedComplaintId(expandedComplaintId === c.id ? null : c.id!)}
                                activeOpacity={0.8}
                              >
                                <Text style={[styles.actionSelectorBtnText, { color: '#1e40af' }]}>
                                  {expandedComplaintId === c.id ? "▲ Close Action Menu" : "⚡ Take Action... (Options Menu)"}
                                </Text>
                              </TouchableOpacity>

                              {expandedComplaintId === c.id && (
                                <View style={[styles.actionMenuContainer, { borderColor: '#bfdbfe', borderRadius: 12 }]}>
                                  <TouchableOpacity 
                                    style={styles.actionMenuItem}
                                    onPress={() => {
                                      setExpandedComplaintId(null);
                                      setActiveTab('map');
                                      handleLocationSelected(
                                        {
                                          confidence_score: 87.5,
                                          classification: "Flood",
                                          area_sq_km: 2.5,
                                          severity: c.severity,
                                          severity_score: c.score || 80,
                                          impact: { population: 3000, buildings: 120, facilities: 2 },
                                          mask_geojson: null
                                        },
                                        c.lat,
                                        c.lon
                                      );
                                    }}
                                  >
                                    <Compass size={14} color="#2563eb" />
                                    <Text style={styles.actionMenuText}>🛰️ Analyze Satellite Imagery & Flow</Text>
                                  </TouchableOpacity>

                                  <TouchableOpacity 
                                    style={styles.actionMenuItem}
                                    onPress={() => handleVoiceCallTrigger(DEFAULT_DEMO_PHONE_E164, c.severity, displayPlace)}
                                  >
                                    <PhoneCall size={14} color="#dc2626" />
                                    <Text style={styles.actionMenuText}>📞 Trigger Twilio Voice Alert Call (+917678656930)</Text>
                                  </TouchableOpacity>

                                  <TouchableOpacity 
                                    style={styles.actionMenuItem}
                                    onPress={() => handleEmailReportTrigger(c)}
                                  >
                                    <Mail size={14} color="#2563eb" />
                                    <Text style={styles.actionMenuText}>📧 Send LLM RAG Situation Report</Text>
                                  </TouchableOpacity>

                                  <TouchableOpacity 
                                    style={styles.actionMenuItem}
                                    onPress={() => handleBroadcastNotification(c)}
                                  >
                                    <Bell size={14} color="#d97706" />
                                    <Text style={styles.actionMenuText}>🔔 Broadcast Push Notification to Users</Text>
                                  </TouchableOpacity>

                                  <TouchableOpacity 
                                    style={styles.actionMenuItem}
                                    onPress={() => handleDeploySDRF(`${c.lat.toFixed(3)}N, ${c.lon.toFixed(3)}E`)}
                                  >
                                    <Users size={14} color="#10b981" />
                                    <Text style={styles.actionMenuText}>🚀 Deploy SDRF Rescue Team</Text>
                                  </TouchableOpacity>

                                  <TouchableOpacity 
                                    style={[styles.actionMenuItem, { borderBottomWidth: 0 }]}
                                    onPress={() => handleResolveComplaint(c.id!)}
                                  >
                                    <Check size={14} color="#059669" />
                                    <Text style={[styles.actionMenuText, { color: '#059669', fontWeight: '800' }]}>✅ Mark Warning Resolved</Text>
                                  </TouchableOpacity>
                                </View>
                              )}
                            </View>
                          ) : (
                            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 4 }}>
                              <View style={[dashStyles.statusPill, { backgroundColor: '#ecfdf5', borderColor: '#a7f3d0' }]}>
                                <Text style={[dashStyles.statusPillText, { color: '#059669' }]}>✓ ACTION TAKEN: RESOLVED</Text>
                              </View>
                            </View>
                          )}
                        </View>
                      );
                    })
                  )}
                </View>
              </View>
            </ScrollView>
          )
        )}

        {activeTab === 'agent' && (
          <AgentPanel 
            lastResult={lastResult} 
            activeLat={activeLat} 
            activeLon={activeLon} 
            onNavigateToMap={() => setActiveTab('map')}
            onOpenReportModal={() => setShowReportModal(true)}
            lang={appLanguage}
          />
        )}

        {activeTab === 'nowcast' && (
          <NowcastPanel
            lat={activeLat}
            lon={activeLon}
            language={appLanguage}
            lastDetectionNowcast={(lastResult as any)?.urnn_nowcast}
          />
        )}

        {activeTab === 'triage' && (
          <TriagePanel />
        )}

        {activeTab === 'settings' && (
          <SettingsPanel />
        )}
      </View>

      {/* Report Viewer & PDF Download Modal */}
      <ReportViewerModal
        visible={showReportModal}
        onClose={() => setShowReportModal(false)}
        location={lastResult ? `${activeLat.toFixed(2)}°N, ${activeLon.toFixed(2)}°E Scan Zone` : 'Regional Area'}
        lat={activeLat}
        lon={activeLon}
        area={lastResult?.area_sq_km || 12.5}
        classification={lastResult?.classification || 'Inundation'}
        severity={lastResult?.severity || 'HIGH'}
        pop={lastResult?.impact?.population || 12500}
        bld={lastResult?.impact?.buildings || 1850}
        fac={lastResult?.impact?.facilities || 4}
        conf={lastResult?.confidence_score || 94.2}
        pdfDownloadUrl={apiService.getPdfReportDownloadUrl({
          location: lastResult ? `${activeLat.toFixed(2)}°N, ${activeLon.toFixed(2)}°E Scan Zone` : 'Regional Area',
          lat: activeLat,
          lon: activeLon,
          area: lastResult?.area_sq_km || 12.5,
          classification: lastResult?.classification || 'Inundation',
          severity: lastResult?.severity || 'HIGH',
          pop: lastResult?.impact?.population || 12500,
          bld: lastResult?.impact?.buildings || 1850,
          fac: lastResult?.impact?.facilities || 4,
          conf: lastResult?.confidence_score || 94.2
        })}
      />

      {/* Navigation Tab Bar — 6 Tabs including 4D Nowcast (P32, P35) */}
      <View style={dashStyles.tabBar}>
        <TouchableOpacity 
          style={dashStyles.tabItem}
          onPress={() => setActiveTab('report')}
          activeOpacity={0.7}
        >
          <Home size={20} color={activeTab === 'report' ? '#059669' : '#94a3b8'} />
          <Text style={[dashStyles.tabLabel, activeTab === 'report' && dashStyles.tabLabelActive]}>
            {t(appLanguage, 'tabHome')}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity 
          style={dashStyles.tabItem}
          onPress={() => setActiveTab('map')}
          activeOpacity={0.7}
        >
          <Map size={20} color={activeTab === 'map' ? '#059669' : '#94a3b8'} />
          <Text style={[dashStyles.tabLabel, activeTab === 'map' && dashStyles.tabLabelActive]}>
            {t(appLanguage, 'tabMap')}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity 
          style={dashStyles.tabItem}
          onPress={() => setActiveTab('nowcast')}
          activeOpacity={0.7}
        >
          <Waves size={20} color={activeTab === 'nowcast' ? '#2563eb' : '#94a3b8'} />
          <Text style={[dashStyles.tabLabel, activeTab === 'nowcast' && { color: '#2563eb', fontWeight: '700' }]}>
            {t(appLanguage, 'tabNowcast')}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity 
          style={dashStyles.tabItem}
          onPress={() => setActiveTab('agent')}
          activeOpacity={0.7}
        >
          <Cpu size={20} color={activeTab === 'agent' ? '#059669' : '#94a3b8'} />
          <Text style={[dashStyles.tabLabel, activeTab === 'agent' && dashStyles.tabLabelActive]}>
            {t(appLanguage, 'tabAgent')}
          </Text>
        </TouchableOpacity>

        {role === 'official' ? (
          <TouchableOpacity 
            style={dashStyles.tabItem}
            onPress={() => setActiveTab('triage')}
            activeOpacity={0.7}
          >
            <CheckCircle2 size={20} color={activeTab === 'triage' ? '#2563eb' : '#94a3b8'} />
            <Text style={[dashStyles.tabLabel, activeTab === 'triage' && { color: '#2563eb', fontWeight: '700' }]}>
              {t(appLanguage, 'tabTriage')}
            </Text>
          </TouchableOpacity>
        ) : (
          <TouchableOpacity 
            style={dashStyles.tabItem}
            onPress={() => setActiveTab('raise')}
            activeOpacity={0.7}
          >
            <AlertOctagon size={20} color={activeTab === 'raise' ? '#059669' : '#94a3b8'} />
            <Text style={[dashStyles.tabLabel, activeTab === 'raise' && dashStyles.tabLabelActive]}>
              {t(appLanguage, 'tabRaise')}
            </Text>
          </TouchableOpacity>
        )}

        <TouchableOpacity 
          style={dashStyles.tabItem}
          onPress={() => setActiveTab('settings')}
          activeOpacity={0.7}
        >
          <SettingsIcon size={20} color={activeTab === 'settings' ? '#059669' : '#94a3b8'} />
          <Text style={[dashStyles.tabLabel, activeTab === 'settings' && dashStyles.tabLabelActive]}>
            {t(appLanguage, 'tabSettings')}
          </Text>
        </TouchableOpacity>
      </View>


    </SafeAreaView>
  );
}



const styles = StyleSheet.create({
  authErrorBox: {
    backgroundColor: '#fef2f2',
    borderWidth: 1,
    borderColor: '#fca5a5',
    borderRadius: 8,
    padding: 10,
    marginBottom: 16
  },
  authErrorText: {
    color: '#ef4444',
    fontSize: 11,
    fontWeight: 'bold',
    textAlign: 'center'
  },
  loginContainer: {
    flex: 1,
    backgroundColor: '#f8fafc',
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 24
  },
  logoHeader: {
    alignItems: 'center',
    marginBottom: 32
  },
  logoTitle: {
    color: '#0f172a',
    fontSize: 28,
    fontWeight: '900',
    letterSpacing: 3
  },
  logoSubtitle: {
    color: '#64748b',
    fontSize: 12,
    marginTop: 6,
    fontWeight: '600'
  },
  authCard: {
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 24,
    width: '100%',
    borderWidth: 1,
    borderColor: '#e2e8f0',
    shadowColor: '#0f172a',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.05,
    shadowRadius: 10,
    elevation: 3
  },
  authTitle: {
    color: '#0f172a',
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 20,
    textAlign: 'center'
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#ffffff',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#cbd5e1',
    paddingHorizontal: 12,
    height: 42,
    marginBottom: 12
  },
  authInput: {
    flex: 1,
    color: '#0f172a',
    fontSize: 13,
    height: '100%'
  },
  authLabel: {
    color: '#475569',
    fontSize: 12,
    fontWeight: 'bold',
    marginBottom: 8
  },
  roleChoiceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 16
  },
  roleSelectBtn: {
    backgroundColor: '#ffffff',
    borderWidth: 1,
    borderColor: '#cbd5e1',
    borderRadius: 8,
    height: 38,
    width: '48%',
    justifyContent: 'center',
    alignItems: 'center'
  },
  roleSelectBtnText: {
    color: '#64748b',
    fontSize: 11,
    fontWeight: '600'
  },
  authSubmitBtn: {
    backgroundColor: '#2563eb',
    borderRadius: 8,
    height: 42,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 8,
    shadowColor: '#2563eb',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 5
  },
  authSubmitBtnText: {
    color: '#ffffff',
    fontSize: 14,
    fontWeight: 'bold'
  },
  authToggleBtn: {
    marginTop: 16,
    alignItems: 'center'
  },
  authToggleBtnText: {
    color: '#2563eb',
    fontSize: 12,
    fontWeight: '600'
  },
  safeContainer: {
    flex: 1,
    backgroundColor: '#f8fafc',
    position: 'relative'
  },
  appHeader: {
    height: 56,
    backgroundColor: '#ffffff',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#e2e8f0'
  },
  headerTitleCol: {
    flexDirection: 'column'
  },
  headerTitle: {
    color: '#0f172a',
    fontSize: 15,
    fontWeight: '900',
    letterSpacing: 1
  },
  headerSubtitle: {
    color: '#64748b',
    fontSize: 10
  },
  headerRightCol: {
    flexDirection: 'row',
    alignItems: 'center'
  },
  badge: {
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderWidth: 1,
    marginRight: 10
  },
  badgeText: {
    fontSize: 8,
    fontWeight: '900'
  },
  logoutBtn: {
    padding: 6
  },
  contentBody: {
    flex: 1
  },
  dashboardContainer: {
    flex: 1,
    backgroundColor: '#f8fafc',
    paddingHorizontal: 16,
    paddingTop: 16,
    ...Platform.select({
      web: {
        overflowY: 'auto'
      } as any
    })
  },
  hubGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 16,
    flexWrap: 'wrap'
  },
  hubCard: {
    width: '48%',
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 14,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    flexDirection: 'column',
    alignItems: 'flex-start',
    shadowColor: '#0f172a',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 1
  },
  hubIconBg: {
    width: 36,
    height: 36,
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 10
  },
  hubTextCol: {
    flexDirection: 'column'
  },
  hubCardTitle: {
    color: '#0f172a',
    fontSize: 12,
    fontWeight: 'bold',
    marginBottom: 4
  },
  hubCardDesc: {
    color: '#64748b',
    fontSize: 9,
    lineHeight: 12
  },
  notificationToast: {
    position: 'absolute',
    top: 10,
    left: 16,
    right: 16,
    borderRadius: 12,
    borderWidth: 1,
    padding: 12,
    flexDirection: 'row',
    alignItems: 'center',
    shadowColor: '#0f172a',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 6,
    zIndex: 9999
  },
  toastTitle: {
    fontSize: 12,
    fontWeight: 'bold'
  },
  toastMessage: {
    fontSize: 10,
    marginTop: 2,
    lineHeight: 13
  },
  chatbotContainer: {
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    marginBottom: 16,
    shadowColor: '#0f172a',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 1
  },
  chatbotHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12
  },
  chatbotTitle: {
    color: '#0f172a',
    fontSize: 13,
    fontWeight: 'bold',
    marginLeft: 6
  },
  chatHistoryScroll: {
    maxHeight: 140,
    marginBottom: 12,
    backgroundColor: '#f8fafc',
    borderRadius: 8,
    padding: 10,
    borderWidth: 1,
    borderColor: '#e2e8f0'
  },
  chatBubbleGroup: {
    marginBottom: 8
  },
  userBubble: {
    alignSelf: 'flex-end',
    backgroundColor: '#dbeafe',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 8,
    maxWidth: '80%'
  },
  userBubbleText: {
    color: '#1e40af',
    fontSize: 11,
    fontWeight: '500'
  },
  botBubble: {
    alignSelf: 'flex-start',
    backgroundColor: '#d1fae5',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 8,
    maxWidth: '80%',
    marginTop: 4
  },
  botBubbleText: {
    color: '#065f46',
    fontSize: 11,
    lineHeight: 15
  },
  chatInputRow: {
    flexDirection: 'row',
    alignItems: 'center'
  },
  chatInput: {
    flex: 1,
    backgroundColor: '#ffffff',
    color: '#0f172a',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#cbd5e1',
    paddingHorizontal: 12,
    fontSize: 11,
    height: 38,
    marginRight: 8
  },
  chatSendBtn: {
    backgroundColor: '#2563eb',
    borderRadius: 8,
    paddingHorizontal: 14,
    height: 38,
    justifyContent: 'center',
    alignItems: 'center'
  },
  chatSendText: {
    color: '#ffffff',
    fontSize: 11,
    fontWeight: 'bold'
  },
  testAlertBtn: {
    backgroundColor: '#ef4444',
    borderRadius: 10,
    height: 38,
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16
  },
  testAlertText: {
    color: '#ffffff',
    fontSize: 11,
    fontWeight: 'bold'
  },
  emailConfigInput: {
    backgroundColor: '#ffffff',
    color: '#0f172a',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#cbd5e1',
    paddingHorizontal: 12,
    height: 38,
    fontSize: 11
  },
  panelCard: {
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    marginBottom: 16,
    shadowColor: '#0f172a',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 1
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10
  },
  cardTitle: {
    color: '#0f172a',
    fontSize: 13,
    fontWeight: 'bold',
    marginLeft: 8
  },
  helperText: {
    color: '#64748b',
    fontSize: 11,
    marginBottom: 12,
    lineHeight: 15
  },
  noDataText: {
    color: '#64748b',
    fontSize: 11,
    textAlign: 'center',
    paddingVertical: 10
  },
  alertItem: {
    borderBottomWidth: 1,
    borderBottomColor: '#f1f5f9',
    paddingVertical: 10
  },
  alertItemTime: {
    color: '#ef4444',
    fontSize: 9,
    fontWeight: 'bold',
    marginBottom: 2
  },
  alertItemText: {
    color: '#334155',
    fontSize: 11,
    lineHeight: 15
  },
  logRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottomWidth: 1,
    borderBottomColor: '#f1f5f9',
    paddingVertical: 12
  },
  logRowLeft: {
    flex: 1.8,
    paddingRight: 8
  },
  logLocation: {
    color: '#0f172a',
    fontSize: 12,
    fontWeight: 'bold'
  },
  logDesc: {
    color: '#64748b',
    fontSize: 10,
    marginTop: 2
  },
  logRowRight: {
    flex: 1,
    alignItems: 'flex-end'
  },
  statusTag: {
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
    marginBottom: 4
  },
  statusText: {
    fontSize: 8,
    fontWeight: 'bold'
  },
  logModelStatus: {
    color: '#10b981',
    fontSize: 9,
    fontWeight: 'bold'
  },
  statsCardRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 16
  },
  statBox: {
    width: '48%',
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    alignItems: 'center',
    shadowColor: '#0f172a',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 1
  },
  statNumber: {
    fontSize: 32,
    color: '#f59e0b',
    fontWeight: '900'
  },
  statLabel: {
    color: '#64748b',
    fontSize: 10,
    marginTop: 4
  },
  groupRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#f1f5f9'
  },
  groupLocName: {
    color: '#334155',
    fontSize: 12
  },
  groupCountBadge: {
    backgroundColor: '#dbeafe',
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 2
  },
  groupCountText: {
    color: '#1e40af',
    fontSize: 9,
    fontWeight: 'bold'
  },
  filterCard: {
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 12,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    marginBottom: 16,
    shadowColor: '#0f172a',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 1
  },
  filterHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10
  },
  filterTitle: {
    color: '#475569',
    fontSize: 11,
    fontWeight: 'bold',
    marginLeft: 6
  },
  filterOptionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8
  },
  filterLabelSmall: {
    color: '#64748b',
    fontSize: 11,
    width: 60
  },
  filterBtn: {
    backgroundColor: '#f8fafc',
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 5,
    marginRight: 6,
    borderWidth: 1,
    borderColor: '#e2e8f0'
  },
  filterBtnActive: {
    backgroundColor: '#2563eb',
    borderColor: '#2563eb'
  },
  filterBtnText: {
    color: '#64748b',
    fontSize: 9,
    fontWeight: 'bold'
  },
  filterBtnTextActive: {
    color: '#ffffff'
  },
  rankedRow: {
    backgroundColor: '#f8fafc',
    borderRadius: 10,
    padding: 12,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    marginBottom: 12
  },
  rankedRowTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 6
  },
  rankedBadge: {
    backgroundColor: '#f3e8ff',
    borderColor: '#c084fc',
    borderWidth: 0.5,
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2
  },
  rankedBadgeText: {
    color: '#6b21a8',
    fontSize: 9,
    fontWeight: 'bold'
  },
  rankedLocText: {
    color: '#0f172a',
    fontSize: 11,
    fontWeight: 'bold'
  },
  rankedSevText: {
    fontSize: 10,
    fontWeight: 'bold'
  },
  rankedDesc: {
    color: '#475569',
    fontSize: 11,
    lineHeight: 15,
    marginBottom: 6
  },
  reporterName: {
    color: '#64748b',
    fontSize: 9,
    marginBottom: 10
  },
  actionSelectorBtn: {
    backgroundColor: '#ffffff',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#cbd5e1',
    height: 36,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 8
  },
  actionSelectorBtnText: {
    color: '#0f172a',
    fontSize: 11,
    fontWeight: 'bold'
  },
  actionMenuContainer: {
    backgroundColor: '#ffffff',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#cbd5e1',
    padding: 8,
    marginTop: 8,
    shadowColor: '#0f172a',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 5
  },
  actionMenuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#f1f5f9',
    paddingHorizontal: 8
  },
  actionMenuText: {
    color: '#334155',
    fontSize: 11,
    fontWeight: 'bold',
    marginLeft: 10
  },
  reportBulletin: {
    paddingVertical: 4
  },
  reportSummaryTitle: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#0f172a'
  },
  reportSummaryMeta: {
    fontSize: 10,
    color: '#64748b',
    marginTop: 2
  },
  reportDivider: {
    height: 1,
    backgroundColor: '#cbd5e1',
    marginVertical: 10
  },
  reportSectionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 8
  },
  reportSectionIconBg: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#f8fafc',
    borderWidth: 1,
    borderColor: '#cbd5e1',
    justifyContent: 'center',
    alignItems: 'center'
  },
  reportSectionLabel: {
    fontSize: 9,
    fontWeight: 'bold',
    color: '#475569'
  },
  reportSectionValue: {
    fontSize: 11,
    fontWeight: 'bold',
    color: '#0f172a',
    marginTop: 2
  },
  reportProgressBarBg: {
    height: 6,
    backgroundColor: '#cbd5e1',
    borderRadius: 3,
    marginTop: 6,
    overflow: 'hidden'
  },
  reportProgressBar: {
    height: '100%'
  },
  infraStatusRow: {
    marginTop: 4
  },
  infraStatusDot: {
    fontSize: 10,
    fontWeight: 'bold',
    marginVertical: 2
  },
  recommendationsBlock: {
    backgroundColor: '#fef2f2',
    borderRadius: 8,
    padding: 10,
    marginTop: 12,
    borderWidth: 1,
    borderColor: '#fca5a5'
  },
  recommendationsTitle: {
    fontSize: 10,
    fontWeight: 'bold',
    color: '#991b1b'
  },
  recommendationsText: {
    fontSize: 10,
    color: '#7f1d1d',
    marginTop: 4,
    lineHeight: 14
  },
  tabBar: {
    height: 60,
    backgroundColor: '#ffffff',
    borderTopWidth: 1,
    borderTopColor: '#e2e8f0',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
    paddingBottom: 6
  },
  tabItem: {
    alignItems: 'center',
    justifyContent: 'center',
    flex: 1,
    height: '100%',
    paddingTop: 8
  },
  tabActive: {
    borderTopWidth: 3,
    borderTopColor: '#2563eb'
  },
  tabLabel: {
    color: '#64748b',
    fontSize: 10,
    marginTop: 4,
    fontWeight: '500'
  },
  tabLabelActive: {
    fontWeight: 'bold',
    color: '#2563eb'
  }
});

const authStyles = StyleSheet.create({
  backgroundImage: {
    flex: 1,
    width: '100%',
    minHeight: '100%',
    backgroundColor: '#8bbfe8',
    overflow: 'hidden',
  },
  backgroundImageLayer: {
    width: '100%',
    height: '112%',
    top: -55,
  },
  backgroundWash: {
    flex: 1,
    backgroundColor: 'rgba(229, 243, 255, 0.04)',
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'flex-end',
    alignItems: 'center',
    paddingHorizontal: 0,
    paddingTop: 308,
    paddingBottom: 40,
  },
  brandingSection: {
    height: 0,
  },
  logoIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: 'rgba(255,255,255,0.35)',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
    shadowColor: '#a855f7',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 12,
    elevation: 6,
  },
  brandTitle: {
    fontSize: 32,
    fontWeight: '900',
    color: '#ffffff',
    letterSpacing: 6,
    textShadowColor: 'rgba(120, 60, 180, 0.3)',
    textShadowOffset: { width: 0, height: 2 },
    textShadowRadius: 8,
  },
  brandSubtitle: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.85)',
    marginTop: 4,
    fontWeight: '600',
    letterSpacing: 0.5,
  },
  card: {
    backgroundColor: 'rgba(255,255,255,0.97)',
    borderRadius: 32,
    paddingHorizontal: 28,
    paddingTop: 24,
    paddingBottom: 30,
    width: '88%',
    maxWidth: 620,
    minHeight: 500,
    marginBottom: 40,
    shadowColor: '#365982',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.14,
    shadowRadius: 24,
    elevation: 8,
    position: 'relative',
  },
  handleArea: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 4,
    paddingBottom: 8,
    marginTop: -10,
    marginBottom: 4,
    width: '100%',
  },
  handleBar: {
    width: 44,
    height: 5,
    borderRadius: 3,
    backgroundColor: '#cbd8e9',
  },
  tabRow: {
    flexDirection: 'row',
    backgroundColor: '#f3f0fa',
    borderRadius: 14,
    padding: 4,
    marginBottom: 24,
  },
  tab: {
    flex: 1,
    height: 40,
    borderRadius: 11,
    justifyContent: 'center',
    alignItems: 'center',
  },
  tabActive: {
    backgroundColor: '#ffffff',
    shadowColor: '#a855f7',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.12,
    shadowRadius: 6,
    elevation: 3,
  },
  tabText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#9ca3af',
  },
  tabTextActive: {
    color: '#7c3aed',
    fontWeight: '700',
  },
  formTitle: {
    fontSize: 26,
    fontWeight: '700',
    color: '#1a1a2e',
    textAlign: 'center',
    marginBottom: 8,
    letterSpacing: -0.5,
  },
  formSubtitle: {
    fontSize: 13.5,
    color: '#7a8aa5',
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 24,
    letterSpacing: 0.1,
  },
  errorBox: {
    backgroundColor: '#fef2f2',
    borderWidth: 1,
    borderColor: '#fca5a5',
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    marginBottom: 16,
  },
  errorText: {
    color: '#dc2626',
    fontSize: 12,
    fontWeight: '600',
    textAlign: 'center',
  },
  fieldLabel: {
    fontSize: 12.5,
    fontWeight: '600',
    color: '#3d4f6e',
    marginBottom: 6,
    marginLeft: 2,
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#f8fbff',
    borderRadius: 18,
    borderWidth: 1,
    borderColor: '#d5e3f5',
    paddingHorizontal: 16,
    height: 56,
    marginBottom: 18,
  },
  input: {
    flex: 1,
    color: '#173464',
    fontSize: 15,
    height: '100%',
  },
  roleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 10,
    marginBottom: 16,
  },
  roleBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#f8f7fc',
    borderWidth: 1.5,
    borderColor: '#ebe8f4',
    borderRadius: 14,
    height: 46,
  },
  roleBtnActive: {
    backgroundColor: '#8b5cf6',
    borderColor: '#8b5cf6',
  },
  roleBtnActiveBlue: {
    backgroundColor: '#6366f1',
    borderColor: '#6366f1',
  },
  roleBtnText: {
    fontSize: 12.5,
    fontWeight: '600',
    color: '#6b7bc8',
  },
  roleBtnTextActive: {
    color: '#ffffff',
  },
  checkRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  checkbox: {
    width: 20,
    height: 20,
    borderRadius: 5,
    borderWidth: 1.5,
    borderColor: '#afc5e4',
    backgroundColor: '#ffffff',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 8,
  },
  checkboxChecked: {
    backgroundColor: '#4785f6',
    borderColor: '#4785f6',
  },
  checkLabel: {
    fontSize: 12,
    color: '#5a7098',
    fontWeight: '500',
  },
  linkText: {
    color: '#256df1',
    fontWeight: '600',
  },
  rememberRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
    marginTop: -4,
  },
  forgotText: {
    fontSize: 12,
    color: '#256df1',
    fontWeight: '600',
  },
  submitBtn: {
    borderRadius: 22,
    overflow: 'hidden',
    marginTop: 16,
    shadowColor: '#4c8ff0',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.3,
    shadowRadius: 14,
    elevation: 6,
  },
  submitGradient: {
    height: 60,
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
  },
  submitText: {
    color: '#ffffff',
    fontSize: 15,
    fontWeight: '600',
    letterSpacing: 0.3,
  },
  dividerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 20,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: '#ccdcef',
  },
  dividerText: {
    fontSize: 11.5,
    color: '#8a9bb5',
    marginHorizontal: 12,
    fontWeight: '500',
  },
  socialRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 12,
  },
  socialBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    height: 58,
    borderRadius: 22,
    borderWidth: 1,
    borderColor: '#d5e3f5',
    backgroundColor: '#ffffff',
  },
  socialIcon: {
    fontSize: 18,
    fontWeight: '700',
    marginRight: 8,
    color: '#1b2c60',
  },
  googleIcon: {
    color: '#4285f4',
  },
  socialImage: {
    width: 23,
    height: 23,
    marginRight: 8,
  },
  socialBtnText: {
    fontSize: 13.5,
    fontWeight: '600',
    color: '#2a3a5c',
  },
  toggleRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 20,
  },
  toggleText: {
    fontSize: 13,
    color: '#6b7fa0',
    fontWeight: '500',
  },
  toggleLink: {
    fontSize: 13,
    color: '#256df1',
    fontWeight: '600',
  },
  serverToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 16,
    paddingVertical: 4,
  },
  serverToggleText: {
    color: '#7891b3',
    fontSize: 11,
    fontWeight: '500',
  },
  serverConfigBox: {
    marginTop: 10,
    padding: 12,
    backgroundColor: '#f8f7fc',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#ebe8f4',
  },
  serverConfigLabel: {
    fontSize: 11,
    color: '#6b6b88',
    fontWeight: '700',
    marginBottom: 6,
  },
  backButton: {
    width: 50,
    height: 50,
    borderRadius: 25,
    borderWidth: 1,
    borderColor: '#e1ebf8',
    backgroundColor: '#ffffff',
    alignItems: 'center',
    justifyContent: 'center',
    position: 'absolute',
    top: -150,
    left: 4,
    shadowColor: '#4b6584',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.14,
    shadowRadius: 12,
    elevation: 6,
  },
});


const dashStyles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingTop: Platform.OS === 'web' ? 14 : 10,
    paddingBottom: 12,
    backgroundColor: '#ffffff',
    borderBottomWidth: 1,
    borderBottomColor: '#f1f5f9',
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  headerLogoBadge: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: '#059669',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#059669',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.25,
    shadowRadius: 6,
    elevation: 4,
  },
  headerBrand: {
    fontSize: 18,
    fontWeight: '800',
    color: '#0f172a',
    letterSpacing: -0.3,
  },
  headerSlogan: {
    fontSize: 10.5,
    color: '#64748b',
    fontWeight: '500',
    marginTop: 1,
  },
  headerRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  rolePill: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
    borderWidth: 1,
  },
  rolePillText: {
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  headerIconBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#f8fafc',
    borderWidth: 1,
    borderColor: '#e2e8f0',
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative',
  },
  unreadDot: {
    position: 'absolute',
    top: 7,
    right: 8,
    width: 7,
    height: 7,
    borderRadius: 3.5,
    backgroundColor: '#ef4444',
    borderWidth: 1.5,
    borderColor: '#ffffff',
  },
  avatarBtn: {
    padding: 2,
  },
  avatarCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#ecfdf5',
    borderWidth: 1.5,
    borderColor: '#a7f3d0',
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarInitial: {
    fontSize: 14,
    fontWeight: '800',
    color: '#059669',
  },
  dashboardInnerContainer: {
    width: '100%',
    maxWidth: 1080,
    alignSelf: 'center',
  },
  heroBanner: {
    marginTop: 6,
    marginBottom: 16,
    borderRadius: 22,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: '#d1fae5',
    shadowColor: '#059669',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 10,
    elevation: 3,
    backgroundColor: '#ffffff',
    width: '100%',
    aspectRatio: 2.0,
    maxHeight: 260,
  },
  heroBg: {
    width: '100%',
    height: '100%',
    borderRadius: 22,
  },
  heroImage: {
    borderRadius: 22,
  },
  metricsRow: {
    flexDirection: 'row',
    marginBottom: 14,
    gap: 10,
  },
  metricCard: {
    flex: 1,
    borderRadius: 18,
    borderWidth: 1,
    padding: 11,
    shadowColor: '#0f172a',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.03,
    shadowRadius: 6,
    elevation: 1,
  },
  metricIconBadge: {
    width: 28,
    height: 28,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 6,
  },
  metricLabel: {
    fontSize: 10.5,
    color: '#475569',
    fontWeight: '600',
  },
  metricValue: {
    fontSize: 17,
    fontWeight: '800',
    color: '#0f172a',
    marginVertical: 2,
    letterSpacing: -0.3,
  },
  metricTrend: {
    fontSize: 10,
    fontWeight: '700',
  },
  gridRow: {
    flexDirection: 'row',
    marginBottom: 14,
    gap: 10,
  },
  mapCard: {
    flex: 1.15,
    backgroundColor: '#ffffff',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    overflow: 'hidden',
    shadowColor: '#0f172a',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  mapCardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 10,
  },
  gridIconBadge: {
    width: 26,
    height: 26,
    borderRadius: 7,
    alignItems: 'center',
    justifyContent: 'center',
  },
  mapCardTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: '#0f172a',
  },
  mapCardDesc: {
    fontSize: 9,
    color: '#64748b',
    lineHeight: 11.5,
    marginTop: 2,
  },
  miniArrowBtn: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: '#f0f9ff',
    alignItems: 'center',
    justifyContent: 'center',
  },
  mapPreviewContainer: {
    height: 195,
    width: '100%',
    position: 'relative',
    backgroundColor: '#f1f5f9',
  },
  mapPreviewImg: {
    width: '100%',
    height: '100%',
  },
  mapUpdatedPill: {
    position: 'absolute',
    bottom: 6,
    left: 6,
    backgroundColor: 'rgba(255, 255, 255, 0.94)',
    borderRadius: 12,
    paddingHorizontal: 7,
    paddingVertical: 3,
    flexDirection: 'row',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 3,
    elevation: 2,
  },
  liveGreenDot: {
    width: 5,
    height: 5,
    borderRadius: 2.5,
    backgroundColor: '#10b981',
    marginRight: 4,
  },
  mapUpdatedText: {
    fontSize: 8.5,
    fontWeight: '600',
    color: '#0f172a',
  },
  rightCol: {
    flex: 1,
    justifyContent: 'space-between',
  },
  actionCardRed: {
    backgroundColor: '#fff5f5',
    borderWidth: 1,
    borderColor: '#fee2e2',
    borderRadius: 18,
    padding: 10,
    marginBottom: 8,
    shadowColor: '#ef4444',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 1,
  },
  actionIconBadgeRed: {
    width: 26,
    height: 26,
    borderRadius: 7,
    backgroundColor: '#fee2e2',
    alignItems: 'center',
    justifyContent: 'center',
  },
  actionCardGreen: {
    backgroundColor: '#f0fdf4',
    borderWidth: 1,
    borderColor: '#dcfce7',
    borderRadius: 18,
    padding: 10,
    shadowColor: '#10b981',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 1,
  },
  actionIconBadgeGreen: {
    width: 26,
    height: 26,
    borderRadius: 7,
    backgroundColor: '#dcfce7',
    alignItems: 'center',
    justifyContent: 'center',
  },
  actionTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: '#0f172a',
    marginTop: 5,
  },
  actionDesc: {
    fontSize: 9,
    color: '#64748b',
    lineHeight: 12,
    marginTop: 2,
    marginBottom: 6,
  },
  actionBtnRed: {
    backgroundColor: '#ef4444',
    borderRadius: 12,
    paddingVertical: 4.5,
    paddingHorizontal: 8,
    alignItems: 'center',
  },
  actionBtnGreen: {
    backgroundColor: '#10b981',
    borderRadius: 12,
    paddingVertical: 4.5,
    paddingHorizontal: 8,
    alignItems: 'center',
  },
  actionBtnText: {
    color: '#ffffff',
    fontSize: 10,
    fontWeight: '700',
  },
  actionCardBlue: {
    backgroundColor: '#eff6ff',
    borderWidth: 1,
    borderColor: '#dbeafe',
    borderRadius: 18,
    padding: 10,
    marginBottom: 8,
    shadowColor: '#2563eb',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 1,
  },
  actionIconBadgeBlue: {
    width: 26,
    height: 26,
    borderRadius: 7,
    backgroundColor: '#dbeafe',
    alignItems: 'center',
    justifyContent: 'center',
  },
  actionBtnBlue: {
    backgroundColor: '#2563eb',
    borderRadius: 12,
    paddingVertical: 4.5,
    paddingHorizontal: 8,
    alignItems: 'center',
  },
  districtsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 12,
  },
  districtChip: {
    backgroundColor: '#f1f5f9',
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 3.5,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  districtChipText: {
    fontSize: 10,
    fontWeight: '600',
    color: '#334155',
  },
  districtCountBadge: {
    backgroundColor: '#dbeafe',
    borderRadius: 8,
    paddingHorizontal: 5,
    paddingVertical: 1,
  },
  districtCountText: {
    fontSize: 9,
    fontWeight: '700',
    color: '#1d4ed8',
  },
  queueFilterRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 12,
  },
  queueFilterPill: {
    paddingHorizontal: 11,
    paddingVertical: 4.5,
    borderRadius: 8,
    backgroundColor: '#f8fafc',
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  queueFilterPillActive: {
    backgroundColor: '#2563eb',
    borderColor: '#2563eb',
  },
  queueFilterText: {
    fontSize: 9.5,
    fontWeight: '700',
    color: '#64748b',
  },
  queueFilterTextActive: {
    color: '#ffffff',
  },
  rankedCardModern: {
    backgroundColor: '#f8fafc',
    borderRadius: 14,
    padding: 12,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    marginBottom: 10,
  },
  rankedTopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 6,
    flexWrap: 'wrap',
    gap: 6,
  },
  rankedMatchBadge: {
    backgroundColor: '#ecfdf5',
    borderColor: '#a7f3d0',
    borderWidth: 1,
    borderRadius: 6,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  rankedMatchText: {
    fontSize: 9.5,
    fontWeight: '700',
    color: '#059669',
  },
  briefCard: {
    marginBottom: 14,
    backgroundColor: '#ffffff',
    borderRadius: 18,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    padding: 12,
    flexDirection: 'row',
    alignItems: 'center',
    shadowColor: '#0f172a',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 1,
  },
  briefIconBadge: {
    width: 32,
    height: 32,
    borderRadius: 9,
    backgroundColor: '#eff6ff',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  briefTextCol: {
    flex: 1,
  },
  briefTitle: {
    fontSize: 12.5,
    fontWeight: '700',
    color: '#0f172a',
  },
  briefDesc: {
    fontSize: 10,
    color: '#64748b',
    marginTop: 2,
    lineHeight: 13,
  },
  panelCard: {
    backgroundColor: '#ffffff',
    borderRadius: 20,
    padding: 16,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    marginBottom: 16,
    shadowColor: '#0f172a',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  panelCardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
    gap: 8,
  },
  panelCardHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    flex: 1,
    minWidth: 0,
  },
  panelCardTextCol: {
    flex: 1,
    minWidth: 0,
    paddingRight: 6,
  },
  panelIconBadge: {
    width: 34,
    height: 34,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    flexShrink: 0,
  },
  panelCardTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#0f172a',
  },
  panelCardSubtitle: {
    fontSize: 10,
    color: '#64748b',
    marginTop: 1,
  },
  panelBadgePill: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 3.5,
    borderRadius: 12,
    borderWidth: 1,
    flexShrink: 0,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  panelBadgeText: {
    fontSize: 9.5,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  newReportLink: {
    paddingHorizontal: 10,
    paddingVertical: 4.5,
    backgroundColor: '#eff6ff',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#bfdbfe',
    flexShrink: 0,
  },
  newReportLinkText: {
    color: '#2563eb',
    fontSize: 10.5,
    fontWeight: '700',
  },
  activeAlertCard: {
    backgroundColor: '#fef2f2',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#fecaca',
    padding: 14,
  },
  alertCardTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  alertPulsePill: {
    backgroundColor: '#fee2e2',
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: 8,
  },
  alertPulseText: {
    color: '#dc2626',
    fontSize: 9.5,
    fontWeight: '800',
  },
  alertTimeText: {
    color: '#991b1b',
    fontSize: 10,
    fontWeight: '600',
  },
  alertCardMsg: {
    color: '#7f1d1d',
    fontSize: 12,
    lineHeight: 18,
    marginBottom: 10,
  },
  alertActionBtn: {
    backgroundColor: '#dc2626',
    paddingVertical: 7,
    paddingHorizontal: 12,
    borderRadius: 10,
    alignSelf: 'flex-start',
  },
  alertActionBtnText: {
    color: '#ffffff',
    fontSize: 11,
    fontWeight: '700',
  },
  emptyCardState: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 20,
    paddingHorizontal: 16,
    backgroundColor: '#f8fafc',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#f1f5f9',
  },
  emptyStateTitle: {
    fontSize: 12.5,
    fontWeight: '700',
    color: '#334155',
    marginTop: 8,
  },
  emptyStateDesc: {
    fontSize: 11,
    color: '#94a3b8',
    textAlign: 'center',
    marginTop: 3,
    lineHeight: 15,
  },
  modernLogRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#f1f5f9',
  },
  modernLogLeft: {
    flex: 1.8,
    paddingRight: 10,
  },
  modernLogLocBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: '#f0f9ff',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
    alignSelf: 'flex-start',
    marginBottom: 3,
  },
  modernLogLocText: {
    fontSize: 10.5,
    fontWeight: '700',
    color: '#0369a1',
  },
  modernLogDesc: {
    fontSize: 11,
    color: '#475569',
    lineHeight: 15,
  },
  modernLogRight: {
    flex: 1,
    alignItems: 'flex-end',
  },
  statusPill: {
    paddingHorizontal: 7,
    paddingVertical: 2.5,
    borderRadius: 10,
    borderWidth: 1,
    marginBottom: 3,
  },
  statusPillText: {
    fontSize: 9,
    fontWeight: '700',
  },
  aiVerifyTag: {
    fontSize: 9,
    fontWeight: '700',
  },
  severityPill: {
    paddingHorizontal: 5,
    paddingVertical: 1.5,
    borderRadius: 5,
  },
  severityPillText: {
    fontSize: 8.5,
    fontWeight: '800',
  },
  tabBar: {
    height: 62,
    backgroundColor: '#ffffff',
    borderTopWidth: 1,
    borderTopColor: '#f1f5f9',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
    paddingBottom: Platform.OS === 'web' ? 6 : 10,
    paddingTop: 6,
    shadowColor: '#0f172a',
    shadowOffset: { width: 0, height: -3 },
    shadowOpacity: 0.05,
    shadowRadius: 10,
    elevation: 8,
  },
  tabItem: {
    alignItems: 'center',
    justifyContent: 'center',
    flex: 1,
    height: '100%',
  },
  tabLabel: {
    color: '#94a3b8',
    fontSize: 9.5,
    marginTop: 3,
    fontWeight: '600',
  },
  tabLabelActive: {
    color: '#059669',
    fontWeight: '700',
  },
  activeTabIndicator: {
    position: 'absolute',
    bottom: 2,
    width: 28,
    height: 3,
    backgroundColor: '#059669',
    borderRadius: 2,
  },
});

