export interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  role: string | null;
  loading: boolean;
  error: string | null;
}

function decodeRole(token: string | null): string | null {
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.role ?? null;
  } catch {
    return null;
  }
}

const storedToken = localStorage.getItem('access_token');

export const initialAuthState: AuthState = {
  accessToken: storedToken,
  refreshToken: localStorage.getItem('refresh_token'),
  role: decodeRole(storedToken),
  loading: false,
  error: null,
};
