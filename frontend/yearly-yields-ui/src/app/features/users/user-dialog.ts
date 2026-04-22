import { Component, inject } from '@angular/core';
import { AbstractControl, FormBuilder, ReactiveFormsModule, ValidationErrors, ValidatorFn, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { User, UserService } from '../../core/services/user.service';

const passwordMatchValidator: ValidatorFn = (group: AbstractControl): ValidationErrors | null => {
  const pw = group.get('password')?.value;
  const confirm = group.get('confirm_password')?.value;
  return pw && confirm && pw !== confirm ? { passwordMismatch: true } : null;
};

export interface UserDialogData {
  user?: User;
  isOwner: boolean;
}

@Component({
  selector: 'app-user-dialog',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
    MatSlideToggleModule,
  ],
  template: `
    <h2 mat-dialog-title>{{ data.user ? 'Edit User' : 'Add User' }}</h2>
    <mat-dialog-content>
      <form [formGroup]="form" class="dialog-form">
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Full Name</mat-label>
          <input matInput formControlName="full_name" />
          <mat-error>Required</mat-error>
        </mat-form-field>

        @if (!data.user) {
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Email</mat-label>
            <input matInput type="email" formControlName="email" />
            <mat-error>
              @if (form.get('email')?.hasError('required')) { Required }
              @else if (form.get('email')?.hasError('email')) { Enter a valid email }
            </mat-error>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Password</mat-label>
            <input matInput type="password" formControlName="password" />
            <mat-error>Required</mat-error>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Confirm Password</mat-label>
            <input matInput type="password" formControlName="confirm_password" />
            <mat-error>
              @if (form.get('confirm_password')?.hasError('required')) { Required }
              @else if (form.hasError('passwordMismatch')) { Passwords do not match }
            </mat-error>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Role</mat-label>
            <mat-select formControlName="role">
              <mat-option value="farmer">Farmer</mat-option>
              <mat-option value="hired_hand">Hired Hand</mat-option>
            </mat-select>
          </mat-form-field>
        }

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Phone</mat-label>
          <input matInput formControlName="phone" />
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Address</mat-label>
          <input matInput formControlName="address" />
        </mat-form-field>

        @if (data.user && data.isOwner) {
          <mat-slide-toggle formControlName="is_active">Active</mat-slide-toggle>
        }
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>Cancel</button>
      <button mat-flat-button [disabled]="form.invalid || saving" (click)="save()">
        {{ saving ? 'Saving...' : 'Save' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    .dialog-form { display: flex; flex-direction: column; gap: 8px; min-width: 360px; padding-top: 8px; }
    .full-width { width: 100%; }
  `],
})
export class UserDialogComponent {
  data: UserDialogData = inject(MAT_DIALOG_DATA);
  private dialogRef = inject(MatDialogRef<UserDialogComponent>);
  private userService = inject(UserService);
  private fb = inject(FormBuilder);

  saving = false;

  form = this.fb.group({
    full_name: [this.data.user?.full_name ?? '', Validators.required],
    email: [{ value: '', disabled: !!this.data.user }, [Validators.required, Validators.email]],
    password: [{ value: '', disabled: !!this.data.user }, Validators.required],
    confirm_password: [{ value: '', disabled: !!this.data.user }, Validators.required],
    role: [{ value: 'farmer', disabled: !!this.data.user }],
    phone: [this.data.user?.phone ?? ''],
    address: [this.data.user?.address ?? ''],
    is_active: [this.data.user?.is_active ?? true],
  }, { validators: this.data.user ? [] : [passwordMatchValidator] });

  save(): void {
    if (this.form.invalid) return;
    this.saving = true;
    const v = this.form.getRawValue();

    const call = this.data.user
      ? this.userService.update(this.data.user.id, {
          full_name: v.full_name ?? undefined,
          phone: v.phone ?? undefined,
          address: v.address ?? undefined,
          is_active: v.is_active ?? undefined,
        })
      : this.userService.create({
          email: v.email!,
          password: v.password!,
          full_name: v.full_name!,
          role: v.role as any,
        });

    call.subscribe({
      next: user => this.dialogRef.close(user),
      error: () => { this.saving = false; },
    });
  }
}
