import { DecimalPipe, TitleCasePipe } from '@angular/common';
import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { Observable } from 'rxjs';
import { Customer } from '../../core/services/customer.service';
import { Invoice, InvoiceService, InvoiceStatus } from '../../core/services/invoice.service';

export interface InvoiceDetailDialogData {
  invoice: Invoice;
  customers: Customer[];
}

const TRANSITIONS: Record<InvoiceStatus, InvoiceStatus[]> = {
  draft:  ['sent', 'voided'],
  sent:   ['paid', 'voided'],
  paid:   [],
  voided: [],
};

@Component({
  selector: 'app-invoice-detail-dialog',
  standalone: true,
  imports: [
    DecimalPipe,
    TitleCasePipe,
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
  ],
  template: `
    <h2 mat-dialog-title>Invoice</h2>
    <mat-dialog-content>
      <div class="summary">
        <span class="label">Total</span>
        <span class="value">\${{ invoice.total_amount | number:'1.2-2' }}</span>
        <span class="label">Unit Price</span>
        <span class="value">\${{ invoice.unit_price | number:'1.2-2' }} / {{ invoice.unit }}</span>
        <span class="label">Current Status</span>
        <span class="value status-{{ invoice.status }}">{{ invoice.status | titlecase }}</span>
        @if (invoice.status !== 'draft') {
          <span class="label">Customer</span>
          <span class="value">{{ customerName(invoice.customer_id) }}</span>
        }
      </div>

      <form [formGroup]="form" class="dialog-form">
        @if (invoice.status === 'draft') {
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Customer</mat-label>
            <mat-select formControlName="customer_id">
              <mat-option [value]="null">— unassigned —</mat-option>
              @for (c of customers; track c.id) {
                <mat-option [value]="c.id">{{ c.name }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
        }

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Quantity ({{ invoice.unit }})</mat-label>
          <input matInput type="number" formControlName="quantity" />
        </mat-form-field>

        @if (invoice.status === 'draft') {
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Unit Price ($ / {{ invoice.unit }})</mat-label>
            <input matInput type="number" step="0.01" formControlName="unit_price" />
          </mat-form-field>
        }

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Notes</mat-label>
          <textarea matInput formControlName="notes" rows="3"></textarea>
        </mat-form-field>

        @if (nextStatuses.length > 0) {
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Advance Status</mat-label>
            <mat-select formControlName="status">
              <mat-option [value]="null">— no change —</mat-option>
              @for (s of nextStatuses; track s) {
                <mat-option [value]="s">{{ s | titlecase }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
        }
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>Cancel</button>
      <button mat-stroked-button [disabled]="downloading" (click)="downloadPdf()">
        <mat-icon>picture_as_pdf</mat-icon>
        {{ downloading ? 'Downloading…' : 'Download PDF' }}
      </button>
      <button mat-flat-button [disabled]="saving" (click)="save()">
        {{ saving ? 'Saving…' : 'Save' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    .dialog-form { display: flex; flex-direction: column; gap: 8px; min-width: 400px; padding-top: 8px; }
    .full-width { width: 100%; }
    .summary { display: grid; grid-template-columns: auto 1fr; gap: 4px 16px; margin-bottom: 16px; align-items: baseline; }
    .label { color: var(--mat-sys-on-surface-variant); font-size: 0.8rem; }
    .value { font-weight: 500; }
    .status-draft  { color: var(--mat-sys-on-surface-variant); }
    .status-sent   { color: var(--mat-sys-tertiary, var(--yy-harvest-gold)); }
    .status-paid   { color: var(--mat-sys-primary); }
    .status-voided { color: var(--mat-sys-error); }

    /* Field green fails WCAG AA (4.10:1) as text on parchment in default theme —
       see docs/accessibility-audit-v1.3.md. Light theme's field-green-on-white
       already passes AA, so no swap needed there. */
    :host-context(.app-theme-default) .status-paid {
      color: var(--yy-field-green-accessible);
    }
  `],
})
export class InvoiceDetailDialogComponent {
  data: InvoiceDetailDialogData = inject(MAT_DIALOG_DATA);
  private dialogRef = inject(MatDialogRef<InvoiceDetailDialogComponent>);
  private invoiceService = inject(InvoiceService);
  private fb = inject(FormBuilder);

  invoice = this.data.invoice;
  customers = this.data.customers;
  nextStatuses = TRANSITIONS[this.invoice.status];
  saving = false;
  downloading = false;

  form = this.fb.group({
    customer_id: [this.invoice.customer_id ?? null as string | null],
    quantity: [this.invoice.quantity],
    unit_price: [this.invoice.unit_price ?? null as number | null],
    notes: [this.invoice.notes ?? ''],
    status: [null as InvoiceStatus | null],
  });

  customerName(id: string | null): string {
    if (!id) return '—';
    return this.customers.find(c => c.id === id)?.name ?? '—';
  }

  downloadPdf(): void {
    this.downloading = true;
    this.invoiceService.downloadPdf(this.invoice.id).subscribe({
      next: blob => {
        this.invoiceService.triggerDownload(blob, this.invoice.id);
        this.downloading = false;
      },
      error: () => { this.downloading = false; },
    });
  }

  save(): void {
    this.saving = true;
    const v = this.form.getRawValue();

    const update$ = this.invoiceService.update(this.invoice.id, {
      ...(this.invoice.status === 'draft' && v.customer_id ? { customer_id: v.customer_id } : {}),
      ...(this.invoice.status === 'draft' && v.unit_price != null ? { unit_price: v.unit_price } : {}),
      quantity: v.quantity ?? undefined,
      notes: v.notes || undefined,
    });

    const transition$: Observable<Invoice> | null = v.status
      ? v.status === 'sent'   ? this.invoiceService.send(this.invoice.id)
      : v.status === 'paid'   ? this.invoiceService.pay(this.invoice.id)
      : v.status === 'voided' ? this.invoiceService.void(this.invoice.id)
      : null
      : null;

    update$.subscribe({
      next: updated => {
        if (transition$) {
          transition$.subscribe({
            next: final => this.dialogRef.close(final),
            error: () => { this.saving = false; },
          });
        } else {
          this.dialogRef.close(updated);
        }
      },
      error: () => { this.saving = false; },
    });
  }
}
