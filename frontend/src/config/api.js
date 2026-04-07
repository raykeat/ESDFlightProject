export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
export const REALTIME_WS_URL = import.meta.env.VITE_REALTIME_WS_URL || 'ws://localhost:8000/ws';

export function apiUrl(path) {
  return `${API_BASE_URL}${path}`;
}
