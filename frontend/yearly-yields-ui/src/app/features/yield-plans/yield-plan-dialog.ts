import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { CropCycle } from '../../core/services/crop.service';
import { YieldPlanService } from '../../core/services/yield-plan.service';

export interface YieldPlanDialogData {
  cycles: CropCycle[];
}

@Component({
  selector: 'app-yield-plan-dialog',
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
    <h2 mat-dialog-title>New Yield Plan</h2>
    <mat-dialog-content>
      <p class="dialog-hint">Enter a target yield and select a crop cycle. The v1.2 guided wizard will replace this form.</p>
      <form [formGroup]="form" class="dialog-form">
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Crop Cycle</mat-label>
          <mat-select formControlName="crop_cycle_id">
            @for (c of data.cycles; track c.id) {
              <mat-option [value]="c.id">{{ c.season_year }} — Cycle {{ c.cycle_number }}</mat-option>
            }
          </mat-select>
          <mat-error>Required</mat-error>
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Target Yield</mat-label>
          <input matInput type="number" formControlName="target_yield" />
          <mat-error>Required</mat-error>
        </mat-form-field>
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>Cancel</button>
      <button mat-flat-button [disabled]="form.invalid || generating" (click)="generate()">
        {{ generating ? 'Generating...' : 'Generate' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    .dialog-form { display: flex; flex-direction: column; gap: 8px; min-width: 400px; padding-top: 8px; }
    .full-width { width: 100%; }
    .dialog-hint { color: var(--mat-sys-on-surface-variant); font-size: 0.875rem; margin: 0 0 8px; }
  `],
})
export class YieldPlanDialogComponent {
  data: YieldPlanDialogData = inject(MAT_DIALOG_DATA);
  private dialogRef = inject(MatDialogRef<YieldPlanDialogComponent>);
  private yieldPlanService = inject(YieldPlanService);
  private fb = inject(FormBuilder);

  generating = false;

  form = this.fb.group({
    crop_cycle_id: ['', Validators.required],
    target_yield: [null as number | null, Validators.required],
  });

  generate(): void {
    if (this.form.invalid) return;
    this.generating = true;
    const v = this.form.getRawValue();

    this.yieldPlanService.create({
      crop_cycle_id: v.crop_cycle_id!,
      target_yield: v.target_yield!,
    }).subscribe({
      next: plan => this.dialogRef.close(plan),
      error: () => { this.generating = false; },
    });
  }
}
