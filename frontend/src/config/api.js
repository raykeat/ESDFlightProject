export const API_BASE_URL = 'http://localhost:8000';
export const REALTIME_WS_URL = 'ws://localhost:5012/ws';

export function apiUrl(path) {
  return `${API_BASE_URL}${path}`;
}
