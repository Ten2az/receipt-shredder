/**
 * screens/SettingsScreen.js — Profile, premium, privacy, logout
 */

import React, { useEffect, useState } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, Switch,
  Alert, Linking, ScrollView, ActivityIndicator
} from 'react-native';
import api from '../utils/api';
import { useAuth } from '../utils/AuthContext';
import { clearToken } from '../utils/AuthContext';

export default function SettingsScreen() {
  const { authState, setAuthState } = useAuth();
  const [user,      setUser]       = useState(null);
  const [loading,   setLoading]    = useState(true);
  const [upgrading, setUpgrading]  = useState(false);

  useEffect(() => {
    api.getMe().then(setUser).finally(() => setLoading(false));
  }, []);

  async function handleUpgrade() {
    setUpgrading(true);
    try {
      const { checkout_url } = await api.createCheckout();
      Linking.openURL(checkout_url);
    } catch (e) {
      Alert.alert('Error', e.message);
    } finally {
      setUpgrading(false);
    }
  }

  function handleLogout() {
    Alert.alert('Log out?', 'You can log back in anytime.', [
      { text: 'Cancel' },
      { text: 'Log Out', style: 'destructive', onPress: () => clearToken(setAuthState) }
    ]);
  }

  if (loading) return <View style={styles.center}><ActivityIndicator color="#7c3aed" /></View>;

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>Settings</Text>

      {/* Account info */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Account</Text>
        <View style={styles.row}>
          <Text style={styles.rowLabel}>Email</Text>
          <Text style={styles.rowValue}>{user?.email}</Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.rowLabel}>Plan</Text>
          <Text style={[styles.rowValue, user?.is_premium && styles.premiumBadge]}>
            {user?.is_premium ? '⭐ Premium' : 'Free (20 scans/month)'}
          </Text>
        </View>
        {user?.profile && (
          <>
            <View style={styles.row}>
              <Text style={styles.rowLabel}>State</Text>
              <Text style={styles.rowValue}>{user.profile.state}</Text>
            </View>
            <View style={styles.row}>
              <Text style={styles.rowLabel}>User Type</Text>
              <Text style={styles.rowValue}>{user.profile.user_type}</Text>
            </View>
          </>
        )}
      </View>

      {/* Premium upgrade */}
      {!user?.is_premium && (
        <View style={styles.premiumCard}>
          <Text style={styles.premiumTitle}>⭐ Upgrade to Premium</Text>
          <Text style={styles.premiumPrice}>$4.99/month</Text>
          <View style={styles.featureList}>
            {[
              'Unlimited receipt scans',
              'PDF export (IRS-ready)',
              'Batch upload (10 at once)',
              'Family sharing (coming soon)',
              'TurboTax export (coming soon)',
            ].map((f, i) => (
              <Text key={i} style={styles.feature}>✓ {f}</Text>
            ))}
          </View>
          <TouchableOpacity
            style={[styles.upgradeBtn, upgrading && { opacity: 0.6 }]}
            onPress={handleUpgrade}
            disabled={upgrading}
          >
            {upgrading
              ? <ActivityIndicator color="#fff" />
              : <Text style={styles.upgradeBtnText}>Upgrade Now</Text>
            }
          </TouchableOpacity>
        </View>
      )}

      {/* Privacy */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Privacy</Text>
        <View style={styles.row}>
          <View>
            <Text style={styles.rowLabel}>🔒 Encrypted Storage</Text>
            <Text style={styles.rowSub}>All data encrypted with Fernet</Text>
          </View>
          <Text style={styles.activeTag}>Active</Text>
        </View>
        <View style={styles.row}>
          <View>
            <Text style={styles.rowLabel}>🚫 No Data Sharing</Text>
            <Text style={styles.rowSub}>Your receipts never leave our servers</Text>
          </View>
          <Text style={styles.activeTag}>Active</Text>
        </View>
      </View>

      {/* About */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>About</Text>
        <TouchableOpacity style={styles.linkRow} onPress={() => Linking.openURL('https://your-app.vercel.app/privacy')}>
          <Text style={styles.link}>Privacy Policy</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.linkRow} onPress={() => Linking.openURL('https://your-app.vercel.app/terms')}>
          <Text style={styles.link}>Terms of Service</Text>
        </TouchableOpacity>
        <View style={styles.row}>
          <Text style={styles.rowLabel}>Version</Text>
          <Text style={styles.rowValue}>1.0.0</Text>
        </View>
      </View>

      {/* Logout */}
      <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
        <Text style={styles.logoutText}>Log Out</Text>
      </TouchableOpacity>

      <View style={{ height: 60 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container:    { flex: 1, backgroundColor: '#0d0d1a', padding: 16 },
  center:       { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#0d0d1a' },
  title:        { fontSize: 24, fontWeight: '800', color: '#e5e7eb', marginTop: 56, marginBottom: 20 },
  section:      { backgroundColor: '#1a1a2e', borderRadius: 16, padding: 16, marginBottom: 14, borderWidth: 1, borderColor: '#2d2d4e' },
  sectionTitle: { color: '#9ca3af', fontSize: 12, fontWeight: '700', letterSpacing: 1, marginBottom: 12, textTransform: 'uppercase' },
  row:          { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 10, borderTopWidth: 1, borderTopColor: '#0d0d1a' },
  rowLabel:     { color: '#d1d5db', fontSize: 15 },
  rowSub:       { color: '#6b7280', fontSize: 12, marginTop: 1 },
  rowValue:     { color: '#9ca3af', fontSize: 14 },
  premiumBadge: { color: '#f59e0b', fontWeight: '700' },
  activeTag:    { color: '#10b981', fontSize: 12, fontWeight: '600' },
  premiumCard:  { backgroundColor: '#1e1040', borderRadius: 20, padding: 20, marginBottom: 14, borderWidth: 1, borderColor: '#4c1d95' },
  premiumTitle: { fontSize: 18, fontWeight: '800', color: '#e5e7eb' },
  premiumPrice: { fontSize: 32, fontWeight: '800', color: '#7c3aed', marginVertical: 8 },
  featureList:  { marginBottom: 16 },
  feature:      { color: '#a78bfa', fontSize: 14, paddingVertical: 3 },
  upgradeBtn:   { backgroundColor: '#7c3aed', borderRadius: 12, padding: 16, alignItems: 'center' },
  upgradeBtnText: { color: '#fff', fontWeight: '800', fontSize: 16 },
  linkRow:      { paddingVertical: 12, borderTopWidth: 1, borderTopColor: '#0d0d1a' },
  link:         { color: '#7c3aed', fontSize: 15 },
  logoutBtn:    { backgroundColor: '#2d1515', borderRadius: 12, padding: 16, alignItems: 'center', marginTop: 8 },
  logoutText:   { color: '#ef4444', fontWeight: '700', fontSize: 16 }
});
