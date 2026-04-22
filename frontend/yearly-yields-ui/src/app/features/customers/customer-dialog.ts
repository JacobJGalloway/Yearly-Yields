import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { Customer, CustomerService } from '../../core/services/customer.service';

export interface CustomerDialogData {
  customer?: Customer;
}

@Component({
  selector: 'app-customer-dialog',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatSlideToggleModule,
  ],
  template: `
    <h2 mat-dialog-title>{{ data.customer ? 'Edit Customer' : 'Add Customer' }}</h2>
    <mat-dialog-content>
      <form [formGroup]="form" class="dialog-form">
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Name</mat-label>
          <input matInput formControlName="name" />
          <mat-error>Required</mat-error>
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Email</mat-label>
          <input matInput type="email" formControlName="email" />
          <mat-error>Valid email required</mat-error>
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Phone</mat-label>
          <input matInput formControlName="phone" />
        </mat-form-field>

        @if (data.customer) {
          <mat-slide-toggle formControlName="is_active">Active</mat-slide-toggle>
        }
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>Cancel</button>
      <button mat-flat-button [disabled]="form.invalid || saving" (click)="save()">
        {{ saving ? 'Saving…' : 'Save' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    .dialog-form { display: flex; flex-direction: column; gap: 8px; min-width: 380px; padding-top: 8px; }
    .full-width { width: 100%; }
  `],
})
export class CustomerDialogComponent {
  data: CustomerDialogData = inject(MAT_DIALOG_DATA);
  private dialogRef = inject(MatDialogRef<CustomerDialogComponent>);
  private customerService = inject(CustomerService);
  private fb = inject(FormBuilder);

  saving = false;

  form = this.fb.group({
    name: [this.data.customer?.name ?? '', Validators.required],
    email: [this.data.customer?.email ?? '', [Validators.required, Validators.email]],
    phone: [this.data.customer?.phone ?? ''],
    is_active: [this.data.customer?.is_active ?? true],
  });

  save(): void {
    if (this.form.invalid) return;
    this.saving = true;
    const v = this.form.getRawValue();

    const obs = this.data.customer
      ? this.customerService.update(this.data.customer.id, {
          name: v.name!,
          email: v.email!,
          phone: v.phone || undefined,
          is_active: v.is_active!,
        })
      : this.customerService.create({
          name: v.name!,
          email: v.email!,
          phone: v.phone || undefined,
        });

    obs.subscribe({
      next: c => this.dialogRef.close(c),
      error: () => { this.saving = false; },
    });
  }
}
