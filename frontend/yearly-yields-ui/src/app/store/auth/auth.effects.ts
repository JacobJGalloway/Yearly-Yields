import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { Actions, createEffect, ofType } from '@ngrx/effects';
import { catchError, map, of, switchMap, tap } from 'rxjs';
import { AuthService } from '../../core/services/auth.service';
import { AuthActions } from './auth.actions';

export const loginEffect = createEffect(
  (actions$ = inject(Actions), authService = inject(AuthService)) =>
    actions$.pipe(
      ofType(AuthActions.login),
      switchMap(({ email, password }) =>
        authService.login(email, password).pipe(
          map(res => AuthActions.loginSuccess({
            accessToken: res.access_token,
            refreshToken: res.refresh_token,
          })),
          catchError(err => of(AuthActions.loginFailure({
            error: err.error?.detail ?? 'Login failed. Please check your credentials.',
          }))),
        ),
      ),
    ),
  { functional: true },
);

export const loginSuccessEffect = createEffect(
  (actions$ = inject(Actions), router = inject(Router)) =>
    actions$.pipe(
      ofType(AuthActions.loginSuccess),
      tap(({ accessToken, refreshToken }) => {
        localStorage.setItem('access_token', accessToken);
        localStorage.setItem('refresh_token', refreshToken);
        router.navigate(['/dashboard']);
      }),
    ),
  { functional: true, dispatch: false },
);

export const tokenRefreshedEffect = createEffect(
  (actions$ = inject(Actions)) =>
    actions$.pipe(
      ofType(AuthActions.tokenRefreshed),
      tap(({ accessToken, refreshToken }) => {
        localStorage.setItem('access_token', accessToken);
        localStorage.setItem('refresh_token', refreshToken);
      }),
    ),
  { functional: true, dispatch: false },
);

export const logoutEffect = createEffect(
  (actions$ = inject(Actions), router = inject(Router)) =>
    actions$.pipe(
      ofType(AuthActions.logout),
      tap(() => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        router.navigate(['/login']);
      }),
    ),
  { functional: true, dispatch: false },
);
