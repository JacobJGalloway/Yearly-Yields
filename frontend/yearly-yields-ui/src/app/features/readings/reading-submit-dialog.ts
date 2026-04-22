import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { ReadingService } from '../../core/services/reading.service';
import { GrowingArea } from '../../core/services/field.service';
import { CropCycle } from '../../core/services/crop.service';

export interface ReadingDialogData {
  fields: GrowingArea[];
  cycles: CropCycle[];
}

@Component({
  selector: 'app-reading-submit-dialog',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
  ],
  template: `
    <h2 mat-dialog-title>Submit Reading</h2>
    <mat-dialog-content>
      <form [formGroup]="form" class="dialog-form">
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
          <mat-label>Crop Cycle (optional)</mat-label>
          <mat-select formControlName="crop_cycle_id">
            <mat-option [value]="null">None</mat-option>
            @for (c of filteredCycles(); track c.id) {
              <mat-option [value]="c.id">{{ c.season_year }} — Cycle {{ c.cycle_number }}</mat-option>
            }
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Temperature (°F)</mat-label>
          <input matInput type="number" formControlName="temperature" />
          <mat-error>Required</mat-error>
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Humidity (%)</mat-label>
          <input matInput type="number" formControlName="humidity" min="0" max="100" />
          <mat-error>Required (0–100)</mat-error>
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Source</mat-label>
          <mat-select formControlName="reading_source">
            <mat-option value="manual">Manual</mat-option>
            <mat-option value="noaa">NOAA</mat-option>
            <mat-option value="fiot">fIoT</mat-option>
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Reading Date/Time</mat-label>
          <input matInput type="datetime-local" formControlName="read_at" />
          <mat-error>Required</mat-error>
        </mat-form-field>
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>Cancel</button>
      <button mat-flat-button [disabled]="form.invalid || saving" (click)="save()">
        {{ saving ? 'Submitting...' : 'Submit' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    .dialog-form { display: flex; flex-direction: column; gap: 8px; min-width: 400px; padding-top: 8px; }
    .full-width { width: 100%; }
  `],
})
export class ReadingSubmitDialogComponent {
  data: ReadingDialogData = inject(MAT_DIALOG_DATA);
  private dialogRef = inject(MatDialogRef<ReadingSubmitDialogComponent>);
  private readingService = inject(ReadingService);
  private fb = inject(FormBuilder);

  saving = false;

  form = this.fb.group({
    growing_area_id: ['', Validators.required],
    crop_cycle_id: [null as string | null],
    temperature: [null as number | null, Validators.required],
    humidity: [null as number | null, [Validators.required, Validators.min(0), Validators.max(100)]],
    reading_source: ['manual'],
    read_at: [new Date().toISOString().slice(0, 16), Validators.required],
  });

  filteredCycles(): CropCycle[] {
    const fieldId = this.form.get('growing_area_id')?.value;
    if (!fieldId) return [];
    return this.data.cycles.filter(c => c.growing_area_id === fieldId && c.status === 'active');
  }

  save(): void {
    if (this.form.invalid) return;
    this.saving = true;
    const v = this.form.getRawValue();

    this.readingService.create({
      growing_area_id: v.growing_area_id!,
      crop_cycle_id: v.crop_cycle_id ?? undefined,
      temperature: v.temperature!,
      humidity: v.humidity!,
      reading_source: v.reading_source as any,
      read_at: new Date(v.read_at!).toISOString(),
    }).subscribe({
      next: reading => this.dialogRef.close(reading),
      error: () => { this.saving = false; },
    });
  }
}
