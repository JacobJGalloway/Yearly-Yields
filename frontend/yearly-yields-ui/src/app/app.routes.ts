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
    path: 'forgot-password',
    loadComponent: () =>
      import('./features/auth/forgot-password/forgot-password').then(m => m.ForgotPasswordComponent),
  },
  {
    path: 'reset-password',
    loadComponent: () =>
      import('./features/auth/reset-password/reset-password').then(m => m.ResetPasswordComponent),
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
      {
        path: 'readings',
        loadComponent: () =>
          import('./features/readings/readings').then(m => m.ReadingsComponent),
      },
      {
        path: 'alerts',
        loadComponent: () =>
          import('./features/alerts/alerts').then(m => m.AlertsComponent),
      },
      {
        path: 'yield-plans',
        loadComponent: () =>
          import('./features/yield-plans/yield-plans').then(m => m.YieldPlansComponent),
      },
      {
        path: 'invoices',
        loadComponent: () =>
          import('./features/invoices/invoices').then(m => m.InvoicesComponent),
      },
      {
        path: 'customers',
        loadComponent: () =>
          import('./features/customers/customers').then(m => m.CustomersComponent),
      },
    ],
  },
  { path: '**', redirectTo: 'dashboard' },
];
