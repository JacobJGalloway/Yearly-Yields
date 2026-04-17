import { Component, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatTableModule } from '@angular/material/table';
import { MatTooltipModule } from '@angular/material/tooltip';
import { User, UserService } from '../../core/services/user.service';
import { UserDialogComponent } from './user-dialog';

@Component({
  selector: 'app-users',
  standalone: true,
  imports: [
    MatTableModule,
    MatButtonModule,
    MatIconModule,
    MatTooltipModule,
  ],
  template: `
    <div class="page-header">
      <h2>Users</h2>
      @if (currentUser()?.role === 'owner') {
        <button mat-flat-button (click)="openCreate()">
          <mat-icon>person_add</mat-icon> Add User
        </button>
      }
    </div>

    <table mat-table [dataSource]="users()" class="users-table mat-elevation-z1">
      <ng-container matColumnDef="full_name">
        <th mat-header-cell *matHeaderCellDef>Name</th>
        <td mat-cell *matCellDef="let u">{{ u.full_name }}</td>
      </ng-container>

      <ng-container matColumnDef="role">
        <th mat-header-cell *matHeaderCellDef>Role</th>
        <td mat-cell *matCellDef="let u">
          <span [class]="'role-' + u.role">{{ roleLabel(u.role) }}</span>
        </td>
      </ng-container>

      <ng-container matColumnDef="email">
        <th mat-header-cell *matHeaderCellDef>Email</th>
        <td mat-cell *matCellDef="let u">{{ u.email }}</td>
      </ng-container>

      <ng-container matColumnDef="phone">
        <th mat-header-cell *matHeaderCellDef>Phone</th>
        <td mat-cell *matCellDef="let u">{{ u.phone ?? '—' }}</td>
      </ng-container>

      <ng-container matColumnDef="status">
        <th mat-header-cell *matHeaderCellDef>Status</th>
        <td mat-cell *matCellDef="let u">
          <span [class]="u.is_active ? 'status-active' : 'status-inactive'">
            {{ u.is_active ? 'Active' : 'Inactive' }}
          </span>
        </td>
      </ng-container>

      <ng-container matColumnDef="actions">
        <th mat-header-cell *matHeaderCellDef></th>
        <td mat-cell *matCellDef="let u">
          @if (canEdit(u)) {
            <button mat-icon-button matTooltip="Edit" (click)="openEdit(u)">
              <mat-icon>edit</mat-icon>
            </button>
          }
        </td>
      </ng-container>

      <tr mat-header-row *matHeaderRowDef="columns"></tr>
      <tr mat-row *matRowDef="let row; columns: columns"></tr>
    </table>
  `,
  styles: [`
    .page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
    .page-header h2 { margin: 0; }
    .users-table { width: 100%; }
    .status-active { color: var(--mat-sys-primary); font-weight: 500; }
    .status-inactive { color: var(--mat-sys-error); }
    .role-owner { color: var(--mat-sys-primary); font-weight: 500; }
    .role-farmer { color: var(--mat-sys-on-surface); font-weight: 500; }
    .role-hired_hand { color: var(--mat-sys-on-surface-variant); }
  `],
})
export class UsersComponent implements OnInit {
  private userService = inject(UserService);
  private dialog = inject(MatDialog);

  users = signal<User[]>([]);
  currentUser = signal<User | null>(null);
  columns = ['full_name', 'role', 'email', 'phone', 'status', 'actions'];

  ngOnInit(): void {
    this.userService.me().subscribe(u => this.currentUser.set(u));
    this.load();
  }

  load(): void {
    this.userService.list().subscribe(users => this.users.set(users));
  }

  canEdit(user: User): boolean {
    const me = this.currentUser();
    if (!me) return false;
    if (me.role === 'owner') return true;
    return me.id === user.id;
  }

  roleLabel(role: string): string {
    return ({ owner: 'Owner', farmer: 'Farmer', hired_hand: 'Hired Hand' })[role] ?? role;
  }

  openCreate(): void {
    this.dialog.open(UserDialogComponent, {
      data: { isOwner: true },
    }).afterClosed().subscribe(result => { if (result) this.load(); });
  }

  openEdit(user: User): void {
    this.dialog.open(UserDialogComponent, {
      data: { user, isOwner: this.currentUser()?.role === 'owner' },
    }).afterClosed().subscribe(result => { if (result) this.load(); });
  }
}
