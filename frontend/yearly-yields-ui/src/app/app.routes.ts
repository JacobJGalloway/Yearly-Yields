import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
  {
    path: 'login',
    loadComponent: () =>
      import('./features/auth/login/login').then(m => m.LoginComponent),
  },
  {
    path: 'dashboard',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/dashboard/shell/dashboard-shell').then(m => m.DashboardShellComponent),
    children: [
      { path: '', redirectTo: 'overview', pathMatch: 'full' },
      {
        path: 'overview',
        loadComponent: () =>
          import('./features/dashboard/shell/overview').then(m => m.OverviewComponent),
      },
      {
        path: 'users',
        loadComponent: () =>
          import('./features/users/users').then(m => m.UsersComponent),
      },
      {
        path: 'fields',
        loadComponent: () =>
          import('./features/fields/fields').then(m => m.FieldsComponent),
      },
      {
        path: 'crops',
        loadComponent: () =>
          import('./features/crop-cycles/crop-cycles').then(m => m.CropCyclesComponent),
      },
    ],
  },
  { path: '**', redirectTo: 'dashboard' },
];
