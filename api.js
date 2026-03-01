/**
 * utils/api.js — Centralized API client
 * =======================================
 * All backend calls go through here.
 * Automatically injects JWT token from AsyncStorage.
 * 
 * Usage:
 *   import api from '../utils/api';
 *   const result = await api.uploadReceipt(imageUri);
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

// Change to your Render backend URL in production
const BASE_URL = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000';

async function getHeaders(isMultipart = false) {
  const token = await AsyncStorage.getItem('auth_token');
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (!isMultipart) headers['Content-Type'] = 'application/json';
  return headers;
}

async function request(method, path, body = null, multipart = false) {
  const headers = await getHeaders(multipart);
  const opts = { method, headers };
  
  if (body) {
    opts.body = multipart ? body : JSON.stringify(body);
  }

  const res = await fetch(`${BASE_URL}${path}`, opts);
  const data = await res.json().catch(() => ({}));
  
  if (!res.ok) {
    throw new Error(data.detail || `Request failed: ${res.status}`);
  }
  return data;
}

const api = {
  // ── Auth ──────────────────────────────────────────────────────
  signup: (email, password) =>
    request('POST', '/auth/signup', { email, password }),
  
  login: (email, password) =>
    request('POST', '/auth/login', { email, password }),
  
  googleLogin: (idToken) =>
    request('POST', '/auth/google', { id_token: idToken }),
  
  getMe: () =>
    request('GET', '/auth/me'),
  
  updateProfile: (profile) =>
    request('PUT', '/auth/profile', profile),

  // ── Receipts ──────────────────────────────────────────────────
  uploadReceipt: async (imageUri) => {
    const form = new FormData();
    const filename = imageUri.split('/').pop();
    const ext = filename.split('.').pop().toLowerCase();
    const mimeType = ext === 'png' ? 'image/png' : 'image/jpeg';
    
    form.append('file', {
      uri: imageUri,
      name: filename,
      type: mimeType
    });
    return request('POST', '/receipts/upload', form, true);
  },

  listReceipts: (page = 1, month = null, category = null) => {
    let path = `/receipts?page=${page}`;
    if (month)    path += `&month=${month}`;
    if (category) path += `&category=${encodeURIComponent(category)}`;
    return request('GET', path);
  },

  getReceipt: (id) =>
    request('GET', `/receipts/${id}`),

  submitFeedback: (id, feedback, corrections = {}) =>
    request('PUT', `/receipts/${id}/feedback`, { feedback, ...corrections }),

  deleteReceipt: (id) =>
    request('DELETE', `/receipts/${id}`),

  // ── Insights ──────────────────────────────────────────────────
  getSummary: () =>
    request('GET', '/insights/summary'),
  
  getTrends: (months = 6) =>
    request('GET', `/insights/trends?months=${months}`),
  
  getDeductibles: (year) =>
    request('GET', `/insights/deductibles${year ? `?year=${year}` : ''}`),

  // ── Export ────────────────────────────────────────────────────
  exportCsvUrl: (month, year) => {
    let path = `${BASE_URL}/export/csv`;
    const params = [];
    if (month) params.push(`month=${month}`);
    if (year)  params.push(`year=${year}`);
    if (params.length) path += '?' + params.join('&');
    return path;
  },

  exportPdfUrl: (year) =>
    `${BASE_URL}/export/pdf${year ? `?year=${year}` : ''}`,

  // ── Stripe ────────────────────────────────────────────────────
  createCheckout: () =>
    request('POST', '/webhooks/create-checkout'),
};

export default api;
