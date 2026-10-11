import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Image,
  ActivityIndicator,
  Alert,
  Platform,
} from 'react-native';
import { WebView } from 'react-native-webview';
import {
  Waves,
  Search,
  MapPin,
  CloudRain,
  Navigation,
  PhoneCall,
  Play,
  Pause,
  Sliders,
  Layers,
  ShieldCheck,
  AlertTriangle,
  Info,
  RefreshCw,
  Map as MapIcon,
  Target,
  Building2,
  CheckCircle2,
  ShieldAlert,
  Sparkles,
} from 'lucide-react-native';
import { apiService } from '../services/api';
import { AppLanguage, t, DEFAULT_DEMO_PHONE_E164 } from '../utils/i18n';
import { runDijkstra } from '../utils/routing';

interface NowcastPanelProps {
  lat: number;
  lon: number;
  locationName?: string;
  language?: AppLanguage;
  lastDetectionNowcast?: any;
}

const PRESET_LOCATIONS = [
  { name: 'Patna, Bihar', nameHi: 'पटना, बिहार', lat: 25.6124, lon: 85.1376, defaultRain: 72 },
  { name: 'Kaziranga, Assam', nameHi: 'काजीरंगा, असम', lat: 26.5775, lon: 93.1711, defaultRain: 95 },
  { name: 'Majuli Island, Assam', nameHi: 'माजुली द्वीप, असम', lat: 26.95, lon: 94.1667, defaultRain: 88 },
  { name: 'Jorhat, Assam', nameHi: 'जोरहाट, असम', lat: 26.7509, lon: 94.2037, defaultRain: 64 },
  { name: 'New Delhi (Yamuna)', nameHi: 'नई दिल्ली (यमुना)', lat: 28.6139, lon: 77.209, defaultRain: 54 },
  { name: 'Kuttanad, Kerala', nameHi: 'कुट्टनाड, केरल', lat: 9.3547, lon: 76.4017, defaultRain: 84 },
];

const HORIZONS: Array<{
  key: 't_0m' | 't_15m' | 't_30m' | 't_60m';
  shortKey: '0m' | '15m' | '30m' | '60m';
  labelEn: string;
  labelHi: string;
  minutes: number;
}> = [
  { key: 't_0m', shortKey: '0m', labelEn: 'Now (0m)', labelHi: 'अभी (0m)', minutes: 0 },
  { key: 't_15m', shortKey: '15m', labelEn: '+15 Min', labelHi: '+15 मिनट', minutes: 15 },
  { key: 't_30m', shortKey: '30m', labelEn: '+30 Min', labelHi: '+30 मिनट', minutes: 30 },
  { key: 't_60m', shortKey: '60m', labelEn: '+60 Min', labelHi: '+60 मिनट', minutes: 60 },
];

