import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Platform,
} from 'react-native';
import {
  Send,
  Bot,
  User,
  Sparkles,
  Layers,
  MapPin,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  FileText,
} from 'lucide-react-native';
import { apiService, DetectionResult } from '../services/api';

interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  toolCalls?: Array<{
    tool_name: string;
    args: any;
    result_summary?: string;
  }>;
  citations?: string[];
  geocodedCoords?: [number, number];
  timestamp: string;
}

interface ChatbotPanelProps {
  lastResult?: DetectionResult | null;
  activeLocationName?: string;
  onNavigateToCoords?: (lat: number, lon: number, name?: string) => void;
  onOpenReportModal?: () => void;
}

const STARTER_PROMPTS = [
  { label: '🌊 Galveston Flood Risk', prompt: 'What is the flood risk around Galveston, Texas?' },
  { label: '🏔️ Aspen Terrain & Slope', prompt: 'Check terrain elevation and slope in Aspen, CO' },
  { label: '🔮 24h TWI Runoff Watch', prompt: 'Run a 24-hour predictive TWI runoff accumulation forecast for this active area' },
  { label: '🏃 Find High-Ground Shelters', prompt: 'Find the nearest elevation-safe evacuation shelters and road corridors nearby' },
];

export const ChatbotPanel: React.FC<ChatbotPanelProps> = ({
  lastResult,
  activeLocationName,
  onNavigateToCoords,
  onOpenReportModal,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'init-1',
      sender: 'assistant',
      text: 'Hello! I am Project Aegis AI — powered by Google Gemini 2.5 Flash with real-time MirEye Earth API geospatial intelligence.\n\nAsk me anything about real-time flood risk, terrain elevation, D8 runoff pooling, evacuation routes, or municipal disaster mitigation for any location in the US or globally.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [expandedTools, setExpandedTools] = useState<Record<string, boolean>>({});

  const scrollViewRef = useRef<ScrollView>(null);

  useEffect(() => {
    scrollViewRef.current?.scrollToEnd({ animated: true });
  }, [messages, isLoading]);

  const toggleToolExpand = (id: string) => {
    setExpandedTools(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const handleSend = async (customText?: string) => {
    const textToSend = (customText || inputText).trim();
    if (!textToSend || isLoading) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages(prev => [...prev, userMsg]);
    if (!customText) setInputText('');
    setIsLoading(true);

    try {
      const locationContext = lastResult
        ? {
            location: activeLocationName || 'Active Scan Area',
            area_sq_km: lastResult.area_sq_km,
            severity: lastResult.severity,
            affected_population: lastResult.impact.population,
            damaged_buildings: lastResult.impact.buildings,
          }
        : activeLocationName
        ? { location: activeLocationName }
        : null;

      const conversationHistory = messages.slice(-8).map(m => ({
        role: m.sender === 'user' ? 'user' : 'assistant',
        content: m.text,
      }));

      const res = await apiService.sendChatMessage(textToSend, conversationHistory, locationContext);

      const botMsg: ChatMessage = {
        id: `bot-${Date.now()}`,
        sender: 'assistant',
        text: res.reply || res.response || 'Analysis complete.',
        toolCalls: res.tool_calls_executed || [],
        citations: res.citations || [],
        geocodedCoords: res.geocoded_coords || undefined,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages(prev => [...prev, botMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        sender: 'assistant',
        text: `Error contacting Aegis Chatbot service: ${err.message || 'Network error'}. Please ensure the backend is running.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      {/* Modern SaaS Header Banner */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <View style={styles.botBadge}>
            <Sparkles size={17} color="#059669" />
          </View>
          <View>
            <View style={styles.titleRow}>
              <Text style={styles.headerTitle}>Aegis Intelligent Assistant</Text>
              <View style={styles.onlinePill}>
                <View style={styles.onlineDot} />
                <Text style={styles.onlineText}>Ready</Text>
              </View>
            </View>
            <Text style={styles.headerSubtitle}>Google Gemini 2.5 Flash × MirEye Earth API</Text>
          </View>
        </View>
        {lastResult && onOpenReportModal && (
          <TouchableOpacity style={styles.reportHeaderBtn} onPress={onOpenReportModal} activeOpacity={0.8}>
            <FileText size={13} color="#059669" />
            <Text style={styles.reportHeaderBtnText}>Bulletin PDF</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Messages Scroll Area */}
      <ScrollView
        ref={scrollViewRef}
        style={styles.messageScroll}
        contentContainerStyle={styles.messageList}
        showsVerticalScrollIndicator={false}
      >
        {messages.map(msg => {
          const isUser = msg.sender === 'user';
          return (
            <View
              key={msg.id}
              style={[
                styles.messageRow,
                isUser ? styles.userRow : styles.botRow,
              ]}
            >
              {!isUser && (
                <View style={styles.avatarBot}>
                  <Bot size={15} color="#059669" />
                </View>
              )}

              <View style={[styles.bubble, isUser ? styles.userBubble : styles.botBubble]}>
                {/* Tool Calls Execution Pill */}
                {!isUser && msg.toolCalls && msg.toolCalls.length > 0 && (
                  <View style={styles.toolCallsContainer}>
                    {msg.toolCalls.map((tc, idx) => {
                      const toolKey = `${msg.id}-tool-${idx}`;
                      const isExpanded = !!expandedTools[toolKey];
                      return (
                        <View key={toolKey} style={styles.toolCard}>
                          <TouchableOpacity
                            style={styles.toolCardHeader}
                            onPress={() => toggleToolExpand(toolKey)}
                            activeOpacity={0.8}
                          >
                            <View style={styles.toolCardLeft}>
                              <Layers size={13} color="#059669" />
                              <Text style={styles.toolNameText}>
                                Tool: <Text style={styles.toolNameHighlight}>{tc.tool_name}</Text>
                              </Text>
                            </View>
                            {isExpanded ? (
                              <ChevronUp size={13} color="#64748b" />
                            ) : (
                              <ChevronDown size={13} color="#64748b" />
                            )}
                          </TouchableOpacity>
                          {isExpanded && (
                            <View style={styles.toolDetails}>
                              <Text style={styles.toolArgsText}>
                                Args: {JSON.stringify(tc.args, null, 2)}
                              </Text>
                              {tc.result_summary ? (
                                <Text style={styles.toolResultText}>
                                  Summary: {tc.result_summary}
                                </Text>
                              ) : null}
                            </View>
                          )}
                        </View>
                      );
                    })}
                  </View>
                )}

                {/* Message Text */}
                <Text style={[styles.messageText, isUser ? styles.userText : styles.botText]}>
                  {msg.text}
                </Text>

                {/* Geocoded Navigation Chip */}
                {!isUser && msg.geocodedCoords && onNavigateToCoords && (
                  <TouchableOpacity
                    style={styles.geoNavigateBtn}
                    onPress={() =>
                      onNavigateToCoords(
                        msg.geocodedCoords![0],
                        msg.geocodedCoords![1],
                        'Selected from Chat'
                      )
                    }
                    activeOpacity={0.8}
                  >
                    <MapPin size={13} color="#059669" />
                    <Text style={styles.geoNavigateText}>
                      View Location on Map ({msg.geocodedCoords[0].toFixed(3)}°, {msg.geocodedCoords[1].toFixed(3)}°)
                    </Text>
                  </TouchableOpacity>
                )}

                {/* Citation Badges */}
                {!isUser && msg.citations && msg.citations.length > 0 && (
                  <View style={styles.citationsContainer}>
                    <Text style={styles.citationsLabel}>Official Data Sources:</Text>
                    <View style={styles.citationChipsWrap}>
                      {msg.citations.map((c, i) => (
                        <View key={i} style={styles.citationChip}>
                          <CheckCircle2 size={11} color="#059669" />
                          <Text style={styles.citationText}>{c}</Text>
                        </View>
                      ))}
                    </View>
                  </View>
                )}

                <Text style={[styles.timeText, isUser ? styles.userTimeText : styles.botTimeText]}>
                  {msg.timestamp}
                </Text>
              </View>

              {isUser && (
                <View style={styles.avatarUser}>
                  <User size={15} color="#ffffff" />
                </View>
              )}
            </View>
          );
        })}

        {isLoading && (
          <View style={[styles.messageRow, styles.botRow]}>
            <View style={styles.avatarBot}>
              <Bot size={15} color="#059669" />
            </View>
            <View style={[styles.bubble, styles.botBubble, styles.loadingBubble]}>
              <ActivityIndicator size="small" color="#059669" />
              <Text style={styles.loadingText}>
                Querying MirEye Earth API & Gemini 2.5 Flash reasoning...
              </Text>
            </View>
          </View>
        )}
      </ScrollView>

      {/* Quick Starter Chips */}
      <View style={styles.starterContainer}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.starterScroll}>
          {STARTER_PROMPTS.map((sp, idx) => (
            <TouchableOpacity
              key={idx}
              style={styles.starterChip}
              onPress={() => handleSend(sp.prompt)}
              disabled={isLoading}
              activeOpacity={0.75}
            >
              <Text style={styles.starterChipText}>{sp.label}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      {/* Input Bar */}
      <View style={styles.inputContainer}>
        <View style={styles.inputPill}>
          <TextInput
            style={styles.textInput}
            placeholder="Ask about flood risk, elevation, TWI runoff, shelters..."
            placeholderTextColor="#94a3b8"
            value={inputText}
            onChangeText={setInputText}
            multiline={false}
            onSubmitEditing={() => handleSend()}
            returnKeyType="send"
            editable={!isLoading}
          />
          <TouchableOpacity
            style={[styles.sendButton, (!inputText.trim() || isLoading) && styles.sendButtonDisabled]}
            onPress={() => handleSend()}
            disabled={!inputText.trim() || isLoading}
            activeOpacity={0.85}
          >
            <Send size={15} color="#ffffff" />
          </TouchableOpacity>
        </View>
      </View>
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
    paddingVertical: 12,
    backgroundColor: '#ffffff',
    borderBottomWidth: 1,
    borderBottomColor: '#f1f5f9',
    shadowColor: '#0f172a',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.03,
    shadowRadius: 3,
    elevation: 1,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  botBadge: {
    width: 36,
    height: 36,
    borderRadius: 11,
    backgroundColor: '#ecfdf5',
    borderWidth: 1,
    borderColor: '#a7f3d0',
    justifyContent: 'center',
    alignItems: 'center',
  },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  headerTitle: {
    color: '#0f172a',
    fontSize: 14,
    fontWeight: '700',
    letterSpacing: -0.2,
  },
  onlinePill: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#ecfdf5',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#d1fae5',
  },
  onlineDot: {
    width: 5,
    height: 5,
    borderRadius: 2.5,
    backgroundColor: '#10b981',
    marginRight: 4,
  },
  onlineText: {
    fontSize: 9,
    fontWeight: '700',
    color: '#059669',
  },
  headerSubtitle: {
    color: '#64748b',
    fontSize: 11,
    marginTop: 1,
  },
  reportHeaderBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 11,
    paddingVertical: 5.5,
    borderRadius: 20,
    backgroundColor: '#ecfdf5',
    borderWidth: 1,
    borderColor: '#a7f3d0',
  },
  reportHeaderBtnText: {
    color: '#059669',
    fontSize: 11,
    fontWeight: '700',
  },
  messageScroll: {
    flex: 1,
    backgroundColor: '#f8fafc',
  },
  messageList: {
    paddingHorizontal: 14,
    paddingVertical: 14,
    gap: 12,
  },
  messageRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
  },
  userRow: {
    justifyContent: 'flex-end',
  },
  botRow: {
    justifyContent: 'flex-start',
  },
  avatarBot: {
    width: 30,
    height: 30,
    borderRadius: 9,
    backgroundColor: '#ecfdf5',
    borderWidth: 1,
    borderColor: '#a7f3d0',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 2,
  },
  avatarUser: {
    width: 30,
    height: 30,
    borderRadius: 9,
    backgroundColor: '#059669',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 2,
  },
  bubble: {
    maxWidth: '82%',
    borderRadius: 18,
    paddingHorizontal: 14,
    paddingVertical: 11,
  },
  userBubble: {
    backgroundColor: '#059669',
    borderBottomRightRadius: 4,
    shadowColor: '#059669',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.18,
    shadowRadius: 5,
    elevation: 2,
  },
  botBubble: {
    backgroundColor: '#ffffff',
    borderWidth: 1,
    borderColor: '#e2e8f0',
    borderBottomLeftRadius: 4,
    shadowColor: '#0f172a',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 1,
  },
  loadingBubble: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 12,
  },
  loadingText: {
    color: '#059669',
    fontSize: 12,
    fontWeight: '500',
  },
  messageText: {
    fontSize: 13.5,
    lineHeight: 20,
  },
  userText: {
    color: '#ffffff',
    fontWeight: '500',
  },
  botText: {
    color: '#1e293b',
  },
  toolCallsContainer: {
    marginBottom: 8,
    gap: 5,
  },
  toolCard: {
    backgroundColor: '#f8fafc',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    overflow: 'hidden',
  },
  toolCardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 9,
    paddingVertical: 5,
    backgroundColor: '#f1f5f9',
  },
  toolCardLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  toolNameText: {
    color: '#64748b',
    fontSize: 10.5,
  },
  toolNameHighlight: {
    color: '#059669',
    fontWeight: '700',
  },
  toolDetails: {
    padding: 8,
    backgroundColor: '#ffffff',
    borderTopWidth: 1,
    borderTopColor: '#e2e8f0',
  },
  toolArgsText: {
    color: '#334155',
    fontSize: 10.5,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  toolResultText: {
    color: '#64748b',
    fontSize: 10.5,
    marginTop: 3,
  },
  geoNavigateBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#ecfdf5',
    borderWidth: 1,
    borderColor: '#a7f3d0',
    borderRadius: 16,
    paddingHorizontal: 11,
    paddingVertical: 6,
    marginTop: 9,
    alignSelf: 'flex-start',
  },
  geoNavigateText: {
    color: '#047857',
    fontSize: 11.5,
    fontWeight: '600',
  },
  citationsContainer: {
    marginTop: 8,
    paddingTop: 7,
    borderTopWidth: 1,
    borderTopColor: '#f1f5f9',
  },
  citationsLabel: {
    color: '#64748b',
    fontSize: 10,
    fontWeight: '700',
    marginBottom: 4,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  citationChipsWrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 5,
  },
  citationChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: '#f0fdf4',
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#dcfce7',
  },
  citationText: {
    color: '#166534',
    fontSize: 10.5,
    fontWeight: '600',
  },
  timeText: {
    fontSize: 9.5,
    alignSelf: 'flex-end',
    marginTop: 4,
  },
  userTimeText: {
    color: 'rgba(255, 255, 255, 0.75)',
  },
  botTimeText: {
    color: '#94a3b8',
  },
  starterContainer: {
    paddingVertical: 7,
    backgroundColor: '#ffffff',
    borderTopWidth: 1,
    borderTopColor: '#f1f5f9',
  },
  starterScroll: {
    paddingHorizontal: 14,
    gap: 7,
  },
  starterChip: {
    backgroundColor: '#f8fafc',
    borderWidth: 1,
    borderColor: '#e2e8f0',
    paddingHorizontal: 11,
    paddingVertical: 5,
    borderRadius: 18,
  },
  starterChipText: {
    color: '#334155',
    fontSize: 11.5,
    fontWeight: '600',
  },
  inputContainer: {
    paddingHorizontal: 12,
    paddingVertical: 9,
    backgroundColor: '#ffffff',
    borderTopWidth: 1,
    borderTopColor: '#f1f5f9',
  },
  inputPill: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#f8fafc',
    borderWidth: 1,
    borderColor: '#e2e8f0',
    borderRadius: 24,
    paddingLeft: 14,
    paddingRight: 5,
    paddingVertical: 4,
  },
  textInput: {
    flex: 1,
    color: '#0f172a',
    fontSize: 13,
    paddingVertical: 6,
  },
  sendButton: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#059669',
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#059669',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 4,
    elevation: 2,
  },
  sendButtonDisabled: {
    backgroundColor: '#cbd5e1',
    shadowOpacity: 0,
  },
});
