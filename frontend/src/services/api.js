/**
 * API Service - Handles all communication with the FastAPI backend.
 */

import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000, // 60 second timeout for LLM responses
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for logging
api.interceptors.request.use(
  (config) => {
    console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      console.error(`[API Error] ${error.response.status}: ${error.response.data?.detail || error.message}`);
    } else if (error.request) {
      console.error('[API Error] No response received. Backend may be offline.');
    }
    return Promise.reject(error);
  }
);

/**
 * Send a chat message to the agent.
 */
export const sendMessage = async (message, sessionId = null) => {
  const response = await api.post('/chat', {
    message,
    session_id: sessionId,
  });
  return response.data;
};

/**
 * Upload a financial document for RAG ingestion.
 */
export const uploadDocument = async (file) => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000, // 2 min for uploads
  });
  return response.data;
};

/**
 * Check backend health.
 */
export const checkHealth = async () => {
  const response = await api.get('/health');
  return response.data;
};

/**
 * Get system statistics.
 */
export const getStats = async () => {
  const response = await api.get('/stats');
  return response.data;
};

/**
 * Get compliance rules.
 */
export const getComplianceRules = async () => {
  const response = await api.get('/compliance/rules');
  return response.data;
};

export default api;