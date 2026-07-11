import { Component, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatTableModule } from '@angular/material/table';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Customer, CustomerService } from '../../core/services/customer.service';
import { CustomerDialogComponent } from './customer-dialog';

@Component({
  selector: 'app-customers',
  standalone: true,
  imports: [
    MatTableModule,
    MatButtonModule,
    MatIconModule,
    MatTooltipModule,
  ],
  template: `
    <div class="page-header">
      <h2>Customers</h2>
      <button mat-flat-button (click)="openDialog()">
        <mat-icon>add</mat-icon> Add Customer
      </button>
    </div>

    <table mat-table [dataSource]="customers()" class="customers-table mat-elevation-z1">
      <ng-container matColumnDef="name">
        <th mat-header-cell *matHeaderCellDef>Name</th>
        <td mat-cell *matCellDef="let c">{{ c.name }}</td>
      </ng-container>

      <ng-container matColumnDef="email">
        <th mat-header-cell *matHeaderCellDef>Email</th>
        <td mat-cell *matCellDef="let c">{{ c.email }}</td>
      </ng-container>

      <ng-container matColumnDef="phone">
        <th mat-header-cell *matHeaderCellDef>Phone</th>
        <td mat-cell *matCellDef="let c">{{ c.phone ?? '—' }}</td>
      </ng-container>

      <ng-container matColumnDef="status">
        <th mat-header-cell *matHeaderCellDef>Status</th>
        <td mat-cell *matCellDef="let c">
          <span [class]="c.is_active ? 'status-active' : 'status-inactive'">
            {{ c.is_active ? 'Active' : 'Inactive' }}
          </span>
        </td>
      </ng-container>

      <ng-container matColumnDef="actions">
        <th mat-header-cell *matHeaderCellDef></th>
        <td mat-cell *matCellDef="let c">
          <button mat-icon-button matTooltip="Edit" aria-label="Edit customer" (click)="openDialog(c)">
            <mat-icon>edit</mat-icon>
          </button>
          <button mat-icon-button
            [matTooltip]="c.is_active ? 'Deactivate' : 'Reactivate'"
            [attr.aria-label]="c.is_active ? 'Deactivate customer' : 'Reactivate customer'"
            (click)="toggleActive(c)">
            <mat-icon>{{ c.is_active ? 'person_off' : 'person' }}</mat-icon>
          </button>
        </td>
      </ng-container>

      <tr mat-header-row *matHeaderRowDef="columns"></tr>
      <tr mat-row *matRowDef="let row; columns: columns"></tr>
    </table>

    @if (customers().length === 0) {
      <p class="empty-state">No customers yet.</p>
    }
  `,
  styles: [`
    .page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1em; }
    .page-header h2 { margin: 0; }
    .customers-table { width: 100%; }
    .status-active { color: var(--mat-sys-primary); font-weight: 500; }
    .status-inactive { color: var(--mat-sys-on-surface-variant); }
    .empty-state { color: var(--mat-sys-on-surface-variant); margin-top: 2em; text-align: center; }

    /* Field green fails WCAG AA (4.10:1) as text on parchment in default theme —
       see docs/accessibility-audit-v1.3.md. Light theme's field-green-on-white
       already passes AA, so no swap needed there. */
    :host-context(.app-theme-default) .status-active {
      color: var(--yy-field-green-accessible);
    }
  `],
})
export class CustomersComponent implements OnInit {
  private customerService = inject(CustomerService);
  private dialog = inject(MatDialog);

  customers = signal<Customer[]>([]);
  columns = ['name', 'email', 'phone', 'status', 'actions'];

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.customerService.list().subscribe(c => this.customers.set(c));
  }

  toggleActive(customer: Customer): void {
    this.customerService.update(customer.id, { is_active: !customer.is_active }).subscribe(() => this.load());
  }

  openDialog(customer?: Customer): void {
    const ref = this.dialog.open(CustomerDialogComponent, {
      data: { customer },
    });
    ref.afterClosed().subscribe(result => {
      if (result) this.load();
    });
  }
}
