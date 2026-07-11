import { DatePipe, DecimalPipe, TitleCasePipe } from '@angular/common';
import { Component, OnInit, ViewChild, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatRadioModule } from '@angular/material/radio';
import { MatStepper, MatStepperModule } from '@angular/material/stepper';
import { Crop, CropCycle, CropService } from '../../core/services/crop.service';
import { GrowingArea, GrowingAreaType } from '../../core/services/field.service';
import { YieldPlan, YieldPlanService } from '../../core/services/yield-plan.service';

export interface YieldPlanWizardData {
  areas: GrowingArea[];
}

@Component({
  selector: 'app-yield-plan-wizard',
  standalone: true,
  imports: [
    DatePipe,
    DecimalPipe,
    TitleCasePipe,
    FormsModule,
    MatDialogModule,
    MatStepperModule,
    MatButtonModule,
    MatRadioModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressSpinnerModule,
    MatIconModule,
  ],
  template: `
    <h2 mat-dialog-title>New Yield Plan</h2>
    <mat-dialog-content>
      <mat-stepper linear #stepper class="wizard-stepper">

        <!-- Step 1: Growing Area -->
        <mat-step [completed]="!!selectedArea">
          <ng-template matStepLabel>Growing Area</ng-template>
          <p class="step-question">Which field or greenhouse are we planning for?</p>
          <mat-radio-group class="radio-list" [(ngModel)]="selectedAreaId" (ngModelChange)="onAreaChange($event)">
            @for (a of data.areas; track a.id) {
              <mat-radio-button [value]="a.id" class="radio-option">
                <span class="option-name">{{ a.name }}</span>
                <span class="option-sub">
                  {{ areaTypeLabel(a.area_type) }}{{ a.nws_station_id ? ' · ' + a.nws_station_id : '' }}
                </span>
              </mat-radio-button>
            }
          </mat-radio-group>
          <div class="step-actions">
            <button mat-button mat-dialog-close>Cancel</button>
            <button mat-flat-button matStepperNext [disabled]="!selectedArea">Next</button>
          </div>
        </mat-step>

        <!-- Step 2: Crop Cycle -->
        <mat-step [completed]="!!selectedCycle">
          <ng-template matStepLabel>Crop Cycle</ng-template>
          <p class="step-question">Which active crop cycle?</p>
          @if (loadingCycles) {
            <mat-spinner diameter="32" class="inline-spinner"></mat-spinner>
          } @else if (cycles.length === 0) {
            <p class="empty-hint">No active cycles found in this area.</p>
          } @else {
            <mat-radio-group class="radio-list" [(ngModel)]="selectedCycleId" (ngModelChange)="onCycleChange($event)">
              @for (c of cycles; track c.id) {
                <mat-radio-button [value]="c.id" class="radio-option">
                  <span class="option-name">
                    {{ cropName(c.crop_id) }} — {{ c.season_year }} · Cycle {{ c.cycle_number }}
                  </span>
                  <span class="option-sub">
                    Planted {{ c.planted_at | date:'mediumDate' }} · {{ c.yield_unit }}
                  </span>
                </mat-radio-button>
              }
            </mat-radio-group>
          }
          <div class="step-actions">
            <button mat-button matStepperPrevious>Back</button>
            <button mat-flat-button matStepperNext [disabled]="!selectedCycle">Next</button>
          </div>
        </mat-step>

        <!-- Step 3: Target Yield -->
        <mat-step [completed]="targetYieldValid">
          <ng-template matStepLabel>Target Yield</ng-template>
          <p class="step-question">What's your target for this cycle?</p>
          <mat-form-field appearance="outline" class="yield-field">
            <mat-label>Target yield</mat-label>
            <input matInput type="number" min="0.01" step="any" [(ngModel)]="targetYield" />
            @if (selectedCycle) {
              <span matTextSuffix>{{ selectedCycle.yield_unit }}</span>
            }
          </mat-form-field>
          <div class="step-actions">
            <button mat-button matStepperPrevious>Back</button>
            <button mat-flat-button [disabled]="!targetYieldValid" (click)="generate()">
              <mat-icon>auto_awesome</mat-icon> Generate Plan
            </button>
          </div>
        </mat-step>

        <!-- Step 4: Result — shows spinner while agent runs, then the plan -->
        <mat-step>
          <ng-template matStepLabel>Your Plan</ng-template>
          @if (generating) {
            <div class="generating-state">
              <mat-spinner diameter="48"></mat-spinner>
              <p>Analyzing your field data…</p>
            </div>
          } @else if (error) {
            <div class="error-state">
              <mat-icon color="warn">error_outline</mat-icon>
              <p>{{ error }}</p>
              <div class="step-actions">
                <button mat-button (click)="reset()">Start Over</button>
                <button mat-flat-button (click)="generate(false)">Try Again</button>
              </div>
            </div>
          } @else if (result) {
            <div class="result-card">
              <div class="result-row">
                <span class="result-label">Confidence</span>
                <span class="confidence-{{ result.confidence_level }}">
                  {{ result.confidence_level | titlecase }}
                </span>
              </div>
              <div class="result-row">
                <span class="result-label">Recommended Plant Qty</span>
                <span>{{ result.recommended_plant_quantity | number }} {{ selectedCycle?.yield_unit }}</span>
              </div>
              <div class="result-row">
                <span class="result-label">Target Yield</span>
                <span>{{ result.target_yield | number }} {{ selectedCycle?.yield_unit }}</span>
              </div>
              <p class="reasoning">{{ result.reasoning }}</p>
            </div>
            <div class="step-actions">
              <button mat-button (click)="reset()">Start Over</button>
              <button mat-flat-button (click)="accept()">Accept Plan</button>
            </div>
          }
        </mat-step>

      </mat-stepper>
    </mat-dialog-content>
  `,
  styles: [`
    :host { display: block; }
    .wizard-stepper { background: transparent; }

    .step-question {
      margin: 12px 0 16px;
      font-size: 0.95rem;
      color: var(--mat-sys-on-surface-variant);
    }

    .radio-list { display: flex; flex-direction: column; gap: 2px; }

    .radio-option ::ng-deep .mdc-label {
      display: flex;
      flex-direction: column;
      padding: 4px 0;
      cursor: pointer;
    }

    .option-name { font-weight: 500; line-height: 1.4; }
    .option-sub {
      font-size: 0.8rem;
      color: var(--mat-sys-on-surface-variant);
      margin-top: 2px;
    }

    .step-actions {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
      margin-top: 20px;
      padding-bottom: 8px;
    }

    .yield-field { width: 100%; max-width: 280px; margin-top: 4px; }

    .generating-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 16px;
      padding: 40px 0 24px;
      color: var(--mat-sys-on-surface-variant);
    }

    .error-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
      padding: 24px 0;
      text-align: center;
    }
    .error-state mat-icon { font-size: 36px; width: 36px; height: 36px; }

    .inline-spinner { margin: 12px 0; }
    .empty-hint { color: var(--mat-sys-on-surface-variant); font-style: italic; margin: 4px 0; }

    .result-card { display: flex; flex-direction: column; margin-top: 8px; }
    .result-row {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      padding: 10px 0;
      border-bottom: 1px solid var(--mat-sys-outline-variant);
      font-size: 0.9rem;
    }
    .result-label { color: var(--mat-sys-on-surface-variant); }

    .reasoning {
      margin: 12px 0 0;
      font-size: 0.85rem;
      line-height: 1.6;
      color: var(--mat-sys-on-surface-variant);
    }

    .confidence-high   { color: var(--mat-sys-primary); font-weight: 600; }
    .confidence-medium { color: var(--yy-harvest-gold, #C9A227); font-weight: 600; }
    .confidence-low    { color: var(--mat-sys-error); font-weight: 600; }

    /* Harvest gold fails WCAG AA on parchment/white surfaces — see
       docs/accessibility-audit-v1.3.md */
    :host-context(.app-theme-default) .confidence-medium,
    :host-context(.app-theme-light) .confidence-medium {
      color: var(--yy-harvest-gold-accessible);
    }

    @media (max-width: 480px) {
      .step-actions { flex-direction: column-reverse; }
      .step-actions button { width: 100%; }
    }
  `],
})
export class YieldPlanWizardComponent implements OnInit {
  data: YieldPlanWizardData = inject(MAT_DIALOG_DATA);
  private dialogRef = inject(MatDialogRef<YieldPlanWizardComponent>);
  private cropService = inject(CropService);
  private yieldPlanService = inject(YieldPlanService);

