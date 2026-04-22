import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { FieldService, GrowingArea, GrowingAreaType } from '../../core/services/field.service';

export interface FieldDialogData {
  field?: GrowingArea;
}

@Component({
  selector: 'app-field-dialog',
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
    <h2 mat-dialog-title>{{ data.field ? 'Edit Field' : 'Add Field' }}</h2>
    <mat-dialog-content>
      <form [formGroup]="form" class="dialog-form">
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Name</mat-label>
          <input matInput formControlName="name" />
          <mat-error>Required</mat-error>
        </mat-form-field>

        @if (!data.field) {
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Type</mat-label>
            <mat-select formControlName="area_type" (selectionChange)="onTypeChange()">
              <mat-option value="open_field">Open Field</mat-option>
              <mat-option value="dwc_greenhouse">DWC Greenhouse</mat-option>
            </mat-select>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Latitude</mat-label>
            <input matInput type="number" formControlName="latitude" />
            <mat-error>Required</mat-error>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Longitude</mat-label>
            <input matInput type="number" formControlName="longitude" />
            <mat-error>Required</mat-error>
          </mat-form-field>

          @if (form.get('area_type')?.value === 'open_field') {
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Area (acres)</mat-label>
              <input matInput type="number" formControlName="area_acres" />
              <mat-error>Required for open fields</mat-error>
            </mat-form-field>
          }

          @if (form.get('area_type')?.value === 'dwc_greenhouse') {
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Area (sq ft)</mat-label>
              <input matInput type="number" formControlName="area_sqft" />
              <mat-error>Required for greenhouses</mat-error>
            </mat-form-field>
          }
        }

        @if (data.field) {
          @if (data.field.area_acres !== null) {
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Area (acres)</mat-label>
              <input matInput type="number" formControlName="area_acres" />
            </mat-form-field>
          }
          @if (data.field.area_sqft !== null) {
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Area (sq ft)</mat-label>
              <input matInput type="number" formControlName="area_sqft" />
            </mat-form-field>
          }
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
export class FieldDialogComponent {
  data: FieldDialogData = inject(MAT_DIALOG_DATA);
  private dialogRef = inject(MatDialogRef<FieldDialogComponent>);
  private fieldService = inject(FieldService);
  private fb = inject(FormBuilder);

  saving = false;

  form = this.fb.group({
    name: [this.data.field?.name ?? '', Validators.required],
    area_type: [{ value: 'open_field' as GrowingAreaType, disabled: !!this.data.field }],
    latitude: [{ value: null as number | null, disabled: !!this.data.field }, Validators.required],
    longitude: [{ value: null as number | null, disabled: !!this.data.field }, Validators.required],
    area_acres: [this.data.field?.area_acres ?? null as number | null],
    area_sqft: [this.data.field?.area_sqft ?? null as number | null],
    is_active: [this.data.field?.is_active ?? true],
  });

  onTypeChange(): void {
    this.form.patchValue({ area_acres: null, area_sqft: null });
  }

  save(): void {
    if (this.form.invalid) return;
    this.saving = true;
    const v = this.form.getRawValue();

    const call = this.data.field
      ? this.fieldService.update(this.data.field.id, {
          name: v.name ?? undefined,
          area_acres: v.area_acres ?? undefined,
          area_sqft: v.area_sqft ?? undefined,
          is_active: v.is_active ?? undefined,
        })
      : this.fieldService.create({
          name: v.name!,
          area_type: v.area_type!,
          latitude: v.latitude!,
          longitude: v.longitude!,
          area_acres: v.area_acres ?? undefined,
          area_sqft: v.area_sqft ?? undefined,
        });

    call.subscribe({
      next: field => this.dialogRef.close(field),
      error: () => { this.saving = false; },
    });
  }
}
