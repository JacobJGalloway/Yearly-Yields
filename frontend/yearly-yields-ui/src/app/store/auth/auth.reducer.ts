import { createReducer, on } from '@ngrx/store';
import { AuthActions } from './auth.actions';
import { AuthState, initialAuthState } from './auth.state';

export const authReducer = createReducer<AuthState>(
  initialAuthState,
  on(AuthActions.login, state => ({ ...state, loading: true, error: null })),
  on(AuthActions.loginSuccess, (state, { accessToken, refreshToken }) => ({
    ...state, accessToken, refreshToken, loading: false, error: null,
  })),
  on(AuthActions.loginFailure, (state, { error }) => ({
    ...state, loading: false, error,
  })),
  on(AuthActions.logout, state => ({
    ...state, accessToken: null, refreshToken: null, error: null,
  })),
);
