/**
 * screens/UploadScreen.js — Receipt photo capture and upload
 * ===========================================================
 * Features:
 *   - Camera capture (Expo Camera)
 *   - Gallery picker (Expo ImagePicker)
 *   - Blurry image warning
 *   - Upload progress + result display
 *   - Inline correction form
 */

import React, { useState } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, Image, ScrollView,
  ActivityIndicator, Alert, TextInput, Modal
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import api from '../utils/api';

const CATEGORIES = ['Food & Dining','Groceries','Transportation','Gas & Fuel',
  'Office Supplies','Software & Tech','Medical','Entertainment','Utilities',
  'Home Office','Education','Travel','Clothing','Personal Care','Other'];

export default function UploadScreen() {
  const [imageUri,  setImageUri]  = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result,    setResult]    = useState(null);
  const [correcting,setCorrecting]= useState(false);
  const [correction,setCorrection]= useState({});

  async function pickFromCamera() {
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) return Alert.alert('Permission needed', 'Camera access required');
    const res = await ImagePicker.launchCameraAsync({
      quality: 0.85, mediaTypes: ImagePicker.MediaTypeOptions.Images
    });
    if (!res.canceled) {
      setImageUri(res.assets[0].uri);
      setResult(null);
    }
  }

  async function pickFromGallery() {
    const res = await ImagePicker.launchImageLibraryAsync({
      quality: 0.85, mediaTypes: ImagePicker.MediaTypeOptions.Images
    });
    if (!res.canceled) {
      setImageUri(res.assets[0].uri);
      setResult(null);
    }
  }

  async function uploadImage() {
    if (!imageUri) return;
    setUploading(true);
    try {
      const data = await api.uploadReceipt(imageUri);
      setResult(data);
    } catch (e) {
      Alert.alert('Upload failed', e.message);
    } finally {
      setUploading(false);
    }
  }

  async function submitCorrection() {
    if (!result?.receipt_id) return;
    try {
      await api.submitFeedback(result.receipt_id, -1, {
        corrected_category: correction.category || undefined,
        corrected_vendor:   correction.vendor   || undefined,
        corrected_total:    correction.total ? parseFloat(correction.total) : undefined,
        corrected_date:     correction.date  || undefined,
      });
      setResult(r => ({
        ...r,
        category: correction.category || r.category,
        vendor:   correction.vendor   || r.vendor,
        total:    correction.total ? parseFloat(correction.total) : r.total,
      }));
      setCorrecting(false);
      Alert.alert('Thanks!', 'Correction saved. AI will improve over time.');
    } catch (e) {
      Alert.alert('Error', e.message);
    }
  }

  async function thumbsUp() {
    if (!result?.receipt_id) return;
    await api.submitFeedback(result.receipt_id, 1);
    Alert.alert('✅ Noted!', 'Thanks for the feedback.');
  }

  function reset() {
    setImageUri(null);
    setResult(null);
    setCorrection({});
  }

  return (
    <ScrollView style={styles.container} showsVerticalScrollIndicator={false}>
      <Text style={styles.title}>Scan Receipt</Text>

      {/* Image preview */}
      {imageUri ? (
        <View style={styles.preview}>
          <Image source={{ uri: imageUri }} style={styles.previewImage} resizeMode="contain" />
          {result?.blurry_warning && (
            <View style={styles.blurWarning}>
              <Text style={styles.blurText}>⚠️ Image appears blurry — results may be inaccurate</Text>
            </View>
          )}
        </View>
      ) : (
        <View style={styles.placeholder}>
          <Text style={styles.placeholderIcon}>📷</Text>
          <Text style={styles.placeholderText}>Take a photo or select from gallery</Text>
        </View>
      )}

      {/* Action buttons */}
      <View style={styles.btnRow}>
        <TouchableOpacity style={styles.actionBtn} onPress={pickFromCamera}>
          <Text style={styles.actionBtnText}>📷 Camera</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.actionBtn} onPress={pickFromGallery}>
          <Text style={styles.actionBtnText}>🖼 Gallery</Text>
        </TouchableOpacity>
      </View>

      {imageUri && !result && (
        <TouchableOpacity
          style={[styles.uploadBtn, uploading && styles.uploadBtnDisabled]}
          onPress={uploadImage}
          disabled={uploading}
        >
          {uploading
            ? <><ActivityIndicator color="#fff" /><Text style={styles.uploadBtnText}> Processing...</Text></>
            : <Text style={styles.uploadBtnText}>🔍 Extract & Categorize</Text>
          }
        </TouchableOpacity>
      )}

      {/* Result card */}
      {result && (
        <View style={styles.resultCard}>
          <Text style={styles.resultTitle}>✅ Receipt Processed</Text>

          <Row label="Vendor"   value={result.vendor} />
          <Row label="Date"     value={result.date} />
          <Row label="Total"    value={result.total != null ? `$${result.total.toFixed(2)}` : '–'} />
          <Row label="Category" value={result.category} />

          {result.is_deductible && (
            <View style={styles.deductBadge}>
              <Text style={styles.deductBadgeText}>
                💰 Tax Deductible — {result.deductible_type}
              </Text>
            </View>
          )}

          {result.state_notes && (
            <View style={styles.stateNote}>
              <Text style={styles.stateNoteText}>📍 {result.state_notes}</Text>
            </View>
          )}

          {result.nudge && (
            <View style={styles.nudge}>
              <Text style={styles.nudgeText}>💡 {result.nudge}</Text>
            </View>
          )}

          <View style={styles.confidenceRow}>
            <Text style={styles.confLabel}>AI Confidence: </Text>
            <Text style={[styles.confVal, { color: result.confidence > 0.7 ? '#10b981' : '#f59e0b' }]}>
              {Math.round((result.confidence || 0) * 100)}%
              {result.confidence < 0.65 ? ' ⚠️ review recommended' : ''}
            </Text>
          </View>

          <View style={styles.feedbackRow}>
            <TouchableOpacity style={styles.thumbBtn} onPress={thumbsUp}>
              <Text style={styles.thumbText}>👍 Correct</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.thumbBtn, styles.thumbBtnRed]} onPress={() => setCorrecting(true)}>
              <Text style={styles.thumbText}>✏️ Fix It</Text>
            </TouchableOpacity>
          </View>

          <TouchableOpacity style={styles.resetBtn} onPress={reset}>
            <Text style={styles.resetText}>Scan Another</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Correction modal */}
      <Modal visible={correcting} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modal}>
            <Text style={styles.modalTitle}>Correct This Receipt</Text>

            <Text style={styles.inputLabel}>Category</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 12 }}>
              {CATEGORIES.map(c => (
                <TouchableOpacity
                  key={c}
                  style={[styles.catChip, correction.category === c && styles.catChipActive]}
                  onPress={() => setCorrection(prev => ({ ...prev, category: c }))}
                >
                  <Text style={[styles.catChipText, correction.category === c && styles.catChipTextActive]}>{c}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>

            <Text style={styles.inputLabel}>Vendor (optional)</Text>
            <TextInput
              style={styles.corrInput}
              placeholder="Correct vendor name"
              placeholderTextColor="#6b7280"
              value={correction.vendor || ''}
              onChangeText={t => setCorrection(p => ({ ...p, vendor: t }))}
            />

            <Text style={styles.inputLabel}>Total (optional)</Text>
            <TextInput
              style={styles.corrInput}
              placeholder="e.g. 24.50"
              placeholderTextColor="#6b7280"
              value={correction.total || ''}
              onChangeText={t => setCorrection(p => ({ ...p, total: t }))}
              keyboardType="decimal-pad"
            />

            <View style={styles.modalBtns}>
              <TouchableOpacity style={styles.cancelBtn} onPress={() => setCorrecting(false)}>
                <Text style={styles.cancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.saveBtn} onPress={submitCorrection}>
                <Text style={styles.saveText}>Save</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

function Row({ label, value }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue}>{value || '–'}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container:   { flex: 1, backgroundColor: '#0d0d1a', padding: 20 },
  title:       { fontSize: 24, fontWeight: '800', color: '#e5e7eb', marginTop: 56, marginBottom: 20 },
  preview:     { borderRadius: 16, overflow: 'hidden', marginBottom: 16, backgroundColor: '#1a1a2e' },
  previewImage:{ width: '100%', height: 240 },
  placeholder: { height: 200, backgroundColor: '#1a1a2e', borderRadius: 16, justifyContent: 'center', alignItems: 'center', marginBottom: 16, borderWidth: 2, borderColor: '#2d2d4e', borderStyle: 'dashed' },
  placeholderIcon: { fontSize: 40, marginBottom: 8 },
  placeholderText: { color: '#6b7280', fontSize: 14 },
  blurWarning: { backgroundColor: '#7c2d12', padding: 10 },
  blurText:    { color: '#fdba74', fontSize: 13, textAlign: 'center' },
  btnRow:      { flexDirection: 'row', gap: 12, marginBottom: 16 },
  actionBtn:   { flex: 1, backgroundColor: '#1a1a2e', borderRadius: 12, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: '#2d2d4e' },
  actionBtnText: { color: '#e5e7eb', fontWeight: '600' },
  uploadBtn:   { backgroundColor: '#7c3aed', borderRadius: 12, padding: 16, alignItems: 'center', flexDirection: 'row', justifyContent: 'center', marginBottom: 20 },
  uploadBtnDisabled: { opacity: 0.6 },
  uploadBtnText:     { color: '#fff', fontWeight: '700', fontSize: 16 },
  resultCard:  { backgroundColor: '#1a1a2e', borderRadius: 20, padding: 20, borderWidth: 1, borderColor: '#2d2d4e' },
  resultTitle: { fontSize: 18, fontWeight: '800', color: '#10b981', marginBottom: 16 },
  row:         { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#2d2d4e' },
  rowLabel:    { color: '#9ca3af', fontSize: 14 },
  rowValue:    { color: '#e5e7eb', fontWeight: '600', fontSize: 14 },
  deductBadge: { backgroundColor: '#052e16', borderRadius: 10, padding: 10, marginTop: 12, borderWidth: 1, borderColor: '#064e3b' },
  deductBadgeText: { color: '#10b981', fontWeight: '600', textAlign: 'center' },
  stateNote:   { backgroundColor: '#0f172a', borderRadius: 10, padding: 10, marginTop: 8, borderWidth: 1, borderColor: '#1e3a5f' },
  stateNoteText: { color: '#60a5fa', fontSize: 13 },
  nudge:       { backgroundColor: '#0f2922', borderRadius: 10, padding: 10, marginTop: 8 },
  nudgeText:   { color: '#6ee7b7', fontSize: 13 },
  confidenceRow: { flexDirection: 'row', alignItems: 'center', marginTop: 12 },
  confLabel:   { color: '#6b7280', fontSize: 13 },
  confVal:     { fontSize: 13, fontWeight: '600' },
  feedbackRow: { flexDirection: 'row', gap: 10, marginTop: 16 },
  thumbBtn:    { flex: 1, backgroundColor: '#052e16', borderRadius: 10, padding: 12, alignItems: 'center' },
  thumbBtnRed: { backgroundColor: '#2d1515' },
  thumbText:   { color: '#e5e7eb', fontWeight: '600' },
  resetBtn:    { marginTop: 12, padding: 12, alignItems: 'center' },
  resetText:   { color: '#7c3aed', fontWeight: '600' },
  // Modal
  modalOverlay:{ flex: 1, backgroundColor: 'rgba(0,0,0,0.8)', justifyContent: 'flex-end' },
  modal:       { backgroundColor: '#1a1a2e', borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 24, maxHeight: '80%' },
  modalTitle:  { fontSize: 18, fontWeight: '700', color: '#e5e7eb', marginBottom: 16 },
  inputLabel:  { color: '#9ca3af', fontSize: 13, marginBottom: 6, marginTop: 4 },
  corrInput:   { backgroundColor: '#0d0d1a', borderRadius: 10, padding: 12, color: '#e5e7eb', borderWidth: 1, borderColor: '#374151', marginBottom: 8 },
  catChip:     { paddingHorizontal: 12, paddingVertical: 7, backgroundColor: '#0d0d1a', borderRadius: 20, marginRight: 8, borderWidth: 1, borderColor: '#374151' },
  catChipActive:     { borderColor: '#7c3aed', backgroundColor: '#1e1040' },
  catChipText:       { color: '#9ca3af', fontSize: 12 },
  catChipTextActive: { color: '#a78bfa' },
  modalBtns:   { flexDirection: 'row', gap: 12, marginTop: 16 },
  cancelBtn:   { flex: 1, borderRadius: 10, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: '#374151' },
  cancelText:  { color: '#9ca3af', fontWeight: '600' },
  saveBtn:     { flex: 1, backgroundColor: '#7c3aed', borderRadius: 10, padding: 14, alignItems: 'center' },
  saveText:    { color: '#fff', fontWeight: '700' },
});