  @ViewChild('stepper') stepper!: MatStepper;

  crops: Crop[] = [];
  cycles: CropCycle[] = [];
  loadingCycles = false;

  selectedAreaId: string | null = null;
  selectedArea: GrowingArea | null = null;
  selectedCycleId: string | null = null;
  selectedCycle: CropCycle | null = null;
  targetYield: number | null = null;

  generating = false;
  result: YieldPlan | null = null;
  error: string | null = null;

  get targetYieldValid(): boolean {
    return this.targetYield !== null && this.targetYield > 0;
  }

  ngOnInit(): void {
    this.cropService.listCrops().subscribe(crops => (this.crops = crops));
  }

  areaTypeLabel(type: GrowingAreaType): string {
    return type === 'open_field' ? 'Open Field' : 'Greenhouse';
  }

  cropName(cropId: string | null): string {
    if (!cropId) return 'Unknown crop';
    const crop = this.crops.find(c => c.id === cropId);
    return crop ? crop.name.replace(/_/g, ' ') : 'Unknown crop';
  }

  onAreaChange(areaId: string): void {
    this.selectedArea = this.data.areas.find(a => a.id === areaId) ?? null;
    this.selectedCycleId = null;
    this.selectedCycle = null;
    this.cycles = [];
    if (!areaId) return;
    this.loadingCycles = true;
    this.cropService.listCycles({ growing_area_id: areaId, status: 'active' }).subscribe({
      next: cs => { this.cycles = cs; this.loadingCycles = false; },
      error: () => { this.loadingCycles = false; },
    });
  }

  onCycleChange(cycleId: string): void {
    this.selectedCycle = this.cycles.find(c => c.id === cycleId) ?? null;
  }

  generate(navigate = true): void {
    if (!this.selectedCycle || !this.targetYieldValid) return;
    this.generating = true;
    this.error = null;
    this.result = null;
    if (navigate) this.stepper.next();
    this.yieldPlanService.create({
      crop_cycle_id: this.selectedCycle.id,
      target_yield: this.targetYield!,
    }).subscribe({
      next: plan => { this.result = plan; this.generating = false; },
      error: () => {
        this.error = 'The AI agent could not generate a plan. Please try again.';
        this.generating = false;
      },
    });
  }

  reset(): void {
    this.selectedAreaId = null;
    this.selectedArea = null;
    this.selectedCycleId = null;
    this.selectedCycle = null;
    this.targetYield = null;
    this.cycles = [];
    this.generating = false;
    this.result = null;
    this.error = null;
    this.stepper.reset();
  }

  accept(): void {
    this.dialogRef.close(this.result);
  }
}
