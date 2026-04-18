import { Component, OnInit, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatListModule } from '@angular/material/list';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Store } from '@ngrx/store';
import { AuthActions } from '../../../store/auth/auth.actions';
import { ThemeService, AppTheme } from '../../../core/services/theme.service';
import { ThemeDialogComponent } from './theme-dialog';

interface NavItem {
  label: string;
  icon: string;
  route: string;
}

const LOGO_MAP: Record<AppTheme, string> = {
  default: 'brand/Logo Work Name One Line Default Mode.svg',
  light:   'brand/Logo Work Name One Line Light Mode.svg',
  dark:    'brand/Logo Work Name One Line Dark Mode.svg',
};

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
export class DashboardShellComponent implements OnInit {
  private store = inject(Store);
  private dialog = inject(MatDialog);
  readonly themeService = inject(ThemeService);

  readonly navItems: NavItem[] = [
    { label: 'Overview',     icon: 'dashboard',       route: '/dashboard/overview'     },
    { label: 'Fields',       icon: 'landscape',       route: '/dashboard/fields'       },
    { label: 'Crop Cycles',  icon: 'grass',           route: '/dashboard/crops'        },
    { label: 'Readings',     icon: 'sensors',         route: '/dashboard/readings'     },
    { label: 'Alerts',       icon: 'notifications',   route: '/dashboard/alerts'       },
    { label: 'Yield Plans',  icon: 'bar_chart',       route: '/dashboard/yield-plans'  },
    { label: 'Invoices',     icon: 'receipt_long',    route: '/dashboard/invoices'     },
    { label: 'Customers',    icon: 'people',          route: '/dashboard/customers'    },
    { label: 'Users',        icon: 'manage_accounts', route: '/dashboard/users'        },
  ];

  get logoSrc(): string {
    return LOGO_MAP[this.themeService.theme()];
  }

  ngOnInit(): void {
    this.themeService.init();
  }

  openThemePicker(): void {
    this.dialog.open(ThemeDialogComponent, {
      data: { current: this.themeService.theme() },
    }).afterClosed().subscribe(theme => {
      if (theme) this.themeService.setTheme(theme);
    });
  }

  logout(): void {
    this.store.dispatch(AuthActions.logout());
  }
}
