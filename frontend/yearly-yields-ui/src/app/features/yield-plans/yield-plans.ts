import { DatePipe, DecimalPipe, TitleCasePipe } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatTableModule } from '@angular/material/table';
import { MatTooltipModule } from '@angular/material/tooltip';
import { CropCycle, CropService } from '../../core/services/crop.service';
import { FieldService, GrowingArea } from '../../core/services/field.service';
import { YieldPlan, YieldPlanService } from '../../core/services/yield-plan.service';
import { YieldPlanWizardComponent } from './yield-plan-wizard';

@Component({
  selector: 'app-yield-plans',
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
      <h2>Yield Plans</h2>
      <button mat-flat-button (click)="openGenerate()">
        <mat-icon>auto_awesome</mat-icon> Generate Plan
      </button>
    </div>

    <table mat-table [dataSource]="plans()" class="plans-table mat-elevation-z1">
      <ng-container matColumnDef="field">
        <th mat-header-cell *matHeaderCellDef>Field</th>
        <td mat-cell *matCellDef="let p">{{ fieldName(p.growing_area_id) }}</td>
      </ng-container>

      <ng-container matColumnDef="cycle">
        <th mat-header-cell *matHeaderCellDef>Cycle</th>
        <td mat-cell *matCellDef="let p">{{ cycleLabel(p.crop_cycle_id) }}</td>
      </ng-container>

      <ng-container matColumnDef="confidence">
        <th mat-header-cell *matHeaderCellDef>Confidence</th>
        <td mat-cell *matCellDef="let p">
          <span [class]="'confidence-' + p.confidence_level">{{ p.confidence_level | titlecase }}</span>
        </td>
      </ng-container>

      <ng-container matColumnDef="recommended_qty">
        <th mat-header-cell *matHeaderCellDef>Rec. Plant Qty</th>
        <td mat-cell *matCellDef="let p">{{ p.recommended_plant_quantity | number }}</td>
      </ng-container>

      <ng-container matColumnDef="target_yield">
        <th mat-header-cell *matHeaderCellDef>Target Yield</th>
        <td mat-cell *matCellDef="let p">{{ p.target_yield | number }}</td>
      </ng-container>

      <ng-container matColumnDef="reasoning">
        <th mat-header-cell *matHeaderCellDef>Reasoning</th>
        <td mat-cell *matCellDef="let p" class="reasoning-cell" [matTooltip]="p.reasoning">
          {{ p.reasoning.length > 80 ? p.reasoning.slice(0, 80) + '…' : p.reasoning }}
        </td>
      </ng-container>

      <ng-container matColumnDef="created_at">
        <th mat-header-cell *matHeaderCellDef>Generated</th>
        <td mat-cell *matCellDef="let p">{{ p.created_at | date:'short' }}</td>
      </ng-container>

      <tr mat-header-row *matHeaderRowDef="columns"></tr>
      <tr mat-row *matRowDef="let row; columns: columns"></tr>
    </table>

    @if (plans().length === 0) {
      <p class="empty-state">No yield plans yet. Click Generate Plan to get started.</p>
    }
  `,
  styles: [`
    .page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1em; }
    .page-header h2 { margin: 0; }
    .plans-table { width: 100%; }
    .reasoning-cell { max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .confidence-high { color: var(--mat-sys-primary); font-weight: 500; }
    .confidence-medium { color: var(--mat-sys-tertiary, var(--yy-harvest-gold)); font-weight: 500; }
    .confidence-low { color: var(--mat-sys-error); font-weight: 500; }
    .empty-state { color: var(--mat-sys-on-surface-variant); margin-top: 2em; text-align: center; }
  `],
})
export class YieldPlansComponent implements OnInit {
  private yieldPlanService = inject(YieldPlanService);
  private cropService = inject(CropService);
  private fieldService = inject(FieldService);
  private dialog = inject(MatDialog);

  plans = signal<YieldPlan[]>([]);
  cycles = signal<CropCycle[]>([]);
  fields = signal<GrowingArea[]>([]);

  columns = ['field', 'cycle', 'confidence', 'recommended_qty', 'target_yield', 'reasoning', 'created_at'];

  ngOnInit(): void {
    this.fieldService.list().subscribe(f => this.fields.set(f));
    this.cropService.listCycles().subscribe(c => {
      this.cycles.set(c);
    });
    this.load();
  }

  load(): void {
    this.yieldPlanService.list().subscribe(p => this.plans.set(p));
  }

  fieldName(id: string): string {
    return this.fields().find(f => f.id === id)?.name ?? '—';
  }

  cycleLabel(id: string): string {
    const c = this.cycles().find(c => c.id === id);
    return c ? `${c.season_year} — Cycle ${c.cycle_number}` : '—';
  }

  openGenerate(): void {
    const ref = this.dialog.open(YieldPlanWizardComponent, {
      data: { areas: this.fields() },
      width: '600px',
      maxWidth: '95vw',
    });
    ref.afterClosed().subscribe(plan => {
      if (plan) this.load();
    });
  }
}
