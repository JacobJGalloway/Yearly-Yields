import { Component, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTableModule } from '@angular/material/table';
import { TitleCasePipe } from '@angular/common';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Crop, CropCycle, CropService } from '../../core/services/crop.service';
import { FieldService, GrowingArea } from '../../core/services/field.service';
import { CropCycleDialogComponent } from './crop-cycle-dialog';

@Component({
  selector: 'app-crop-cycles',
  standalone: true,
  imports: [
    TitleCasePipe,
    MatTableModule,
    MatButtonModule,
    MatIconModule,
    MatTooltipModule,
  ],
  template: `
    <div class="page-header">
      <h2>Crop Cycles</h2>
      <button mat-flat-button (click)="openCreate()">
        <mat-icon>add</mat-icon> Start Cycle
      </button>
    </div>

    <table mat-table [dataSource]="cycles()" class="cycles-table mat-elevation-z1">
      <ng-container matColumnDef="field">
        <th mat-header-cell *matHeaderCellDef>Field</th>
        <td mat-cell *matCellDef="let c">{{ fieldName(c.growing_area_id) }}</td>
      </ng-container>

      <ng-container matColumnDef="crop">
        <th mat-header-cell *matHeaderCellDef>Crop</th>
        <td mat-cell *matCellDef="let c">{{ cropName(c.crop_id) | titlecase }}</td>
      </ng-container>

      <ng-container matColumnDef="phase">
        <th mat-header-cell *matHeaderCellDef>Phase</th>
        <td mat-cell *matCellDef="let c">
          <span [class]="'phase-' + currentPhase(c)">{{ phaseLabel(c) }}</span>
          @if (currentSubPhase(c)) {
            <br><small class="sub-phase-label">{{ currentSubPhase(c) }}</small>
          }
        </td>
      </ng-container>

      <ng-container matColumnDef="planted_at">
        <th mat-header-cell *matHeaderCellDef>Planted</th>
        <td mat-cell *matCellDef="let c">{{ c.planted_at }}</td>
      </ng-container>

      <ng-container matColumnDef="season">
        <th mat-header-cell *matHeaderCellDef>Season</th>
        <td mat-cell *matCellDef="let c">{{ c.season_year }}</td>
      </ng-container>

      <ng-container matColumnDef="status">
        <th mat-header-cell *matHeaderCellDef>Status</th>
        <td mat-cell *matCellDef="let c">
          <span [class]="'status-' + c.status">{{ statusLabel(c.status) }}</span>
        </td>
      </ng-container>

      <ng-container matColumnDef="yield">
        <th mat-header-cell *matHeaderCellDef>Yield</th>
        <td mat-cell *matCellDef="let c">
          {{ c.actual_yield ? c.actual_yield + ' ' + c.yield_unit : (c.target_yield ? 'Target: ' + c.target_yield : '—') }}
        </td>
      </ng-container>

      <ng-container matColumnDef="actions">
        <th mat-header-cell *matHeaderCellDef></th>
        <td mat-cell *matCellDef="let c">
          @if (c.status === 'active' && isContinuousPick(c)) {
            <button mat-icon-button matTooltip="Log Pick" aria-label="Log harvest pick" (click)="logPick(c)" [disabled]="logging().has(c.id)">
              <mat-icon>agriculture</mat-icon>
            </button>
          }
          @if (c.status === 'active' || c.status === 'fallow') {
            <button mat-icon-button matTooltip="Update" aria-label="Update crop cycle" (click)="openEdit(c)">
              <mat-icon>edit</mat-icon>
            </button>
          }
        </td>
      </ng-container>

      <tr mat-header-row *matHeaderRowDef="columns"></tr>
      <tr mat-row *matRowDef="let row; columns: columns"></tr>
    </table>
  `,
  styles: [`
    .page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
    .page-header h2 { margin: 0; }
    .cycles-table { width: 100%; }
    .status-active { color: var(--mat-sys-primary); font-weight: 500; }
    .status-fallow { color: var(--mat-sys-on-surface-variant); }
    .status-harvested { color: var(--yy-harvest-gold); font-weight: 500; }
    .status-abandoned { color: var(--mat-sys-error); }
    .phase-seeding { color: var(--mat-sys-on-surface-variant); }
    .phase-growing { color: var(--mat-sys-primary); font-weight: 500; }
    .phase-harvesting { color: var(--yy-harvest-gold); font-weight: 500; }
    .phase-complete { color: var(--mat-sys-on-surface-variant); }
    .sub-phase-label { color: var(--mat-sys-on-surface-variant); font-size: 0.75em; font-weight: 400; }

    /* Harvest gold fails WCAG AA on parchment/white table surfaces (see
       docs/accessibility-audit-v1.3.md) — swap to the accessible variant
       in default/light themes. Dark theme's surface already passes AA. */
    :host-context(.app-theme-default) .status-harvested,
    :host-context(.app-theme-light) .status-harvested,
    :host-context(.app-theme-default) .phase-harvesting,
    :host-context(.app-theme-light) .phase-harvesting {
      color: var(--yy-harvest-gold-accessible);
    }

    /* Field green fails WCAG AA (4.10:1) as text on parchment in default theme.
       Light theme's field-green-on-white already passes AA, so no swap needed there. */
    :host-context(.app-theme-default) .status-active,
    :host-context(.app-theme-default) .phase-growing {
      color: var(--yy-field-green-accessible);
    }
  `],
})
export class CropCyclesComponent implements OnInit {
  private cropService = inject(CropService);
  private fieldService = inject(FieldService);
  private dialog = inject(MatDialog);
  private snackBar = inject(MatSnackBar);