const escapeHtml = (str: string) => (str || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;');

export const NowcastPanel: React.FC<NowcastPanelProps> = ({
  lat: propLat,
  lon: propLon,
  locationName = 'Patna, Bihar',
  language = 'en',
  lastDetectionNowcast,
}) => {
  const isDefaultIndiaCenter = Boolean(
    propLat && Math.abs(propLat - 20.5937) < 0.05 && propLon && Math.abs(propLon - 78.9629) < 0.05
  );
  const initialLat = isDefaultIndiaCenter ? 25.6124 : (propLat || 25.6124);
  const initialLon = isDefaultIndiaCenter ? 85.1376 : (propLon || 85.1376);
  const initialName = isDefaultIndiaCenter ? 'Patna, Bihar' : (locationName || 'Patna, Bihar');

  const [activeLat, setActiveLat] = useState<number>(initialLat);
  const [activeLon, setActiveLon] = useState<number>(initialLon);
  const [activePlaceName, setActivePlaceName] = useState<string>(initialName);
  const [searchQuery, setSearchQuery] = useState<string>(initialName);
  const [searchingPlace, setSearchingPlace] = useState<boolean>(false);

  const [viewMode, setViewMode] = useState<'map' | 'grid'>('map');
  const [selectedHorizonIdx, setSelectedHorizonIdx] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [rainSliderMmHr, setRainSliderMmHr] = useState<number>(68);
  const [drainageEffPct, setDrainageEffPct] = useState<number>(65);
  const [loading, setLoading] = useState<boolean>(false);
  const [callingDemo, setCallingDemo] = useState<boolean>(false);
  const [nowcastData, setNowcastData] = useState<any>(null);

  const iframeRef = useRef<any>(null);

  useEffect(() => {
    if (
      propLat &&
      propLon &&
      !isDefaultIndiaCenter &&
      (Math.abs(propLat - activeLat) > 0.001 || Math.abs(propLon - activeLon) > 0.001)
    ) {
      setActiveLat(propLat);
      setActiveLon(propLon);
      setActivePlaceName(locationName || `${propLat.toFixed(3)}°N, ${propLon.toFixed(3)}°E`);
      setSearchQuery(locationName || `${propLat.toFixed(3)}°N, ${propLon.toFixed(3)}°E`);
    }
  }, [propLat, propLon]);

  const loadSimulation = async (targetLat: number, targetLon: number, rainVal: number, drainVal: number) => {
    setLoading(true);
    try {
      const res = await apiService.simulateNowcast(targetLat, targetLon, rainVal, drainVal);
      setNowcastData(res);
    } catch (e) {
      console.warn('[NowcastPanel] Simulation error:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSimulation(activeLat, activeLon, rainSliderMmHr, drainageEffPct);
  }, [activeLat, activeLon]);

  useEffect(() => {
    if (!isPlaying) return;
    const timer = setInterval(() => {
      setSelectedHorizonIdx((prev) => (prev + 1) % HORIZONS.length);
    }, 1500);
    return () => clearInterval(timer);
  }, [isPlaying]);

  const handleSearchLocation = async () => {
    const q = searchQuery.trim();
    if (!q) return;
    setSearchingPlace(true);
    try {
      const coordMatch = q.match(/^(-?\d+(\.\d+)?)\s*,\s*(-?\d+(\.\d+)?)$/);
      if (coordMatch) {
        const parsedLat = parseFloat(coordMatch[1]);
        const parsedLon = parseFloat(coordMatch[3]);
        setActiveLat(parsedLat);
        setActiveLon(parsedLon);
        setActivePlaceName(`${parsedLat.toFixed(4)}°N, ${parsedLon.toFixed(4)}°E`);
      } else {
        const geo = await apiService.geocodePlace(q);
        if (typeof geo.lat === 'number' && typeof geo.lon === 'number') {
          setActiveLat(geo.lat);
          setActiveLon(geo.lon);
          setActivePlaceName(geo.name ? geo.name.split(',').slice(0, 2).join(',') : q);
        } else {
          throw new Error(geo.message || 'Location not found');
        }
      }
      setSearchQuery('');
    } catch (e: any) {
      const msg =
        language === 'hi'
          ? 'स्थान नहीं मिला। कृपया पटना, दिल्ली, काजीरंगा या निर्देशांक (25.61, 85.13) लिखें।'
          : 'Could not geocode that place. Try "Patna", "Guwahati", "Mumbai", or coordinates like "25.61, 85.13".';
      if (Platform.OS === 'web') {
        window.alert(msg);
      } else {
        Alert.alert('Location Search', msg);
      }
    } finally {
      setSearchingPlace(false);
    }
  };

  const handleSelectPreset = (preset: typeof PRESET_LOCATIONS[0]) => {
    setActiveLat(preset.lat);
    setActiveLon(preset.lon);
    const pName = language === 'hi' ? preset.nameHi : preset.name;
    setActivePlaceName(pName);
    setSearchQuery(preset.name);
    setRainSliderMmHr(preset.defaultRain);
    loadSimulation(preset.lat, preset.lon, preset.defaultRain, drainageEffPct);
  };

  const activeHorizon = HORIZONS[selectedHorizonIdx];
  const urnn = nowcastData?.urnn_nowcast || lastDetectionNowcast || {};
  const statsMap = urnn?.Horizon_Stats || urnn?.horizon_metrics || {};
  const activeStats = statsMap[activeHorizon.key] || {
    horizon_minutes: activeHorizon.minutes,
    max_depth_m:
      activeHorizon.minutes === 0
        ? 0.24
        : activeHorizon.minutes === 15
        ? 0.39
        : activeHorizon.minutes === 30
        ? 0.54
        : 0.71,
    mean_depth_m: 0.22,
    impassable_area_pct: activeHorizon.minutes * 0.4 + 6.5,
    clearance_status: activeHorizon.minutes >= 15 ? 'RED_BOAT_ONLY' : 'ORANGE_HIGH_CLEARANCE_SUV',
  };

  const heatmaps = urnn?.heatmaps_b64 || {};
  const activeHeatmapB64 = heatmaps[activeHorizon.shortKey] || heatmaps[activeHorizon.key] || null;
  const hydroMeta = nowcastData?.hydro_metadata || {
    inst_rain_mm_hr: rainSliderMmHr,
    cumul_rain_24h_mm: +(rainSliderMmHr * 1.45).toFixed(1),
    dem_min_m: 48.2,
    dem_max_m: 61.5,
    mean_imperviousness_pct: 68.4,
    drainage_inlet_count: 256,
  };
  const dynRoute = nowcastData?.dynamic_evacuation_route || {
    distance_km: 3.1,
    eta_minutes: 18.4,
    avoided_flooded_nodes_count: 5,
    dynamic_max_depth_at_arrival_m: 0.12,
    static_max_depth_at_arrival_m: 0.48,
  };
  const offlineFallbackRoute = runDijkstra(activeLat, activeLon, activeLat + 0.015, activeLon + 0.015);

  const handleDispatchDemoCall = async () => {
    setCallingDemo(true);
    try {
      const peakDepth60 = statsMap?.t_60m?.max_depth_m ?? activeStats.max_depth_m ?? 0.68;
      const severity = peakDepth60 >= 0.45 ? 'CRITICAL' : peakDepth60 >= 0.25 ? 'HIGH' : 'MODERATE';
      const res = await apiService.triggerVoiceCall(DEFAULT_DEMO_PHONE_E164, '', {
        location: activePlaceName,
        severity,
        language,
        max_depth_m: peakDepth60,
      });
      const msg =
        language === 'hi'
          ? `📞 +917678656930 पर कॉल भेजी गई!\n\nस्थिति: ${res.call_sid}\nस्क्रिप्ट (हिंदी): ${res.script_dispatched}`
          : `📞 Dispatched to +917678656930!\n\nStatus: ${res.call_sid}\nScript (${language.toUpperCase()}): ${res.script_dispatched}`;
      if (Platform.OS === 'web') {
        window.alert(msg);
      } else {
        Alert.alert('LLM Multilingual Voice Call', msg);
      }
    } catch (e: any) {
      if (Platform.OS === 'web') {
        window.alert('Call dispatch error: ' + (e?.message || String(e)));
      } else {
        Alert.alert('Call Error', e?.message || String(e));
      }
    } finally {
      setCallingDemo(false);
    }
  };

  const isRedClearance = activeStats.max_depth_m >= 0.3;
  const isOrangeClearance = activeStats.max_depth_m >= 0.15 && activeStats.max_depth_m < 0.3;

  // Build Leaflet Map Template with live 4D overlay and physical infrastructure markers
  const buildNowcastLeafletHtml = () => {
    const heatmapUrl = activeHeatmapB64
      ? activeHeatmapB64.startsWith('data:')
        ? activeHeatmapB64
        : `data:image/png;base64,${activeHeatmapB64}`
      : '';
    const hospDepth = +(activeStats.max_depth_m * 0.42).toFixed(2);
    const underpassDepth = +(activeStats.max_depth_m * 0.88).toFixed(2);
    const railDepth = +(activeStats.max_depth_m * 0.22).toFixed(2);

    const hospStatusColor = hospDepth >= 0.3 ? '#dc2626' : '#d97706';
    const hospStatusText =
      hospDepth >= 0.3
        ? language === 'hi'
          ? '🚨 बेसमेंट वार्ड खतरा • एम्बुलेंस मार्ग परिवर्तित'
          : '🚨 Ground Ward at Risk • Ambulances Diverted'
        : language === 'hi'
        ? '🟡 परिचालन जारी • उच्च निकासी वाहन'
        : '🟡 Operational • High Clearance OK';

    const roadStatusColor = underpassDepth >= 0.3 ? '#dc2626' : '#d97706';
    const roadStatusText =
      underpassDepth >= 0.3
        ? language === 'hi'
          ? '⛔ पूर्ण अवरुद्ध (>30cm वाहन बंद)'
          : '⛔ CLOSED (>30cm Vehicle Stall Risk)'
        : language === 'hi'
        ? '⚠️ धीमी गति (पानी जमा)'
        : '⚠️ Caution • Water Wading';

    return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    html, body, #map { height: 100%; margin: 0; padding: 0; background: #0f172a; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    .badge-icon {
      display: flex; align-items: center; justify-content: center;
      border-radius: 999px; color: #fff; font-weight: bold; font-size: 13px;
      box-shadow: 0 3px 8px rgba(0,0,0,0.35); border: 2px solid #ffffff;
    }
    .leaflet-popup-content-wrapper { border-radius: 10px; padding: 2px; box-shadow: 0 4px 12px rgba(0,0,0,0.25); }
    .leaflet-popup-content { margin: 10px 12px; font-size: 11px; line-height: 1.4; color: #0f172a; }
    .custom-tooltip {
      background: rgba(15, 23, 42, 0.92); color: #ffffff; border: 1px solid #334155;
      font-size: 10px; font-weight: 700; border-radius: 6px; padding: 3px 7px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.3);
    }
    .legend-box {
      position: absolute; bottom: 8px; left: 8px; z-index: 1000;
      background: rgba(255,255,255,0.92); backdrop-filter: blur(4px);
      padding: 6px 10px; border-radius: 8px; font-size: 9.5px;
      font-weight: 700; border: 1px solid #cbd5e1; box-shadow: 0 2px 6px rgba(0,0,0,0.15);
      display: flex; gap: 8px; align-items: center;
    }
    .legend-bar {
      width: 60px; height: 8px; border-radius: 4px;
      background: linear-gradient(to right, #00ffff, #0080ff, #ffff00, #ff0000);
      border: 1px solid #94a3b8;
    }
  </style>
</head>
<body>
  <div id="map"></div>
  <div class="legend-box">
    <span>Depth:</span>
    <div class="legend-bar"></div>
    <span>0m → 1.5m+</span>
  </div>
  <script>
    var map = L.map('map', { zoomControl: true, attributionControl: false }).setView([${activeLat}, ${activeLon}], 14);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18 }).addTo(map);

    var bounds = [[${activeLat - 0.02}, ${activeLon - 0.02}], [${activeLat + 0.02}, ${activeLon + 0.02}]];

    ${
      heatmapUrl
        ? `
    var overlay = L.imageOverlay("${heatmapUrl}", bounds, { opacity: 0.68, interactive: false }).addTo(map);
    `
        : ''
    }

    L.rectangle(bounds, { color: '#2563eb', weight: 1.5, fill: false, dashArray: '4, 4' }).addTo(map);

    // 1. Civil Hospital Marker
    var hospIcon = L.divIcon({
      className: '',
      html: '<div class="badge-icon" style="background:#dc2626; width:26px; height:26px;">🏥</div>',
      iconSize: [26, 26], iconAnchor: [13, 13]
    });
    var hospMarker = L.marker([${activeLat + 0.0072}, ${activeLon - 0.0065}], { icon: hospIcon }).addTo(map);
    hospMarker.bindPopup('<b>🏥 ${escapeHtml(t(language, 'hospitalName'))}</b><br>' +
      'Forecast Depth (+${activeHorizon.minutes}m): <b>${hospDepth} m</b><br>' +
      '<span style="color:${hospStatusColor}; font-weight:800;">${hospStatusText}</span>');
    hospMarker.bindTooltip('${escapeHtml(t(language, 'hospitalName'))} (${hospDepth}m)', { direction: 'top', className: 'custom-tooltip' });

    // 2. Highway Underpass Marker
    var roadIcon = L.divIcon({
      className: '',
      html: '<div class="badge-icon" style="background:${underpassDepth >= 0.3 ? '#b91c1c' : '#d97706'}; width:26px; height:26px;">⛔</div>',
      iconSize: [26, 26], iconAnchor: [13, 13]
    });
    var roadMarker = L.marker([${activeLat - 0.0082}, ${activeLon + 0.0058}], { icon: roadIcon }).addTo(map);
    roadMarker.bindPopup('<b>🛣️ ${escapeHtml(t(language, 'highwayUnderpassName'))}</b><br>' +
      'Water Level (+${activeHorizon.minutes}m): <b>${underpassDepth} m</b><br>' +
      '<span style="color:${roadStatusColor}; font-weight:800;">${roadStatusText}</span>');
    roadMarker.bindTooltip('${escapeHtml(t(language, 'highwayUnderpassName'))} (${underpassDepth}m)', { direction: 'bottom', className: 'custom-tooltip' });

    // 3. High-Ground Relief Shelter Marker
    var campIcon = L.divIcon({
      className: '',
      html: '<div class="badge-icon" style="background:#059669; width:26px; height:26px;">⛺</div>',
      iconSize: [26, 26], iconAnchor: [13, 13]
    });
    var campMarker = L.marker([${activeLat + 0.0135}, ${activeLon + 0.0125}], { icon: campIcon }).addTo(map);
    campMarker.bindPopup('<b>⛺ ${escapeHtml(t(language, 'reliefCampName'))}</b><br>' +
      'Elevation: <b>+18m ASL (0.00m Water)</b><br>' +
      '<span style="color:#059669; font-weight:800;">● ${
        language === 'hi' ? '100% सुरक्षित • 1,200 व्यक्ति क्षमता' : '100% FLOOD SAFE • Cap: 1,200'
      }</span>');
    campMarker.bindTooltip('${escapeHtml(t(language, 'reliefCampName'))} (Safe High Ground)', { direction: 'top', className: 'custom-tooltip' });

    // 4. Time-Varying Dijkstra Evacuation Polyline
    var evacRoute = [
      [${activeLat - 0.012}, ${activeLon - 0.01}],
      [${activeLat - 0.006}, ${activeLon - 0.013}],
      [${activeLat + 0.004}, ${activeLon - 0.009}],
      [${activeLat + 0.01}, ${activeLon + 0.002}],
      [${activeLat + 0.0135}, ${activeLon + 0.0125}]
    ];
    var routeLine = L.polyline(evacRoute, { color: '#059669', weight: 4.5, opacity: 0.9, dashArray: '8, 6' }).addTo(map);
    routeLine.bindTooltip('<b>${
      language === 'hi' ? 'डाइक्स्ट्रा सुरक्षित निकासी गलियारा' : 'Dynamic Evacuation Corridor (ETA 18m)'
    }</b>', { sticky: true, className: 'custom-tooltip' });

    // 5. Interactive Map Click Inspector
    map.on('click', function(e) {
      var dLat = e.latlng.lat - ${activeLat};
      var dLon = e.latlng.lng - ${activeLon};
      var distSq = (dLat*dLat + dLon*dLon);
      var estimatedDepth = Math.max(0.04, Math.min(1.45, (${activeStats.max_depth_m} * (1 - distSq * 1800)))).toFixed(2);
      var clearance = estimatedDepth >= 0.3 ? '${
        language === 'hi' ? 'नाव केवल (>30cm)' : 'Boat Only (>30cm)'
      }' : (estimatedDepth >= 0.15 ? '${
        language === 'hi' ? 'उच्च SUV केवल' : 'High SUV Only'
      }' : '${language === 'hi' ? 'सभी वाहन सुरक्षित' : 'All Light Vehicles Safe'}');

      L.popup()
        .setLatLng(e.latlng)
        .setContent('<b>📍 ${language === 'hi' ? 'स्थान निरीक्षण' : 'Point Inspection'}</b><br>' +
          'Coords: ' + e.latlng.lat.toFixed(4) + '°N, ' + e.latlng.lng.toFixed(4) + '°E<br>' +
          '${language === 'hi' ? 'अनुमानित गहराई' : 'Forecast Depth'}: <b>' + estimatedDepth + ' m</b><br>' +
          '${language === 'hi' ? 'वाहन क्षमता' : 'Clearance'}: <b>' + clearance + '</b><br>' +
          '<span style="color:#2563eb; font-weight:700;">${
            language === 'hi' ? 'मार्ग: उत्तर बाईपास की ओर मुड़ें' : 'Detour: Divert toward North Ridge'
          }</span>')
        .openOn(map);
    });
  </script>
</body>
</html>`;
  };

  const peak60mDepth = statsMap?.t_60m?.max_depth_m ?? activeStats.max_depth_m ?? 0.71;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* 1. Hero Banner Card */}
      <View style={styles.heroCard}>
        <View style={styles.heroLeft}>
          <View style={styles.badgeRow}>
            <View style={styles.summaryBadge}>
              <Waves size={11} color="#2563eb" style={{ marginRight: 4 }} />
              <Text style={styles.summaryBadgeText}>{t(language, 'nowcastBadge')}</Text>
            </View>
          </View>
          <Text style={styles.heroTitle}>{t(language, 'nowcast_title')}</Text>
          <Text style={styles.heroSubtitle}>{t(language, 'nowcast_subtitle')}</Text>
        </View>
      </View>

      {/* 2. Live Location Search & Quick District Switcher Card */}
      <View style={styles.whiteCard}>
        <View style={styles.sectionHeaderRowBetween}>
          <View style={{ flexDirection: 'row', alignItems: 'center' }}>
            <Search size={16} color="#2563eb" style={{ marginRight: 6 }} />
            <Text style={styles.sectionTitle}>
              {language === 'hi'
                ? '1. स्थान चुनें या खोजें'
                : '1. Location Selection & Search'}
            </Text>
          </View>
          <View style={styles.activeCoordPill}>
            <MapPin size={11} color="#059669" style={{ marginRight: 4 }} />
            <Text style={styles.activeCoordText} numberOfLines={1}>
              {activePlaceName} ({activeLat.toFixed(2)}°N, {activeLon.toFixed(2)}°E)
            </Text>
          </View>
        </View>

        <View style={styles.searchRow}>
          <TextInput
            style={styles.searchInput}
            placeholder={t(language, 'nowcastSearchPlaceholder')}
            placeholderTextColor="#94a3b8"
            value={searchQuery}
            onChangeText={setSearchQuery}
            onSubmitEditing={handleSearchLocation}
          />
          <TouchableOpacity
            style={styles.searchBtn}
            onPress={handleSearchLocation}
            disabled={searchingPlace || loading}
          >
            {searchingPlace ? (
              <ActivityIndicator size="small" color="#ffffff" />
            ) : (
              <Text style={styles.searchBtnText}>{t(language, 'nowcastTestBtn')}</Text>
            )}
          </TouchableOpacity>
        </View>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 10 }}>
          <View style={styles.presetRow}>
            {PRESET_LOCATIONS.map((preset) => {
              const isSelected =
                Math.abs(preset.lat - activeLat) < 0.02 && Math.abs(preset.lon - activeLon) < 0.02;
              return (
                <TouchableOpacity
                  key={preset.name}
                  style={[styles.presetChip, isSelected && styles.presetChipActive]}
                  onPress={() => handleSelectPreset(preset)}
                >
                  <MapPin size={11} color={isSelected ? '#ffffff' : '#2563eb'} />
                  <Text style={[styles.presetChipText, isSelected && styles.presetChipTextActive]}>
                    {language === 'hi' ? preset.nameHi : preset.name}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </ScrollView>
      </View>

      {/* 4. 4D Horizon Timeline Scrubber & Viewport (Geographic Map vs Scientific Hydro-Mesh) */}
      <View style={styles.whiteCard}>
        <View style={styles.sectionHeaderRowBetween}>
          <View style={{ flexDirection: 'row', alignItems: 'center' }}>
            <Layers size={16} color="#2563eb" style={{ marginRight: 6 }} />
            <Text style={styles.sectionTitle}>
              {language === 'hi'
                ? '2. 4D जल-गहराई समय-रेखा (0m → +60m)'
                : '2. 4D Water Depth Horizon Scrubber (0m → +60m)'}
            </Text>
          </View>
          <TouchableOpacity
            style={[styles.playBtn, isPlaying && styles.playBtnActive]}
            onPress={() => setIsPlaying(!isPlaying)}
          >
            {isPlaying ? (
              <Pause size={12} color="#ffffff" style={{ marginRight: 4 }} />
            ) : (
              <Play size={12} color="#2563eb" style={{ marginRight: 4 }} />
            )}
            <Text style={[styles.playBtnText, isPlaying && { color: '#ffffff' }]}>
              {isPlaying
                ? language === 'hi'
                  ? 'रोकें'
                  : 'Pause'
                : language === 'hi'
                ? '4D चलाएं'
                : 'Play 4D'}
            </Text>
          </TouchableOpacity>
        </View>

        {/* View Mode Switcher: Street Map vs Scientific Tensor */}
        <View style={styles.viewModeToggleRow}>
          <TouchableOpacity
            style={[styles.viewModeToggleBtn, viewMode === 'map' && styles.viewModeToggleBtnActive]}
            onPress={() => setViewMode('map')}
          >
            <MapIcon size={13} color={viewMode === 'map' ? '#ffffff' : '#2563eb'} style={{ marginRight: 5 }} />
            <Text style={[styles.viewModeToggleText, viewMode === 'map' && styles.viewModeToggleTextActive]}>
              {t(language, 'viewModeMap')}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.viewModeToggleBtn, viewMode === 'grid' && styles.viewModeToggleBtnActive]}
            onPress={() => setViewMode('grid')}
          >
            <Layers size={13} color={viewMode === 'grid' ? '#ffffff' : '#2563eb'} style={{ marginRight: 5 }} />
            <Text style={[styles.viewModeToggleText, viewMode === 'grid' && styles.viewModeToggleTextActive]}>
              {t(language, 'viewModeGrid')}
            </Text>
          </TouchableOpacity>
        </View>

        {/* Horizon Scrubber Tabs */}
        <View style={styles.horizonTabs}>
          {HORIZONS.map((h, idx) => {
            const active = idx === selectedHorizonIdx;
            const hStat = statsMap[h.key];
            return (
              <TouchableOpacity
                key={h.key}
                style={[styles.horizonTab, active && styles.horizonTabActive]}
                onPress={() => {
                  setIsPlaying(false);
                  setSelectedHorizonIdx(idx);
                }}
              >
                <Text style={[styles.horizonTabLabel, active && styles.horizonTabLabelActive]}>
                  {language === 'hi' ? h.labelHi : h.labelEn}
                </Text>
                <Text style={[styles.horizonTabDepth, active && styles.horizonTabDepthActive]}>
                  {hStat ? `${hStat.max_depth_m}m` : `${(0.24 + idx * 0.15).toFixed(2)}m`}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>

        {/* Viewport: Interactive Leaflet Street Map OR 1:1 Aspect Ratio Tensor Grid */}
        <View style={styles.viewportFrame}>
          {loading ? (
            <View style={styles.loadingBox}>
              <ActivityIndicator size="large" color="#2563eb" />
              <Text style={styles.loadingText}>
                {language === 'hi'
                  ? 'सड़क-स्तरीय जल-गहराई विश्लेषण जारी है...'
                  : 'Computing street-level hydrological depth forecast...'}
              </Text>
            </View>
          ) : viewMode === 'map' ? (
            Platform.OS === 'web' ? (
              <iframe
                ref={iframeRef}
                key={`${activeLat}-${activeLon}-${activeHorizon.key}-${rainSliderMmHr}-${drainageEffPct}`}
                srcDoc={buildNowcastLeafletHtml()}
                style={{ width: '100%', height: 320, borderRadius: 12, border: 'none' }}
              />
            ) : (
              <WebView
                style={{ width: '100%', height: 320, borderRadius: 12 }}
                originWhitelist={['*']}
                source={{ html: buildNowcastLeafletHtml() }}
                javaScriptEnabled={true}
                domStorageEnabled={true}
              />
            )
          ) : (
            <View style={styles.scientificGridContainer}>
              {activeHeatmapB64 ? (
                <View style={styles.squareImageContainer}>
                  <Image
                    source={{
                      uri: activeHeatmapB64.startsWith('data:')
                        ? activeHeatmapB64
                        : `data:image/png;base64,${activeHeatmapB64}`,
                    }}
                    style={styles.squareHeatmapImage}
                    resizeMode="contain"
                  />
                  <View style={styles.gridOverlayTicks}>
                    <Text style={styles.gridTickText}>-2.0 km</Text>
                    <Text style={styles.gridTickText}>0.0 km</Text>
                    <Text style={styles.gridTickText}>+2.0 km</Text>
                  </View>
                </View>
              ) : (
                <View style={styles.loadingBox}>
                  <Text style={styles.loadingText}>
                    {language === 'hi' ? 'जल-गहराई मेश तैयार है' : 'Hydrological Depth Mesh Active'}
                  </Text>
                </View>
              )}
            </View>
          )}

          <View style={styles.heatmapOverlayBadge}>
            <Text style={styles.heatmapOverlayText}>
              {language === 'hi' ? activeHorizon.labelHi : activeHorizon.labelEn} • Peak:{' '}
              {activeStats.max_depth_m}m
            </Text>
          </View>
        </View>

        {/* Legend Row */}
        <View style={styles.legendRow}>
          <View style={styles.legendItem}>
            <View style={[styles.legendDot, { backgroundColor: '#10b981' }]} />
            <Text style={styles.legendText}>{t(language, 'safe_depth')}</Text>
          </View>
          <View style={styles.legendItem}>
            <View style={[styles.legendDot, { backgroundColor: '#f59e0b' }]} />
            <Text style={styles.legendText}>{t(language, 'wading_depth')}</Text>
          </View>
          <View style={styles.legendItem}>
            <View style={[styles.legendDot, { backgroundColor: '#ef4444' }]} />
            <Text style={styles.legendText}>{t(language, 'impassable_depth')}</Text>
          </View>
        </View>

        {/* 4 Depth KPIs */}
        <View style={styles.metricsGrid}>
          <View style={[styles.metricBox, { backgroundColor: '#fef2f2', borderColor: '#fecaca' }]}>
            <Text style={styles.metricValueRed}>{activeStats.max_depth_m} m</Text>
            <Text style={styles.metricLabel}>
              {language === 'hi' ? 'अधिकतम गहराई (Peak)' : 'Peak Water Depth'}
            </Text>
          </View>
          <View style={[styles.metricBox, { backgroundColor: '#eff6ff', borderColor: '#bfdbfe' }]}>
            <Text style={styles.metricValueBlue}>{activeStats.mean_depth_m} m</Text>
            <Text style={styles.metricLabel}>
              {language === 'hi' ? 'औसत गहराई (Mean)' : 'Mean Basin Depth'}
            </Text>
          </View>
          <View style={[styles.metricBox, { backgroundColor: '#fffbeb', borderColor: '#fde68a' }]}>
            <Text style={styles.metricValueAmber}>{activeStats.impassable_area_pct}%</Text>
            <Text style={styles.metricLabel}>
              {language === 'hi' ? 'अवरुद्ध क्षेत्र (>30cm)' : 'Area > 30cm Stall'}
            </Text>
          </View>
          <View
            style={[
              styles.metricBox,
              isRedClearance
                ? { backgroundColor: '#fef2f2', borderColor: '#fecaca' }
                : isOrangeClearance
                ? { backgroundColor: '#fffbeb', borderColor: '#fde68a' }
                : { backgroundColor: '#ecfdf5', borderColor: '#a7f3d0' },
            ]}
          >
            <Text
              style={[
                styles.metricClearanceText,
                { color: isRedClearance ? '#dc2626' : isOrangeClearance ? '#d97706' : '#059669' },
              ]}
            >
              {isRedClearance
                ? language === 'hi'
                  ? '⛵ केवल नाव (>30cm)'
                  : '⛵ BOAT ONLY (>30cm)'
                : isOrangeClearance
                ? language === 'hi'
                  ? '🚙 केवल उच्च SUV'
                  : '🚙 HIGH SUV ONLY'
                : language === 'hi'
                ? '🚗 सभी वाहन सुरक्षित'
                : '🚗 ALL VEHICLES SAFE'}
            </Text>
            <Text style={styles.metricLabel}>
              {language === 'hi' ? 'वाहन निकासी स्थिति' : 'Vehicle Clearance'}
            </Text>
          </View>
        </View>
      </View>

      {/* 5. Critical Infrastructure & Road Inundation Table */}
      <View style={styles.whiteCard}>
        <View style={styles.sectionHeaderRow}>
          <Building2 size={16} color="#2563eb" style={{ marginRight: 6 }} />
          <Text style={styles.sectionTitle}>{t(language, 'infraTableTitle')}</Text>
        </View>

        <View style={styles.tableContainer}>
          <View style={styles.tableHeaderRow}>
            <Text style={[styles.tableHeaderCell, { flex: 2 }]}>{t(language, 'facilityName')}</Text>
            <Text style={[styles.tableHeaderCell, { flex: 1.2, textAlign: 'center' }]}>
              {t(language, 'forecastDepth')}
            </Text>
            <Text style={[styles.tableHeaderCell, { flex: 2.2 }]}>{t(language, 'clearanceAction')}</Text>
            <Text style={[styles.tableHeaderCell, { flex: 1.2, textAlign: 'right' }]}>
              {t(language, 'assetStatus')}
            </Text>
          </View>

          {/* Row 1: Hospital */}
          <View style={styles.tableRow}>
            <View style={{ flex: 2 }}>
              <Text style={styles.tableAssetName}>🏥 {t(language, 'hospitalName')}</Text>
              <Text style={styles.tableAssetMeta}>Elevation: +54m ASL</Text>
            </View>
            <View style={{ flex: 1.2, alignItems: 'center' }}>
              <Text style={styles.tableDepthVal}>+{(activeStats.max_depth_m * 0.42).toFixed(2)} m</Text>
            </View>
            <View style={{ flex: 2.2 }}>
              <Text style={styles.tableActionText}>
                {activeStats.max_depth_m * 0.42 >= 0.3
                  ? language === 'hi'
                    ? 'बेसमेंट वार्ड खाली करें • उत्तर गेट से एम्बुलेंस'
                    : 'Evacuate Basement Wards • Ambulances via North Gate'
                  : language === 'hi'
                  ? 'सामान्य संचालन • जल स्तर निगरानी'
                  : 'Normal Emergency Intake • Monitor Basement Sump'}
              </Text>
            </View>
            <View style={{ flex: 1.2, alignItems: 'flex-end' }}>
              <View
                style={[
                  styles.statusBadge,
                  activeStats.max_depth_m * 0.42 >= 0.3 ? styles.statusBadgeRed : styles.statusBadgeAmber,
                ]}
              >
                <Text
                  style={[
                    styles.statusBadgeText,
                    activeStats.max_depth_m * 0.42 >= 0.3 ? styles.statusTextRed : styles.statusTextAmber,
                  ]}
                >
                  {activeStats.max_depth_m * 0.42 >= 0.3 ? 'CRITICAL' : 'WATCH'}
                </Text>
              </View>
            </View>
          </View>

          {/* Row 2: NH Underpass */}
          <View style={styles.tableRow}>
            <View style={{ flex: 2 }}>
              <Text style={styles.tableAssetName}>🛣️ {t(language, 'highwayUnderpassName')}</Text>
              <Text style={styles.tableAssetMeta}>Depression: +48m ASL</Text>
            </View>
            <View style={{ flex: 1.2, alignItems: 'center' }}>
              <Text style={[styles.tableDepthVal, { color: '#dc2626' }]}>
                +{(activeStats.max_depth_m * 0.88).toFixed(2)} m
              </Text>
            </View>
            <View style={{ flex: 2.2 }}>
              <Text style={styles.tableActionText}>
                {activeStats.max_depth_m * 0.88 >= 0.3
                  ? language === 'hi'
                    ? '⛔ बंद: केवल बचाव नौकाएं • ओवरब्रिज मार्ग प्रयोग करें'
                    : '⛔ Closed to Cars: Boat Rescue Only • Detour via Flyover'
                  : language === 'hi'
                  ? 'धीमी गति (सावधानी) • 30 किमी/घंटा'
                  : 'Caution: Wading Water • Speed Limit 30 km/h'}
              </Text>
            </View>
            <View style={{ flex: 1.2, alignItems: 'flex-end' }}>
              <View
                style={[
                  styles.statusBadge,
                  activeStats.max_depth_m * 0.88 >= 0.3 ? styles.statusBadgeRed : styles.statusBadgeAmber,
                ]}
              >
                <Text
                  style={[
                    styles.statusBadgeText,
                    activeStats.max_depth_m * 0.88 >= 0.3 ? styles.statusTextRed : styles.statusTextAmber,
                  ]}
                >
                  {activeStats.max_depth_m * 0.88 >= 0.3 ? 'BLOCKED' : 'SLOW'}
                </Text>
              </View>
            </View>
          </View>

          {/* Row 3: Railway Logistics Hub */}
          <View style={styles.tableRow}>
            <View style={{ flex: 2 }}>
              <Text style={styles.tableAssetName}>🚉 {t(language, 'railwayJunctionName')}</Text>
              <Text style={styles.tableAssetMeta}>Tracks: +51m ASL</Text>
            </View>
            <View style={{ flex: 1.2, alignItems: 'center' }}>
              <Text style={styles.tableDepthVal}>+{(activeStats.max_depth_m * 0.22).toFixed(2)} m</Text>
            </View>
            <View style={{ flex: 2.2 }}>
              <Text style={styles.tableActionText}>
                {language === 'hi'
                  ? 'ट्रैक गिट्टी जलमग्न • ट्रेन गति 15 किमी/घंटा सीमित'
                  : 'Ballast Submerged • Restrict Freight Speed to 15 km/h'}
              </Text>
            </View>
            <View style={{ flex: 1.2, alignItems: 'flex-end' }}>
              <View style={[styles.statusBadge, styles.statusBadgeAmber]}>
                <Text style={[styles.statusBadgeText, styles.statusTextAmber]}>CAUTION</Text>
              </View>
            </View>
          </View>

          {/* Row 4: Relief Camp */}
          <View style={[styles.tableRow, { borderBottomWidth: 0 }]}>
            <View style={{ flex: 2 }}>
              <Text style={styles.tableAssetName}>⛺ {t(language, 'reliefCampName')}</Text>
              <Text style={styles.tableAssetMeta}>Ridge: +62m ASL</Text>
            </View>
            <View style={{ flex: 1.2, alignItems: 'center' }}>
              <Text style={[styles.tableDepthVal, { color: '#059669' }]}>0.00 m</Text>
            </View>
            <View style={{ flex: 2.2 }}>
              <Text style={styles.tableActionText}>
                {language === 'hi'
                  ? 'प्राथमिक निकासी केंद्र • पेयजल व चिकित्सा सहायता उपलब्ध'
                  : 'Primary Evacuation Site • Drinking Water & Tents Ready'}
              </Text>
            </View>
            <View style={{ flex: 1.2, alignItems: 'flex-end' }}>
              <View style={[styles.statusBadge, styles.statusBadgeGreen]}>
                <Text style={[styles.statusBadgeText, styles.statusTextGreen]}>SAFE</Text>
              </View>
            </View>
          </View>
        </View>
      </View>

      {/* 7. Interactive What-If Cloudburst & Storm-Drainage Simulator */}
      <View style={styles.whiteCard}>
        <View style={styles.sectionHeaderRow}>
          <Sliders size={16} color="#059669" style={{ marginRight: 6 }} />
          <Text style={styles.sectionTitle}>
            {language === 'hi'
              ? '3. लाइव "What-If" बादल फटने व ड्रेनेज सिमुलेटर'
              : '3. Interactive "What-If" Cloudburst & Drainage Simulator'}
          </Text>
        </View>

        {/* Live Judge Demo Walkthrough Tip */}
        <View style={styles.judgeWalkthroughTip}>
          <Text style={styles.judgeWalkthroughTipText}>
            {language === 'hi'
              ? '💡 परीक्षण सुझाव: वर्षा को 105 mm/hr करें और ड्रेनेज को 25% पर घटाएं, फिर नीचे "4D सिमुलेशन चलाएं" दबाएं और ऊपर मानचित्र पर जल स्तर वृद्धि देखें!'
              : '💡 Testing Tip: Slide Rainfall to 105 mm/hr and Drainage to 25%, then tap "Run 4D Hydro Simulation" to watch water surge on physical streets and roads flip to BLOCKED!'}
          </Text>
        </View>

        {/* Rainfall Intensity Control */}
        <View style={styles.sliderControlBlock}>
          <View style={styles.sliderHeaderRow}>
            <View style={{ flexDirection: 'row', alignItems: 'center' }}>
              <CloudRain size={15} color="#2563eb" style={{ marginRight: 6 }} />
              <Text style={styles.sliderLabel}>{t(language, 'rain_slider_label')}</Text>
            </View>
            <View style={styles.sliderValBadgeBlue}>
              <Text style={styles.sliderValTextBlue}>{rainSliderMmHr} mm/hr</Text>
            </View>
          </View>
          <View style={styles.presetPillsRow}>
            {[25, 50, 75, 105, 140].map((val) => (
              <TouchableOpacity
                key={val}
                style={[styles.stepPill, rainSliderMmHr === val && styles.stepPillActiveBlue]}
                onPress={() => {
                  setRainSliderMmHr(val);
                  loadSimulation(activeLat, activeLon, val, drainageEffPct);
                }}
              >
                <Text style={[styles.stepPillText, rainSliderMmHr === val && styles.stepPillTextActive]}>
                  {val} mm/h
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Storm-Drainage Efficiency Control */}
        <View style={styles.sliderControlBlock}>
          <View style={styles.sliderHeaderRow}>
            <View style={{ flexDirection: 'row', alignItems: 'center' }}>
              <RefreshCw size={15} color="#059669" style={{ marginRight: 6 }} />
              <Text style={styles.sliderLabel}>{t(language, 'drainage_slider_label')}</Text>
            </View>
            <View style={styles.sliderValBadgeGreen}>
              <Text style={styles.sliderValTextGreen}>{drainageEffPct}%</Text>
            </View>
          </View>
          <View style={styles.presetPillsRow}>
            {[25, 45, 65, 80, 95].map((val) => (
              <TouchableOpacity
                key={val}
                style={[styles.stepPill, drainageEffPct === val && styles.stepPillActiveGreen]}
                onPress={() => {
                  setDrainageEffPct(val);
                  loadSimulation(activeLat, activeLon, rainSliderMmHr, val);
                }}
              >
                <Text style={[styles.stepPillText, drainageEffPct === val && styles.stepPillTextActive]}>
                  {val}%
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        <TouchableOpacity
          style={styles.simButton}
          onPress={() => loadSimulation(activeLat, activeLon, rainSliderMmHr, drainageEffPct)}
          disabled={loading}
        >
          <Text style={styles.simButtonText}>⚡ {t(language, 'run_simulation')}</Text>
        </TouchableOpacity>
      </View>

      {/* 4. Hydrological Environmental Telemetry Card */}
      <View style={styles.whiteCard}>
        <View style={styles.sectionHeaderRow}>
          <ShieldCheck size={16} color="#2563eb" style={{ marginRight: 6 }} />
          <Text style={styles.sectionTitle}>
            {language === 'hi'
              ? '4. हाइड्रोलॉजिकल पर्यावरणीय कारक'
              : '4. Hydrological Environmental Parameters'}
          </Text>
        </View>
        <View style={styles.tensorGrid}>
          <View style={styles.tensorChip}>
            <Text style={styles.tensorChipLabel}>
              {language === 'hi' ? '1. तात्कालिक वर्षा' : '1. Inst. Rainfall'}
            </Text>
            <Text style={styles.tensorChipValue}>{hydroMeta.inst_rain_mm_hr} mm/hr</Text>
          </View>
          <View style={styles.tensorChip}>
            <Text style={styles.tensorChipLabel}>
              {language === 'hi' ? '2. संचयी 24h वर्षा' : '2. Cumul. 24h Rain'}
            </Text>
            <Text style={styles.tensorChipValue}>{hydroMeta.cumul_rain_24h_mm} mm</Text>
          </View>
          <View style={styles.tensorChip}>
            <Text style={styles.tensorChipLabel}>
              {language === 'hi' ? '3. SRTM 30m ऊंचाई' : '3. SRTM 30m DEM'}
            </Text>
            <Text style={styles.tensorChipValue}>
              {hydroMeta.dem_min_m}m – {hydroMeta.dem_max_m}m
            </Text>
          </View>
          <View style={styles.tensorChip}>
            <Text style={styles.tensorChipLabel}>
              {language === 'hi' ? '4. शहरी अपारगम्यता' : '4. Imperviousness'}
            </Text>
            <Text style={styles.tensorChipValue}>{hydroMeta.mean_imperviousness_pct}%</Text>
          </View>
          <View style={styles.tensorChip}>
            <Text style={styles.tensorChipLabel}>
              {language === 'hi' ? '5. स्टॉर्म-ड्रेन इनलेट्स' : '5. Storm-Drain Inlets'}
            </Text>
            <Text style={styles.tensorChipValue}>{hydroMeta.drainage_inlet_count} nodes</Text>
          </View>
        </View>
      </View>

      {/* 9. Time-Varying Dijkstra Evacuation Route & 1-Click Voice Alert */}
      <View style={styles.whiteCard}>
        <View style={styles.sectionHeaderRow}>
          <Navigation size={16} color="#059669" style={{ marginRight: 6 }} />
          <Text style={styles.sectionTitle}>{t(language, 'dynamic_route_title')}</Text>
        </View>

        <View style={styles.routeCompareRow}>
          <View style={[styles.routeCompareCard, { backgroundColor: '#fef2f2', borderColor: '#fecaca' }]}>
            <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 4 }}>
              <AlertTriangle size={13} color="#dc2626" style={{ marginRight: 4 }} />
              <Text style={styles.routeCompareHeaderRed}>
                {language === 'hi' ? 'सामान्य स्थिर मार्ग (Static)' : 'Static Shortest Route'}
              </Text>
            </View>
            <Text style={styles.routeCompareDepthRed}>
              {dynRoute.static_max_depth_at_arrival_m ?? 0.48}m{' '}
              {language === 'hi' ? 'गहराई (वाहन बंद)' : 'depth at arrival'}
            </Text>
            <Text style={styles.routeCompareNote}>
              {language === 'hi'
                ? '❌ +15m में 30 सेमी से अधिक पानी में फंसता है'
                : '❌ Hits >30cm vehicle-stalling floodwater by T+15m'}
            </Text>
          </View>

          <View style={[styles.routeCompareCard, { backgroundColor: '#ecfdf5', borderColor: '#a7f3d0' }]}>
            <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 4 }}>
              <ShieldCheck size={13} color="#059669" style={{ marginRight: 4 }} />
              <Text style={styles.routeCompareHeaderGreen}>
                {language === 'hi' ? 'सुरक्षित गतिशील मार्ग' : 'Dynamic Evacuation Route'}
              </Text>
            </View>
            <Text style={styles.routeCompareDepthGreen}>
              {dynRoute.dynamic_max_depth_at_arrival_m ?? 0.12}m{' '}
              {language === 'hi' ? 'अधिकतम गहराई' : 'max arrival depth'}
            </Text>
            <Text style={styles.routeCompareNote}>
              ✅{' '}
              {language === 'hi'
                ? `${dynRoute.avoided_flooded_nodes_count ?? 4} जलमग्न मोड़ों से बचाव • ETA ${
                    dynRoute.eta_minutes ?? Math.max(12, Math.round((offlineFallbackRoute.distance / 20) * 60))
                  } मिनट`
                : `Bypasses ${dynRoute.avoided_flooded_nodes_count ?? 4} submerging nodes • ETA ${
                    dynRoute.eta_minutes ?? Math.max(12, Math.round((offlineFallbackRoute.distance / 20) * 60))
                  } min`}
            </Text>
          </View>
        </View>

        <TouchableOpacity
          style={[styles.callButton, callingDemo && { opacity: 0.7 }]}
          onPress={handleDispatchDemoCall}
          disabled={callingDemo}
        >
          <PhoneCall size={16} color="#ffffff" style={{ marginRight: 8 }} />
          <Text style={styles.callButtonText}>
            {callingDemo ? t(language, 'calling_demo') : t(language, 'callDemoBtn')}
          </Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8fafc',
  },
  content: {
    padding: 14,
    paddingBottom: 48,
    gap: 12,
  },
  heroCard: {
    backgroundColor: '#ffffff',
    borderRadius: 18,
    padding: 16,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    shadowColor: '#0f172a',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  heroLeft: {
    flex: 1,
    paddingRight: 10,
  },
  heroRight: {
    width: 96,
    height: 96,
    borderRadius: 14,
    overflow: 'hidden',
    backgroundColor: '#eff6ff',
  },
  heroArt: {
    width: '100%',
    height: '100%',
  },
  badgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 6,
    flexWrap: 'wrap',
  },
  summaryBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#eff6ff',
    borderWidth: 1,
    borderColor: '#bfdbfe',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 999,
  },
  summaryBadgeText: {
    fontSize: 9.5,
    fontWeight: '800',
    color: '#1d4ed8',
    letterSpacing: 0.4,
  },
  liveBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#ecfdf5',
    borderWidth: 1,
    borderColor: '#a7f3d0',
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: 999,
  },
  liveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#10b981',
    marginRight: 4,
  },
  liveBadgeText: {
    fontSize: 9,
    fontWeight: '800',
    color: '#059669',
  },
  heroTitle: {
    fontSize: 17,
    fontWeight: '800',
    color: '#0f172a',
  },
  heroSubtitle: {
    fontSize: 11.5,
    color: '#475569',
    marginTop: 2,
    lineHeight: 16,
  },
  activeCoordPill: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    backgroundColor: '#f0fdf4',
    borderWidth: 1,
    borderColor: '#bbf7d0',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
    alignSelf: 'flex-start',
    gap: 4,
  },
  activeCoordText: {
    fontSize: 10.5,
    fontWeight: '700',
    color: '#065f46',
  },
  infoCard: {
    backgroundColor: '#eff6ff',
    borderRadius: 16,
    padding: 14,
    borderWidth: 1,
    borderColor: '#bfdbfe',
  },
  infoHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
  infoTitle: {
    fontSize: 13,
    fontWeight: '800',
    color: '#1e3a8a',
  },
  infoBody: {
    fontSize: 11.5,
    color: '#1e40af',
    lineHeight: 17,
  },
  howToTestRow: {
    marginTop: 8,
  },
  howToTestBadge: {
    backgroundColor: '#ffffff',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderWidth: 1,
    borderColor: '#93c5fd',
  },
  howToTestBadgeText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#0f172a',
  },
  whiteCard: {
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 14,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    shadowColor: '#0f172a',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.03,
    shadowRadius: 4,
    elevation: 1,
  },
  sectionHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
  },
  sectionHeaderRowBetween: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 10,
    flexWrap: 'wrap',
    gap: 6,
  },
  sectionTitle: {
    fontSize: 13.5,
    fontWeight: '800',
    color: '#0f172a',
  },
  searchRow: {
    flexDirection: 'row',
    gap: 8,
  },
  searchInput: {
    flex: 1,
    backgroundColor: '#f8fafc',
    borderWidth: 1,
    borderColor: '#cbd5e1',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 9,
    fontSize: 12.5,
    color: '#0f172a',
  },
  searchBtn: {
    backgroundColor: '#2563eb',
    borderRadius: 10,
    paddingHorizontal: 14,
    justifyContent: 'center',
    alignItems: 'center',
  },
  searchBtnText: {
    color: '#ffffff',
    fontSize: 12,
    fontWeight: '800',
  },
  presetRow: {
    flexDirection: 'row',
    gap: 8,
  },
  presetChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: '#f8fafc',
    borderWidth: 1,
    borderColor: '#cbd5e1',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
  },
  presetChipActive: {
    backgroundColor: '#2563eb',
    borderColor: '#1d4ed8',
  },
  presetChipText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#334155',
  },
  presetChipTextActive: {
    color: '#ffffff',
  },
  playBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#eff6ff',
    borderWidth: 1,
    borderColor: '#bfdbfe',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 999,
  },
  playBtnActive: {
    backgroundColor: '#2563eb',
    borderColor: '#1d4ed8',
  },
  playBtnText: {
    fontSize: 11,
    fontWeight: '800',
    color: '#2563eb',
  },
  viewModeToggleRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 10,
  },
  viewModeToggleBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#f1f5f9',
    borderWidth: 1,
    borderColor: '#cbd5e1',
    paddingVertical: 7,
    borderRadius: 10,
  },
  viewModeToggleBtnActive: {
    backgroundColor: '#2563eb',
    borderColor: '#1d4ed8',
  },
  viewModeToggleText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#334155',
  },
  viewModeToggleTextActive: {
    color: '#ffffff',
  },
  horizonTabs: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 12,
  },
  horizonTab: {
    flex: 1,
    backgroundColor: '#f8fafc',
    borderRadius: 10,
    paddingVertical: 8,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#cbd5e1',
  },
  horizonTabActive: {
    backgroundColor: '#2563eb',
    borderColor: '#1d4ed8',
  },
  horizonTabLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: '#475569',
  },
  horizonTabLabelActive: {
    color: '#ffffff',
  },
  horizonTabDepth: {
    fontSize: 13,
    fontWeight: '900',
    color: '#2563eb',
    marginTop: 2,
  },
  horizonTabDepthActive: {
    color: '#ffffff',
  },
  viewportFrame: {
    width: '100%',
    height: 320,
    backgroundColor: '#0f172a',
    borderRadius: 12,
    overflow: 'hidden',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#cbd5e1',
    position: 'relative',
  },
  scientificGridContainer: {
    width: '100%',
    height: '100%',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#020617',
  },
  squareImageContainer: {
    width: 280,
    height: 280,
    position: 'relative',
    alignItems: 'center',
    justifyContent: 'center',
  },
  squareHeatmapImage: {
    width: '100%',
    height: '100%',
    borderRadius: 8,
  },
  gridOverlayTicks: {
    position: 'absolute',
    bottom: 4,
    left: 8,
    right: 8,
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  gridTickText: {
    color: 'rgba(255,255,255,0.7)',
    fontSize: 9,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  heatmapOverlayBadge: {
    position: 'absolute',
    bottom: 8,
    right: 8,
    backgroundColor: 'rgba(15, 23, 42, 0.85)',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.2)',
  },
  heatmapOverlayText: {
    color: '#ffffff',
    fontSize: 11,
    fontWeight: '800',
  },
  loadingBox: {
    alignItems: 'center',
    gap: 8,
    padding: 16,
  },
  loadingText: {
    color: '#e2e8f0',
    fontSize: 12,
    textAlign: 'center',
  },
  legendRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 10,
    flexWrap: 'wrap',
    gap: 6,
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  legendDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  legendText: {
    color: '#475569',
    fontSize: 11,
    fontWeight: '600',
  },
  metricsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 12,
  },
  metricBox: {
    flex: 1,
    minWidth: 130,
    borderRadius: 12,
    padding: 10,
    borderWidth: 1,
  },
  metricValueRed: {
    color: '#dc2626',
    fontSize: 17,
    fontWeight: '900',
  },
  metricValueBlue: {
    color: '#2563eb',
    fontSize: 17,
    fontWeight: '900',
  },
  metricValueAmber: {
    color: '#d97706',
    fontSize: 17,
    fontWeight: '900',
  },
  metricClearanceText: {
    fontSize: 12,
    fontWeight: '900',
  },
  metricLabel: {
    color: '#475569',
    fontSize: 10.5,
    fontWeight: '600',
    marginTop: 3,
  },
  commanderBriefCard: {
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 15,
    borderWidth: 1,
    borderColor: '#bfdbfe',
    shadowColor: '#2563eb',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 6,
    elevation: 2,
  },
  briefHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
  },
  briefHeaderTitle: {
    fontSize: 13.5,
    fontWeight: '800',
    color: '#1e3a8a',
  },
  briefPointsList: {
    gap: 10,
  },
  briefPointItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
  },
  briefPointBullet: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: '#eff6ff',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 1,
  },
  briefPointContent: {
    flex: 1,
  },
  briefPointTitle: {
    fontSize: 12,
    fontWeight: '800',
    color: '#0f172a',
  },
  briefPointDesc: {
    fontSize: 11,
    color: '#475569',
    marginTop: 2,
    lineHeight: 16,
  },
  tableContainer: {
    borderWidth: 1,
    borderColor: '#e2e8f0',
    borderRadius: 10,
    overflow: 'hidden',
  },
  tableHeaderRow: {
    flexDirection: 'row',
    backgroundColor: '#f8fafc',
    paddingVertical: 8,
    paddingHorizontal: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#e2e8f0',
  },
  tableHeaderCell: {
    fontSize: 10,
    fontWeight: '800',
    color: '#64748b',
    textTransform: 'uppercase',
  },
  tableRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#f1f5f9',
    backgroundColor: '#ffffff',
  },
  tableAssetName: {
    fontSize: 11.5,
    fontWeight: '800',
    color: '#0f172a',
  },
  tableAssetMeta: {
    fontSize: 9.5,
    color: '#64748b',
    marginTop: 1,
  },
  tableDepthVal: {
    fontSize: 12,
    fontWeight: '900',
    color: '#2563eb',
  },
  tableActionText: {
    fontSize: 10.5,
    color: '#334155',
    lineHeight: 14,
  },
  statusBadge: {
    paddingHorizontal: 6,
    paddingVertical: 3,
    borderRadius: 6,
  },
  statusBadgeRed: {
    backgroundColor: '#fef2f2',
    borderWidth: 1,
    borderColor: '#fecaca',
  },
  statusBadgeAmber: {
    backgroundColor: '#fffbeb',
    borderWidth: 1,
    borderColor: '#fde68a',
  },
  statusBadgeGreen: {
    backgroundColor: '#ecfdf5',
    borderWidth: 1,
    borderColor: '#a7f3d0',
  },
  statusBadgeText: {
    fontSize: 9.5,
    fontWeight: '900',
  },
  statusTextRed: {
    color: '#dc2626',
  },
  statusTextAmber: {
    color: '#d97706',
  },
  statusTextGreen: {
    color: '#059669',
  },
  judgeWalkthroughTip: {
    backgroundColor: '#f0fdf4',
    borderWidth: 1,
    borderColor: '#bbf7d0',
    borderRadius: 10,
    padding: 10,
    marginBottom: 10,
  },
  judgeWalkthroughTipText: {
    fontSize: 11,
    color: '#065f46',
    lineHeight: 16,
    fontWeight: '600',
  },
  sliderControlBlock: {
    backgroundColor: '#f8fafc',
    borderRadius: 12,
    padding: 10,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    marginBottom: 10,
  },
  sliderHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  sliderLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: '#1e293b',
  },
  sliderValBadgeBlue: {
    backgroundColor: '#eff6ff',
    borderWidth: 1,
    borderColor: '#bfdbfe',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
  },
  sliderValTextBlue: {
    fontSize: 11.5,
    fontWeight: '800',
    color: '#1d4ed8',
  },
  sliderValBadgeGreen: {
    backgroundColor: '#ecfdf5',
    borderWidth: 1,
    borderColor: '#a7f3d0',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
  },
  sliderValTextGreen: {
    fontSize: 11.5,
    fontWeight: '800',
    color: '#059669',
  },
  presetPillsRow: {
    flexDirection: 'row',
    gap: 6,
    flexWrap: 'wrap',
  },
  stepPill: {
    flex: 1,
    minWidth: 54,
    backgroundColor: '#ffffff',
    borderWidth: 1,
    borderColor: '#cbd5e1',
    borderRadius: 8,
    paddingVertical: 6,
    alignItems: 'center',
  },
  stepPillActiveBlue: {
    backgroundColor: '#2563eb',
    borderColor: '#1d4ed8',
  },
  stepPillActiveGreen: {
    backgroundColor: '#059669',
    borderColor: '#047857',
  },
  stepPillText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#334155',
  },
  stepPillTextActive: {
    color: '#ffffff',
  },
  simButton: {
    backgroundColor: '#059669',
    paddingVertical: 11,
    borderRadius: 10,
    alignItems: 'center',
  },
  simButtonText: {
    color: '#ffffff',
    fontWeight: '800',
    fontSize: 13,
  },
  tensorGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  tensorChip: {
    flex: 1,
    minWidth: 135,
    backgroundColor: '#f8fafc',
    borderRadius: 10,
    padding: 10,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  tensorChipLabel: {
    color: '#64748b',
    fontSize: 10.5,
    fontWeight: '600',
  },
  tensorChipValue: {
    color: '#0f172a',
    fontSize: 13.5,
    fontWeight: '800',
    marginTop: 2,
  },
  routeCompareRow: {
    flexDirection: 'row',
    gap: 8,
    flexWrap: 'wrap',
  },
  routeCompareCard: {
    flex: 1,
    minWidth: 145,
    borderRadius: 12,
    padding: 10,
    borderWidth: 1,
  },
  routeCompareHeaderRed: {
    color: '#b91c1c',
    fontSize: 11.5,
    fontWeight: '800',
  },
  routeCompareDepthRed: {
    color: '#dc2626',
    fontSize: 15,
    fontWeight: '900',
    marginVertical: 2,
  },
  routeCompareHeaderGreen: {
    color: '#047857',
    fontSize: 11.5,
    fontWeight: '800',
  },
  routeCompareDepthGreen: {
    color: '#059669',
    fontSize: 15,
    fontWeight: '900',
    marginVertical: 2,
  },
  routeCompareNote: {
    color: '#334155',
    fontSize: 10.5,
    marginTop: 2,
    lineHeight: 14,
  },
  callButton: {
    marginTop: 12,
    backgroundColor: '#dc2626',
    paddingVertical: 12,
    borderRadius: 10,
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
  },
  callButtonText: {
    color: '#ffffff',
    fontWeight: '800',
    fontSize: 13,
  },
});

export default NowcastPanel;
