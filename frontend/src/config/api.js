export const API_BASE_URL = 'http://localhost:8000';

export function apiUrl(path) {
  return `${API_BASE_URL}${path}`;
}
