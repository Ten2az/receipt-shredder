/**
 * screens/InsightsScreen.js — Visual spending analysis
 * =====================================================
 * Charts: SVG-based bar chart (no Chart.js dependency for RN)
 * Shows: 6-month trend, category pie, deductibles by type
 */

import React, { useEffect, useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, TouchableOpacity,
  ActivityIndicator, Linking
} from 'react-native';
import { Svg, Rect, Text as SvgText, G } from 'react-native-svg';
import api from '../utils/api';

const COLORS = ['#7c3aed','#10b981','#3b82f6','#f59e0b','#ef4444','#8b5cf6','#14b8a6'];

export default function InsightsScreen() {
  const [trends,      setTrends]      = useState(null);
  const [deductibles, setDeductibles] = useState(null);
  const [loading,     setLoading]     = useState(true);

  useEffect(() => {
    Promise.all([
      api.getTrends(6),
      api.getDeductibles()
    ]).then(([t, d]) => {
      setTrends(t.trends);
      setDeductibles(d);
    }).finally(() => setLoading(false));
  }, []);

  async function handleExportCsv() {
    const url = api.exportCsvUrl(null, new Date().getFullYear().toString());
    // On web: open in new tab. On native: share sheet.
    Linking.openURL(url).catch(() => {});
  }

  if (loading) return <View style={styles.center}><ActivityIndicator color="#7c3aed" size="large" /></View>;

  const maxTrend = trends ? Math.max(...trends.map(t => t.total), 1) : 1;

  return (
    <ScrollView style={styles.container} showsVerticalScrollIndicator={false}>
      <Text style={styles.title}>Insights</Text>

      {/* 6-month spending bar chart */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Monthly Spending</Text>
        {trends && (
          <Svg width="100%" height={140} viewBox={`0 0 ${trends.length * 50} 120`}>
            {trends.map((t, i) => {
              const barH = (t.total / maxTrend) * 90;
              const x = i * 50 + 8;
              const y = 100 - barH;
              return (
                <G key={i}>
                  <Rect
                    x={x} y={y} width={34} height={barH}
                    rx={4} fill={i === trends.length - 1 ? '#7c3aed' : '#2d2d4e'}
                  />
                  <SvgText
                    x={x + 17} y={115}
                    textAnchor="middle" fontSize={9} fill="#6b7280"
                  >
                    {t.month.slice(5)}
                  </SvgText>
                  {t.total > 0 && (
                    <SvgText
                      x={x + 17} y={y - 4}
                      textAnchor="middle" fontSize={8} fill="#9ca3af"
                    >
                      ${t.total.toFixed(0)}
                    </SvgText>
                  )}
                </G>
              );
            })}
          </Svg>
        )}
      </View>

      {/* Deductibles summary */}
      {deductibles && (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Tax Deductibles — {deductibles.year}</Text>

          <View style={styles.bigRow}>
            <View style={styles.bigStat}>
              <Text style={styles.bigNum}>${deductibles.total_deductible.toFixed(2)}</Text>
              <Text style={styles.bigLabel}>Total Deductible</Text>
            </View>
            <View style={styles.bigStat}>
              <Text style={[styles.bigNum, { color: '#10b981' }]}>
                ${deductibles.estimated_tax_savings.toFixed(2)}
              </Text>
              <Text style={styles.bigLabel}>Est. Tax Savings</Text>
            </View>
          </View>

          {deductibles.by_type.map((d, i) => (
            <View key={i} style={styles.dedRow}>
              <View style={[styles.dedDot, { backgroundColor: COLORS[i % COLORS.length] }]} />
              <Text style={styles.dedType}>{d.type}</Text>
              <Text style={styles.dedCount}>{d.count} receipts</Text>
              <Text style={styles.dedAmt}>${d.total.toFixed(2)}</Text>
            </View>
          ))}

          {deductibles.by_type.length === 0 && (
            <Text style={styles.empty}>No deductible expenses yet. Upload receipts and mark them!</Text>
          )}

          <Text style={styles.disclaimer}>
            * Est. savings based on 22% tax bracket. Consult a tax professional.
          </Text>
        </View>
      )}

      {/* Export */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Export Reports</Text>
        <TouchableOpacity style={styles.exportBtn} onPress={handleExportCsv}>
          <Text style={styles.exportBtnText}>📊 Download CSV (Free)</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.exportBtn, styles.exportBtnPremium]}
          onPress={() => Linking.openURL('/settings')}
        >
          <Text style={styles.exportBtnText}>📄 Download PDF (Premium)</Text>
        </TouchableOpacity>
        <Text style={styles.exportNote}>
          PDF includes IRS Schedule C notes and state-specific deduction guidance.
        </Text>
      </View>

      <View style={{ height: 60 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0d0d1a', padding: 16 },
  center:    { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#0d0d1a' },
  title:     { fontSize: 24, fontWeight: '800', color: '#e5e7eb', marginTop: 56, marginBottom: 16 },
  card:      { backgroundColor: '#1a1a2e', borderRadius: 20, padding: 20, marginBottom: 14, borderWidth: 1, borderColor: '#2d2d4e' },
  cardTitle: { fontSize: 16, fontWeight: '700', color: '#e5e7eb', marginBottom: 14 },
  bigRow:    { flexDirection: 'row', justifyContent: 'space-around', marginBottom: 16 },
  bigStat:   { alignItems: 'center' },
  bigNum:    { fontSize: 28, fontWeight: '800', color: '#7c3aed' },
  bigLabel:  { color: '#9ca3af', fontSize: 12, marginTop: 2 },
  dedRow:    { flexDirection: 'row', alignItems: 'center', paddingVertical: 8, borderTopWidth: 1, borderTopColor: '#2d2d4e' },
  dedDot:    { width: 10, height: 10, borderRadius: 5, marginRight: 10 },
  dedType:   { color: '#d1d5db', flex: 1, fontSize: 14 },
  dedCount:  { color: '#6b7280', fontSize: 12, marginRight: 12 },
  dedAmt:    { color: '#e5e7eb', fontWeight: '700', fontSize: 14 },
  disclaimer:{ color: '#4b5563', fontSize: 11, marginTop: 12 },
  empty:     { color: '#6b7280', textAlign: 'center', paddingVertical: 16 },
  exportBtn: { backgroundColor: '#0d0d1a', borderRadius: 12, padding: 14, alignItems: 'center', marginBottom: 10, borderWidth: 1, borderColor: '#374151' },
  exportBtnPremium: { borderColor: '#7c3aed' },
  exportBtnText:    { color: '#e5e7eb', fontWeight: '600' },
  exportNote:       { color: '#6b7280', fontSize: 11, textAlign: 'center' }
});
