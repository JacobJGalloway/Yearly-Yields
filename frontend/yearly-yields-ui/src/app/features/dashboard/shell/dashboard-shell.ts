import { Component } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatListModule } from '@angular/material/list';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Store } from '@ngrx/store';
import { AuthActions } from '../../../store/auth/auth.actions';

interface NavItem {
  label: string;
  icon: string;
  route: string;
}

@Component({
  selector: 'app-dashboard-shell',
  standalone: true,
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    MatSidenavModule,
    MatToolbarModule,
    MatListModule,
    MatIconModule,
    MatButtonModule,
    MatTooltipModule,
  ],
  templateUrl: './dashboard-shell.html',
  styleUrl: './dashboard-shell.scss',
})
export class DashboardShellComponent {
  readonly navItems: NavItem[] = [
    { label: 'Overview',     icon: 'dashboard',      route: '/dashboard/overview' },
    { label: 'Fields',       icon: 'landscape',      route: '/dashboard/fields' },
    { label: 'Crop Cycles',  icon: 'grass',          route: '/dashboard/crops' },
    { label: 'Readings',     icon: 'sensors',        route: '/dashboard/readings' },
    { label: 'Alerts',       icon: 'notifications',  route: '/dashboard/alerts' },
    { label: 'Yield Plans',  icon: 'bar_chart',      route: '/dashboard/yield-plans' },
    { label: 'Invoices',     icon: 'receipt_long',   route: '/dashboard/invoices' },
    { label: 'Customers',    icon: 'people',         route: '/dashboard/customers' },
    { label: 'Users',        icon: 'manage_accounts', route: '/dashboard/users' },
  ];

  constructor(private store: Store, private router: Router) {}

  logout(): void {
    this.store.dispatch(AuthActions.logout());
  }
}
