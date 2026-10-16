import React, { useEffect, useState } from 'react';
import { Platform, StyleSheet, Text, View } from 'react-native';
import { WebView } from 'react-native-webview';
import type { LiveView, RunState } from '../services/webIntel';
import { C } from './webIntelUi';

export interface LiveBrowserViewProps {
  liveView: LiveView | null | undefined;
  runState: RunState;
  sourceLabel: string;
  height?: number;
}

const HTTPS_URL = /^https:\/\/[^\s"'<>\\]+$/i;
const MAX_TIMER_MS = 2_147_483_647;

function expiryMs(liveView: LiveView): number {
  const t = new Date(liveView.expires_at).getTime();
  return Number.isNaN(t) ? 0 : t;
}

export default function LiveBrowserView({ liveView, runState, sourceLabel, height = 360 }: LiveBrowserViewProps) {
  const url = liveView && HTTPS_URL.test(liveView.streaming_url) ? liveView.streaming_url : null;
  const expiresAt = liveView ? expiryMs(liveView) : 0;
  const [expired, setExpired] = useState(() => expiresAt <= Date.now());

  useEffect(() => {
    const remaining = expiresAt - Date.now();
    setExpired(remaining <= 0);
    if (remaining <= 0) return;
    const timer = setTimeout(() => setExpired(true), Math.min(remaining, MAX_TIMER_MS));
    return () => clearTimeout(timer);
  }, [expiresAt]);

  if (!url || runState !== 'running' || expired) return null;

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View style={styles.dot} />
        <Text style={styles.title} numberOfLines={1}>
          Live TinyFish browser — {sourceLabel}
        </Text>
      </View>
      {Platform.OS === 'web' ? (
        <iframe
          key={url}
          src={url}
          title={`Live TinyFish browser for ${sourceLabel}`}
          sandbox="allow-scripts allow-same-origin"
          referrerPolicy="no-referrer"
          style={{ width: '100%', height, border: 'none', display: 'block', backgroundColor: '#000' }}
        />
      ) : (
        <WebView
          key={url}
          style={{ width: '100%', height }}
          source={{ uri: url }}
          originWhitelist={['https://*']}
          onShouldStartLoadWithRequest={(req) => req.url.startsWith('https://') || req.url === 'about:blank'}
          setSupportMultipleWindows={false}
          incognito
          javaScriptEnabled
        />
      )}
      <Text style={styles.footer}>
        Read-only view of the real browser session. It closes when the run ends or the link expires.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: C.console,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#1e293b',
    overflow: 'hidden',
    marginVertical: 10,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    gap: 8,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#ef4444',
  },
  title: {
    color: '#10b981',
    fontSize: 12,
    fontWeight: '700',
    flex: 1,
  },
  footer: {
    color: '#94a3b8',
    fontSize: 9.5,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
});
