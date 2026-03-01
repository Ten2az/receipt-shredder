/**
 * screens/DashboardScreen.js — Home dashboard
 * ============================================
 * Shows:
 *   - Monthly spending total + trend vs last month
 *   - Category breakdown (simple bar visualization)
 *   - Recent receipts
 *   - AI nudges + badges
 *   - Quick upload button
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
  RefreshControl, ActivityIndicator
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import api from '../utils/api';

const CATEGORY_COLORS = {
  'Food & Dining': '#ef4444', 'Groceries': '#f97316', 'Transportation': '#3b82f6',
  'Office Supplies': '#8b5cf6', 'Medical': '#10b981', 'Entertainment': '#f59e0b',
  'Software & Tech': '#6366f1', 'Utilities': '#14b8a6', 'Other': '#6b7280'
};

export default function DashboardScreen({ navigation }) {
  const [summary,  setSummary]  = useState(null);
  const [receipts, setReceipts] = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [refresh,  setRefresh]  = useState(false);

  async function load(isRefresh = false) {
    try {
      if (isRefresh) setRefresh(true);
      const [sum, recs] = await Promise.all([
        api.getSummary(),
        api.listReceipts(1)
      ]);
      setSummary(sum);
      setReceipts(recs.receipts?.slice(0, 5) || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
      setRefresh(false);
    }
  }

  useFocusEffect(useCallback(() => { load(); }, []));

  if (loading) {
    return <View style={styles.center}><ActivityIndicator color="#7c3aed" size="large" /></View>;
  }

  const maxCatVal = summary?.by_category
    ? Math.max(...Object.values(summary.by_category), 1)
    : 1;

  return (
    <ScrollView
      style={styles.container}
      refreshControl={<RefreshControl refreshing={refresh} onRefresh={() => load(true)} tintColor="#7c3aed" />}
    >
      <View style={styles.header}>
        <Text style={styles.appName}>🧾 Receipt Shredder</Text>
        <TouchableOpacity
          style={styles.uploadBtn}
          onPress={() => navigation.navigate('Upload')}
        >
          <Text style={styles.uploadBtnText}>+ Scan</Text>
        </TouchableOpacity>
      </View>

      {/* Spending card */}
      <View style={styles.spendCard}>
        <Text style={styles.spendLabel}>This Month</Text>
        <Text style={styles.spendAmount}>
          ${(summary?.total_spent || 0).toFixed(2)}
        </Text>
        {summary?.vs_last_month_pct != null && (
          <Text style={[styles.spendChange, { color: summary.vs_last_month_pct > 0 ? '#ef4444' : '#10b981' }]}>
            {summary.vs_last_month_pct > 0 ? '▲' : '▼'} {Math.abs(summary.vs_last_month_pct).toFixed(1)}% vs last month
          </Text>
        )}
        <View style={styles.deductRow}>
          <Text style={styles.deductLabel}>💰 Deductible: </Text>
          <Text style={styles.deductAmt}>${(summary?.total_deductible || 0).toFixed(2)}</Text>
        </View>
      </View>

      {/* Badges */}
      {summary?.badges?.length > 0 && (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.badgeRow}>
          {summary.badges.map((b, i) => (
            <View key={i} style={styles.badge}>
              <Text style={styles.badgeText}>{b}</Text>
            </View>
          ))}
        </ScrollView>
      )}

      {/* AI Nudges */}
      {summary?.nudges?.length > 0 && (
        <View style={styles.nudgeCard}>
          <Text style={styles.sectionTitle}>💡 Insights</Text>
          {summary.nudges.map((n, i) => (
            <Text key={i} style={styles.nudge}>• {n}</Text>
          ))}
        </View>
      )}

      {/* Category breakdown */}
      {summary?.by_category && Object.keys(summary.by_category).length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>By Category</Text>
          {Object.entries(summary.by_category).slice(0, 6).map(([cat, amt]) => (
            <View key={cat} style={styles.catRow}>
              <Text style={styles.catName}>{cat}</Text>
              <View style={styles.barBg}>
                <View style={[
                  styles.barFill,
                  { width: `${(amt / maxCatVal) * 100}%`, backgroundColor: CATEGORY_COLORS[cat] || '#6b7280' }
                ]} />
              </View>
              <Text style={styles.catAmt}>${amt.toFixed(0)}</Text>
            </View>
          ))}
        </View>
      )}

      {/* Recent receipts */}
      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Recent Receipts</Text>
          <TouchableOpacity onPress={() => navigation.navigate('Receipts')}>
            <Text style={styles.seeAll}>See all</Text>
          </TouchableOpacity>
        </View>
        {receipts.length === 0
          ? <Text style={styles.empty}>No receipts yet. Tap + Scan to add one!</Text>
          : receipts.map(r => (
              <View key={r.id} style={styles.receiptRow}>
                <View>
                  <Text style={styles.receiptVendor}>{r.vendor || 'Unknown'}</Text>
                  <Text style={styles.receiptMeta}>{r.category} · {r.date || 'No date'}</Text>
                </View>
                <View style={styles.receiptRight}>
                  <Text style={styles.receiptTotal}>${(r.total || 0).toFixed(2)}</Text>
                  {r.is_deductible && <Text style={styles.deductBadge}>📋</Text>}
                  {r.needs_review && <Text style={styles.reviewBadge}>⚠️</Text>}
                </View>
              </View>
            ))
        }
      </View>

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container:  { flex: 1, backgroundColor: '#0d0d1a' },
  center:     { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#0d0d1a' },
  header:     { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 20, paddingTop: 56 },
  appName:    { fontSize: 20, fontWeight: '800', color: '#e5e7eb' },
  uploadBtn:  { backgroundColor: '#7c3aed', paddingHorizontal: 16, paddingVertical: 8, borderRadius: 20 },
  uploadBtnText: { color: '#fff', fontWeight: '700' },
  spendCard:  { margin: 16, backgroundColor: '#1a1a2e', borderRadius: 20, padding: 24, borderWidth: 1, borderColor: '#2d2d4e' },
  spendLabel: { color: '#9ca3af', fontSize: 14, marginBottom: 4 },
  spendAmount:{ color: '#e5e7eb', fontSize: 42, fontWeight: '800', letterSpacing: -1 },
  spendChange:{ fontSize: 14, marginTop: 4, fontWeight: '600' },
  deductRow:  { flexDirection: 'row', marginTop: 12, alignItems: 'center' },
  deductLabel:{ color: '#9ca3af', fontSize: 14 },
  deductAmt:  { color: '#10b981', fontSize: 14, fontWeight: '700' },
  badgeRow:   { paddingLeft: 16, marginBottom: 8 },
  badge:      { backgroundColor: '#1e1040', borderRadius: 20, paddingHorizontal: 14, paddingVertical: 7, marginRight: 8, borderWidth: 1, borderColor: '#4c1d95' },
  badgeText:  { color: '#a78bfa', fontSize: 12, fontWeight: '600' },
  nudgeCard:  { margin: 16, marginTop: 8, backgroundColor: '#0f2922', borderRadius: 16, padding: 16, borderWidth: 1, borderColor: '#064e3b' },
  section:    { margin: 16, marginTop: 8 },
  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  sectionTitle:  { color: '#e5e7eb', fontSize: 16, fontWeight: '700', marginBottom: 12 },
  seeAll:     { color: '#7c3aed', fontSize: 13 },
  catRow:     { flexDirection: 'row', alignItems: 'center', marginBottom: 10 },
  catName:    { color: '#9ca3af', fontSize: 13, width: 110 },
  barBg:      { flex: 1, backgroundColor: '#1a1a2e', height: 8, borderRadius: 4, marginHorizontal: 8 },
  barFill:    { height: 8, borderRadius: 4 },
  catAmt:     { color: '#e5e7eb', fontSize: 13, fontWeight: '600', width: 50, textAlign: 'right' },
  receiptRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#1a1a2e', borderRadius: 12, padding: 14, marginBottom: 8 },
  receiptVendor: { color: '#e5e7eb', fontWeight: '600', fontSize: 15 },
  receiptMeta:   { color: '#6b7280', fontSize: 12, marginTop: 2 },
  receiptRight:  { alignItems: 'flex-end' },
  receiptTotal:  { color: '#e5e7eb', fontWeight: '700', fontSize: 15 },
  deductBadge:   { fontSize: 14 },
  reviewBadge:   { fontSize: 14 },
  nudge:      { color: '#6ee7b7', fontSize: 14, marginBottom: 4 },
  empty:      { color: '#6b7280', textAlign: 'center', paddingVertical: 20 }
});
