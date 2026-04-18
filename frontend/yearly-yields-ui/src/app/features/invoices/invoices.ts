import { DatePipe, DecimalPipe, TitleCasePipe } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatTableModule } from '@angular/material/table';
import { MatTooltipModule } from '@angular/material/tooltip';
import { CropCycle, CropService } from '../../core/services/crop.service';
import { Customer, CustomerService } from '../../core/services/customer.service';
import { Invoice, InvoiceService } from '../../core/services/invoice.service';
import { InvoiceDetailDialogComponent } from './invoice-detail-dialog';

@Component({
  selector: 'app-invoices',
  standalone: true,
  imports: [
    DatePipe,
    DecimalPipe,
    TitleCasePipe,
    MatTableModule,
    MatButtonModule,
    MatIconModule,
    MatTooltipModule,
  ],
  template: `
    <div class="page-header">
      <h2>Invoices</h2>
    </div>

    <table mat-table [dataSource]="invoices()" class="invoices-table mat-elevation-z1">
      <ng-container matColumnDef="customer">
        <th mat-header-cell *matHeaderCellDef>Customer</th>
        <td mat-cell *matCellDef="let i">{{ customerName(i.customer_id) }}</td>
      </ng-container>

      <ng-container matColumnDef="cycle">
        <th mat-header-cell *matHeaderCellDef>Cycle</th>
        <td mat-cell *matCellDef="let i">{{ cycleLabel(i.crop_cycle_id) }}</td>
      </ng-container>

      <ng-container matColumnDef="quantity">
        <th mat-header-cell *matHeaderCellDef>Quantity</th>
        <td mat-cell *matCellDef="let i">{{ i.quantity | number }} {{ i.unit }}</td>
      </ng-container>

      <ng-container matColumnDef="unit_price">
        <th mat-header-cell *matHeaderCellDef>Unit Price</th>
        <td mat-cell *matCellDef="let i">\${{ i.unit_price | number:'1.2-2' }}</td>
      </ng-container>

      <ng-container matColumnDef="total">
        <th mat-header-cell *matHeaderCellDef>Total</th>
        <td mat-cell *matCellDef="let i">\${{ i.total_amount | number:'1.2-2' }}</td>
      </ng-container>

      <ng-container matColumnDef="status">
        <th mat-header-cell *matHeaderCellDef>Status</th>
        <td mat-cell *matCellDef="let i">
          <span [class]="'status-' + i.status">{{ i.status | titlecase }}</span>
        </td>
      </ng-container>

      <ng-container matColumnDef="invoice_date">
        <th mat-header-cell *matHeaderCellDef>Date</th>
        <td mat-cell *matCellDef="let i">{{ i.invoice_date | date:'mediumDate' }}</td>
      </ng-container>

      <ng-container matColumnDef="actions">
        <th mat-header-cell *matHeaderCellDef></th>
        <td mat-cell *matCellDef="let i">
          @if (i.status !== 'paid' && i.status !== 'voided') {
            <button mat-icon-button matTooltip="Review / Advance" (click)="openDetail(i)">
              <mat-icon>receipt_long</mat-icon>
            </button>
          }
        </td>
      </ng-container>

      <tr mat-header-row *matHeaderRowDef="columns"></tr>
      <tr mat-row *matRowDef="let row; columns: columns"></tr>
    </table>

    @if (invoices().length === 0) {
      <p class="empty-state">No invoices yet. Invoices are created automatically when a crop cycle is marked harvested.</p>
    }
  `,
  styles: [`
    .page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1em; }
    .page-header h2 { margin: 0; }
    .invoices-table { width: 100%; }
    .status-draft  { color: var(--mat-sys-on-surface-variant); font-weight: 500; }
    .status-sent   { color: var(--mat-sys-tertiary, #c9a227); font-weight: 500; }
    .status-paid   { color: var(--mat-sys-primary); font-weight: 500; }
    .status-voided { color: var(--mat-sys-error); font-weight: 500; }
    .empty-state { color: var(--mat-sys-on-surface-variant); margin-top: 2em; text-align: center; }
  `],
})
export class InvoicesComponent implements OnInit {
  private invoiceService = inject(InvoiceService);
  private customerService = inject(CustomerService);
  private cropService = inject(CropService);
  private dialog = inject(MatDialog);

  invoices = signal<Invoice[]>([]);
  customers = signal<Customer[]>([]);
  cycles = signal<CropCycle[]>([]);

  columns = ['customer', 'cycle', 'quantity', 'unit_price', 'total', 'status', 'invoice_date', 'actions'];

  ngOnInit(): void {
    this.customerService.list().subscribe(c => this.customers.set(c));
    this.cropService.listCycles().subscribe(c => this.cycles.set(c));
    this.load();
  }

  load(): void {
    this.invoiceService.list().subscribe(i => this.invoices.set(i));
  }

  customerName(id: string): string {
    return this.customers().find(c => c.id === id)?.name ?? '—';
  }

  cycleLabel(id: string): string {
    const c = this.cycles().find(c => c.id === id);
    return c ? `${c.season_year} — Cycle ${c.cycle_number}` : '—';
  }

  openDetail(invoice: Invoice): void {
    const ref = this.dialog.open(InvoiceDetailDialogComponent, {
      data: { invoice },
    });
    ref.afterClosed().subscribe(updated => {
      if (updated) this.load();
    });
  }
}
