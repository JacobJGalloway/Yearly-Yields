import { DecimalPipe, TitleCasePipe } from '@angular/common';
import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { Invoice, InvoiceService, InvoiceStatus } from '../../core/services/invoice.service';

export interface InvoiceDetailDialogData {
  invoice: Invoice;
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
      </div>

      <form [formGroup]="form" class="dialog-form">
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Quantity ({{ invoice.unit }})</mat-label>
          <input matInput type="number" formControlName="quantity" />
        </mat-form-field>

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
    .status-sent   { color: var(--mat-sys-tertiary, #c9a227); }
    .status-paid   { color: var(--mat-sys-primary); }
    .status-voided { color: var(--mat-sys-error); }
  `],
})
export class InvoiceDetailDialogComponent {
  data: InvoiceDetailDialogData = inject(MAT_DIALOG_DATA);
  private dialogRef = inject(MatDialogRef<InvoiceDetailDialogComponent>);
  private invoiceService = inject(InvoiceService);
  private fb = inject(FormBuilder);

  invoice = this.data.invoice;
  nextStatuses = TRANSITIONS[this.invoice.status];
  saving = false;

  form = this.fb.group({
    quantity: [this.invoice.quantity],
    notes: [this.invoice.notes ?? ''],
    status: [null as InvoiceStatus | null],
  });

  save(): void {
    this.saving = true;
    const v = this.form.getRawValue();

    this.invoiceService.update(this.invoice.id, {
      quantity: v.quantity ?? undefined,
      notes: v.notes || undefined,
      status: v.status ?? undefined,
    }).subscribe({
      next: updated => this.dialogRef.close(updated),
      error: () => { this.saving = false; },
    });
  }
}
