import { HttpErrorResponse, HttpEventType, HttpHandlerFn, HttpInterceptorFn, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { Store } from '@ngrx/store';
import { BehaviorSubject, EMPTY, catchError, filter, first, switchMap, take, tap, throwError } from 'rxjs';
import { AuthActions } from '../../store/auth/auth.actions';
import { selectAccessToken } from '../../store/auth/auth.selectors';
import { AuthService } from '../services/auth.service';

let isRefreshing = false;
const refreshSubject$ = new BehaviorSubject<string | null>(null);

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const store = inject(Store);
  const authService = inject(AuthService);

  return store.select(selectAccessToken).pipe(
    first(),
    switchMap(token => {
      const authed = token
        ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
        : req;
      return next(authed).pipe(
        tap(event => {
          if (event.type === HttpEventType.Response) {
            const newAccess = event.headers.get('X-New-Access-Token');
            const newRefresh = event.headers.get('X-New-Refresh-Token');
            if (newAccess && newRefresh) {
              store.dispatch(AuthActions.tokenRefreshed({ accessToken: newAccess, refreshToken: newRefresh }));
            }
          }
        }),
        catchError(err => {
          if (err instanceof HttpErrorResponse && err.status === 401 && !req.url.includes('/auth/')) {
            return handle401(req, next, store, authService);
          }
          return throwError(() => err);
        }),
      );
    }),
  );
};

function handle401(
  req: HttpRequest<unknown>,
  next: HttpHandlerFn,
  store: Store,
  authService: AuthService,
) {
  if (isRefreshing) {
    return refreshSubject$.pipe(
      filter(token => token !== null),
      take(1),
      switchMap(token =>
        next(req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })),
      ),
    );
  }

  isRefreshing = true;
  refreshSubject$.next(null);

  const storedRefresh = localStorage.getItem('refresh_token');
  if (!storedRefresh) {
    isRefreshing = false;
    store.dispatch(AuthActions.logout());
    return EMPTY;
  }

  return authService.refresh(storedRefresh).pipe(
    switchMap(res => {
      isRefreshing = false;
      store.dispatch(AuthActions.tokenRefreshed({
        accessToken: res.access_token,
        refreshToken: res.refresh_token,
      }));
      refreshSubject$.next(res.access_token);
      return next(req.clone({ setHeaders: { Authorization: `Bearer ${res.access_token}` } }));
    }),
    catchError(() => {
      isRefreshing = false;
      store.dispatch(AuthActions.logout());
      return EMPTY;
    }),
  );
}
