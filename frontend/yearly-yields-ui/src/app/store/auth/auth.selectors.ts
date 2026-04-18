import { createFeatureSelector, createSelector } from '@ngrx/store';
import { AuthState } from './auth.state';

const selectAuthState = createFeatureSelector<AuthState>('auth');

export const selectIsAuthenticated = createSelector(
  selectAuthState,
  state => !!state.accessToken,
);

export const selectAuthLoading = createSelector(
  selectAuthState,
  state => state.loading,
);

export const selectAuthError = createSelector(
  selectAuthState,
  state => state.error,
);

export const selectAccessToken = createSelector(
  selectAuthState,
  state => state.accessToken,
);

export const selectRefreshToken = createSelector(
  selectAuthState,
  state => state.refreshToken,
);
