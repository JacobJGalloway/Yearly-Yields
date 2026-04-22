import { TitleCasePipe } from '@angular/common';
import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { Crop, CropCycle, CropCycleStatus, CropService, YieldUnit } from '../../core/services/crop.service';
import { GrowingArea } from '../../core/services/field.service';

export interface CropCycleDialogData {
  cycle?: CropCycle;
  fields: GrowingArea[];
  crops: Crop[];
}

@Component({
  selector: 'app-crop-cycle-dialog',
  standalone: true,
  imports: [
    TitleCasePipe,
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
  ],
  template: `
    <h2 mat-dialog-title>{{ data.cycle ? 'Update Cycle' : 'Start Crop Cycle' }}</h2>
    <mat-dialog-content>
      <form [formGroup]="form" class="dialog-form">
        @if (!data.cycle) {
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Field</mat-label>
            <mat-select formControlName="growing_area_id">
              @for (f of data.fields; track f.id) {
                <mat-option [value]="f.id">{{ f.name }}</mat-option>
              }
            </mat-select>
            <mat-error>Required</mat-error>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Crop</mat-label>
            <mat-select formControlName="crop_id">
              @for (c of availableCrops(); track c.id) {
                <mat-option [value]="c.id">{{ c.name | titlecase }}</mat-option>
              }
            </mat-select>
            <mat-error>Required</mat-error>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Season Year</mat-label>
            <input matInput type="number" formControlName="season_year" />
            <mat-error>Required</mat-error>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Cycle Number</mat-label>
            <input matInput type="number" formControlName="cycle_number" />
            <mat-error>Required</mat-error>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Planted Date</mat-label>
            <input matInput type="date" formControlName="planted_at" />
            <mat-error>Required</mat-error>
          </mat-form-field>

          @if (selectedCropName() === 'tomatoes') {
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Forecasted End Date</mat-label>
              <input matInput type="date" formControlName="forecasted_end_date" />
              <mat-hint>First frost date or planned greenhouse shutdown</mat-hint>
            </mat-form-field>
          }

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Yield Unit</mat-label>
            <mat-select formControlName="yield_unit">
              <mat-option value="bushels">Bushels</mat-option>
              <mat-option value="pounds">Pounds</mat-option>
              <mat-option value="tons">Tons</mat-option>
              <mat-option value="units">Units</mat-option>
            </mat-select>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Target Yield (optional)</mat-label>
            <input matInput type="number" formControlName="target_yield" />
          </mat-form-field>
        }

        @if (data.cycle) {
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Status</mat-label>
            <mat-select formControlName="status">
              @for (s of validNextStatuses(); track s) {
                <mat-option [value]="s">{{ statusLabel(s) }}</mat-option>
              }
            </mat-select>
          </mat-form-field>

          @if (form.get('status')?.value === 'harvested') {
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Harvest Date</mat-label>
              <input matInput type="date" formControlName="harvested_at" />
            </mat-form-field>

            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Actual Yield</mat-label>
              <input matInput type="number" formControlName="actual_yield" />
            </mat-form-field>
          }

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Target Yield</mat-label>
            <input matInput type="number" formControlName="target_yield" />
          </mat-form-field>

          @if (isTomatoCycle()) {
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Forecasted End Date</mat-label>
              <input matInput type="date" formControlName="forecasted_end_date" />
              <mat-hint>First frost date or planned greenhouse shutdown</mat-hint>
            </mat-form-field>
          }
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
    .dialog-form { display: flex; flex-direction: column; gap: 8px; min-width: 400px; padding-top: 8px; }
    .full-width { width: 100%; }
  `],
})
export class CropCycleDialogComponent {
  data: CropCycleDialogData = inject(MAT_DIALOG_DATA);
  private dialogRef = inject(MatDialogRef<CropCycleDialogComponent>);
  private cropService = inject(CropService);
  private fb = inject(FormBuilder);

  saving = false;

  form = this.fb.group({
    growing_area_id: [{ value: '', disabled: !!this.data.cycle }, Validators.required],
    crop_id: [{ value: '', disabled: !!this.data.cycle }, Validators.required],
    season_year: [{ value: new Date().getFullYear(), disabled: !!this.data.cycle }, Validators.required],
    cycle_number: [{ value: 1, disabled: !!this.data.cycle }, Validators.required],
    planted_at: [{ value: '', disabled: !!this.data.cycle }, Validators.required],
    yield_unit: [{ value: 'bushels' as YieldUnit, disabled: !!this.data.cycle }],
    target_yield: [this.data.cycle?.target_yield ?? null as number | null],
    status: [this.data.cycle?.status ?? null as CropCycleStatus | null],
    harvested_at: [null as string | null],
    actual_yield: [null as number | null],
    forecasted_end_date: [this.data.cycle?.forecasted_end_date ?? null as string | null],
  });

  selectedCropName(): string {
    const cropId = this.form.get('crop_id')?.value;
    return this.data.crops.find(c => c.id === cropId)?.name ?? '';
  }

  isTomatoCycle(): boolean {
    if (!this.data.cycle) return false;
    return this.data.crops.find(c => c.id === this.data.cycle?.crop_id)?.name === 'tomatoes';
  }

  availableCrops(): Crop[] {
    const fieldId = this.form.get('growing_area_id')?.value;
    const field = this.data.fields.find(f => f.id === fieldId);
    if (!field) return this.data.crops;
    const isGreenhouse = field.area_type === 'dwc_greenhouse';
    return this.data.crops.filter(c => isGreenhouse ? c.greenhouse_compatible : !c.greenhouse_compatible);
  }

  validNextStatuses(): CropCycleStatus[] {
    const current = this.data.cycle?.status;
    const map: Record<string, CropCycleStatus[]> = {
      active: ['harvested', 'abandoned'],
      fallow: ['active'],
    };
    return map[current ?? ''] ?? [];
  }

  statusLabel(s: string): string {
    return ({ active: 'Active', fallow: 'Fallow', harvested: 'Harvested', transplanted: 'Transplanted', abandoned: 'Abandoned' })[s] ?? s;
  }

  save(): void {
    if (this.form.invalid) return;
    this.saving = true;
    const v = this.form.getRawValue();

    const call = this.data.cycle
      ? this.cropService.updateCycle(this.data.cycle.id, {
          status: v.status ?? undefined,
          actual_yield: v.actual_yield ?? undefined,
          harvested_at: v.harvested_at ?? undefined,
          target_yield: v.target_yield ?? undefined,
          forecasted_end_date: v.forecasted_end_date ?? undefined,
        })
      : this.cropService.createCycle({
          growing_area_id: v.growing_area_id!,
          crop_id: v.crop_id ?? undefined,
          season_year: v.season_year!,
          cycle_number: v.cycle_number!,
          planted_at: v.planted_at!,
          yield_unit: v.yield_unit!,
          target_yield: v.target_yield ?? undefined,
          forecasted_end_date: v.forecasted_end_date ?? undefined,
        });

    call.subscribe({
      next: cycle => this.dialogRef.close(cycle),
      error: () => { this.saving = false; },
    });
  }
}
