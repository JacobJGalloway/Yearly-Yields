import { createActionGroup, emptyProps, props } from '@ngrx/store';

export const AuthActions = createActionGroup({
  source: 'Auth',
  events: {
    'Login': props<{ email: string; password: string }>(),
    'Login Success': props<{ accessToken: string; refreshToken: string }>(),
    'Login Failure': props<{ error: string }>(),
    'Token Refreshed': props<{ accessToken: string; refreshToken: string }>(),
    'Logout': emptyProps(),
  },
});
