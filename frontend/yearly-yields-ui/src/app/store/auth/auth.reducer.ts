import { createReducer, on } from '@ngrx/store';
import { AuthActions } from './auth.actions';
import { AuthState, initialAuthState } from './auth.state';

function decodeRole(token: string): string | null {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.role ?? null;
  } catch {
    return null;
  }
}

export const authReducer = createReducer<AuthState>(
  initialAuthState,
  on(AuthActions.login, state => ({ ...state, loading: true, error: null })),
  on(AuthActions.loginSuccess, (state, { accessToken, refreshToken }) => ({
    ...state,
    accessToken,
    refreshToken,
    role: decodeRole(accessToken),
    loading: false,
    error: null,
  })),
  on(AuthActions.tokenRefreshed, (state, { accessToken, refreshToken }) => ({
    ...state,
    accessToken,
    refreshToken,
    role: decodeRole(accessToken),
  })),
  on(AuthActions.loginFailure, (state, { error }) => ({
    ...state, loading: false, error,
  })),
  on(AuthActions.logout, state => ({
    ...state, accessToken: null, refreshToken: null, role: null, error: null,
  })),
);