  cycles = signal<CropCycle[]>([]);
  fields = signal<GrowingArea[]>([]);
  crops = signal<Crop[]>([]);
  logging = signal<Set<string>>(new Set());
  columns = ['field', 'crop', 'phase', 'planted_at', 'season', 'status', 'yield', 'actions'];

  ngOnInit(): void {
    this.fieldService.list().subscribe(f => this.fields.set(f));
    this.cropService.listCrops().subscribe(c => this.crops.set(c));
    this.load();
  }

  load(): void {
    this.cropService.listCycles().subscribe(c => this.cycles.set(c));
  }

  fieldName(id: string): string {
    return this.fields().find(f => f.id === id)?.name ?? '—';
  }

  cropName(id: string | null): string {
    if (!id) return '—';
    return this.crops().find(c => c.id === id)?.name ?? '—';
  }

  currentPhase(cycle: CropCycle): string {
    if (cycle.status !== 'active') return 'complete';
    const crop = this.crops().find(c => c.id === cycle.crop_id);
    if (!crop) return 'complete';
    const daysIn = Math.floor((Date.now() - new Date(cycle.planted_at).getTime()) / 86400000);
    if (daysIn < crop.seeding_days) return 'seeding';
    if (daysIn < crop.seeding_days + crop.growing_days) return 'growing';
    return 'harvesting';
  }

  phaseLabel(cycle: CropCycle): string {
    if (cycle.status !== 'active') return '—';
    const phase = this.currentPhase(cycle);
    return ({ seeding: 'Seeding', growing: 'Growing', harvesting: 'Harvesting', complete: '—' })[phase] ?? '—';
  }

  currentSubPhase(cycle: CropCycle): string {
    if (cycle.status !== 'active') return '';
    const crop = this.crops().find(c => c.id === cycle.crop_id);
    if (!crop) return '';
    const daysIn = Math.floor((Date.now() - new Date(cycle.planted_at).getTime()) / 86400000);
    const planted = new Date(cycle.planted_at);
    const month = planted.getMonth() + 1;

    switch (crop.name) {
      case 'tomatoes':
        if (daysIn < 10)  return 'Germination';
        if (daysIn < 30)  return 'Seedling';
        if (daysIn < 60)  return 'Vegetative';
        if (daysIn < 75)  return 'Flowering & Fruit Set';
        if (daysIn < 110) return 'Fruiting & Ripening';
        return 'Harvest';

      case 'arugula_lettuce': {
        const isSummer = month >= 6 && month <= 8;
        if (daysIn < 7)  return 'Germination';
        if (daysIn < 14) return 'Seedling';
        if (daysIn < 25) return 'Rapid Growth';
        return isSummer ? 'Baby Leaf Harvest' : 'Full Leaf Harvest';
      }

      case 'soybeans': {
        const day = planted.getDate();
        const isDoubleCrop = month > 6 || (month === 6 && day >= 15);
        if (daysIn < 8) return 'Germination';
        if (isDoubleCrop) {
          if (daysIn < 30) return 'Vegetative';
          if (daysIn < 60) return 'Flowering & Pod Set';
          if (daysIn < 80) return 'Seed Fill & Maturation';
          return 'Field Harvest';
        }
        if (daysIn < 45)  return 'Vegetative';
        if (daysIn < 90)  return 'Flowering & Pod Set';
        if (daysIn < 120) return 'Seed Fill & Maturation';
        return 'Field Harvest';
      }

      case 'corn':
        if (daysIn < 10)  return 'Germination';
        if (daysIn < 75)  return 'Vegetative';
        if (daysIn < 85)  return 'Silking & Pollination';
        if (daysIn < 130) return 'Grain Fill & Drying';
        return 'Field Harvest';

      default: {
        const sp = crop.sub_phases?.find(p => daysIn >= p.day_start && daysIn < p.day_end);
        return sp?.label ?? '';
      }
    }
  }

  isContinuousPick(cycle: CropCycle): boolean {
    // Only tomatoes use continuous-pick harvesting today (see PhaseDays.min_pick_interval_days).
    return this.crops().find(c => c.id === cycle.crop_id)?.name === 'tomatoes';
  }

  logPick(cycle: CropCycle): void {
    this.logging.update(s => new Set(s).add(cycle.id));
    this.cropService.logPick(cycle.growing_area_id, cycle.growing_area_plot_id).subscribe({
      next: () => {
        this.logging.update(s => { const next = new Set(s); next.delete(cycle.id); return next; });
        this.snackBar.open('Pick logged', 'Dismiss', { duration: 3000 });
      },
      error: () => this.logging.update(s => { const next = new Set(s); next.delete(cycle.id); return next; }),
    });
  }

  statusLabel(s: string): string {
    return ({ active: 'Active', fallow: 'Fallow', harvested: 'Harvested', transplanted: 'Transplanted', abandoned: 'Abandoned' })[s] ?? s;
  }

  openCreate(): void {
    this.dialog.open(CropCycleDialogComponent, {
      data: { fields: this.fields(), crops: this.crops() },
    }).afterClosed().subscribe(result => { if (result) this.load(); });
  }

  openEdit(cycle: CropCycle): void {
    this.dialog.open(CropCycleDialogComponent, {
      data: { cycle, fields: this.fields(), crops: this.crops() },
    }).afterClosed().subscribe(result => { if (result) this.load(); });
  }
}
