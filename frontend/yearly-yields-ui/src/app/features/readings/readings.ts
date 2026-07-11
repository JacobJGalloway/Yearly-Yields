import { Component, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatSelectModule } from '@angular/material/select';
import { MatTableModule } from '@angular/material/table';
import { MatTooltipModule } from '@angular/material/tooltip';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CropCycle, CropService } from '../../core/services/crop.service';
import { FieldService, GrowingArea } from '../../core/services/field.service';
import { ReadingService, SensorReading } from '../../core/services/reading.service';
import { ReadingSubmitDialogComponent } from './reading-submit-dialog';

@Component({
  selector: 'app-readings',
  standalone: true,
  imports: [
    DatePipe,
    FormsModule,
    MatTableModule,
    MatButtonModule,
    MatIconModule,
    MatSelectModule,
    MatTooltipModule,
  ],
  template: `
    <div class="page-header">
      <h2>Readings</h2>
      <button mat-flat-button (click)="openSubmit()">
        <mat-icon>add</mat-icon> Submit Reading
      </button>
    </div>

    <div class="filters">
      <mat-select [(ngModel)]="selectedField" (ngModelChange)="load()" placeholder="All Fields">
        <mat-option [value]="null">All Fields</mat-option>
        @for (f of fields(); track f.id) {
          <mat-option [value]="f.id">{{ f.name }}</mat-option>
        }
      </mat-select>

      <mat-select [(ngModel)]="selectedStatus" (ngModelChange)="load()" placeholder="All Statuses">
        <mat-option [value]="null">All Statuses</mat-option>
        <mat-option value="pending">Pending</mat-option>
        <mat-option value="normal">Normal</mat-option>
        <mat-option value="anomalous">Anomalous</mat-option>
        <mat-option value="error">Error</mat-option>
      </mat-select>
    </div>

    <table mat-table [dataSource]="readings()" class="readings-table mat-elevation-z1">
      <ng-container matColumnDef="field">
        <th mat-header-cell *matHeaderCellDef>Field</th>
        <td mat-cell *matCellDef="let r">{{ fieldName(r.growing_area_id) }}</td>
      </ng-container>

      <ng-container matColumnDef="read_at">
        <th mat-header-cell *matHeaderCellDef>Read At</th>
        <td mat-cell *matCellDef="let r">{{ r.read_at | date:'short' }}</td>
      </ng-container>

      <ng-container matColumnDef="temperature">
        <th mat-header-cell *matHeaderCellDef>Temp (°F)</th>
        <td mat-cell *matCellDef="let r">{{ r.temperature }}</td>
      </ng-container>

      <ng-container matColumnDef="humidity">
        <th mat-header-cell *matHeaderCellDef>Humidity (%)</th>
        <td mat-cell *matCellDef="let r">{{ r.humidity }}</td>
      </ng-container>

      <ng-container matColumnDef="source">
        <th mat-header-cell *matHeaderCellDef>Source</th>
        <td mat-cell *matCellDef="let r">{{ sourceLabel(r.reading_source) }}</td>
      </ng-container>

      <ng-container matColumnDef="status">
        <th mat-header-cell *matHeaderCellDef>Status</th>
        <td mat-cell *matCellDef="let r">
          <span [class]="'status-' + r.assessment_status">{{ statusLabel(r.assessment_status) }}</span>
        </td>
      </ng-container>

      <ng-container matColumnDef="summary">
        <th mat-header-cell *matHeaderCellDef>Summary</th>
        <td mat-cell *matCellDef="let r" class="summary-cell" [matTooltip]="r.assessment_summary ?? ''">
          {{ r.assessment_summary ? (r.assessment_summary.length > 60 ? r.assessment_summary.slice(0, 60) + '…' : r.assessment_summary) : '—' }}
        </td>
      </ng-container>

      <tr mat-header-row *matHeaderRowDef="columns"></tr>
      <tr mat-row *matRowDef="let row; columns: columns"></tr>
    </table>
  `,
  styles: [`
    .page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
    .page-header h2 { margin: 0; }
    .filters { display: flex; gap: 1em; margin-bottom: 1em; }
    .filters mat-select { min-width: 160px; }
    .readings-table { width: 100%; }
    .summary-cell { max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .status-pending { color: var(--mat-sys-on-surface-variant); }
    .status-normal { color: var(--mat-sys-primary); font-weight: 500; }
    .status-anomalous { color: var(--mat-sys-error); font-weight: 500; }
    .status-error { color: var(--mat-sys-error); }

    /* Field green fails WCAG AA (4.10:1) as text on parchment in default theme —
       see docs/accessibility-audit-v1.3.md. Light theme's field-green-on-white
       already passes AA, so no swap needed there. */
    :host-context(.app-theme-default) .status-normal {
      color: var(--yy-field-green-accessible);
    }
  `],
})
export class ReadingsComponent implements OnInit {
  private readingService = inject(ReadingService);
  private fieldService = inject(FieldService);
  private cropService = inject(CropService);
  private dialog = inject(MatDialog);

  readings = signal<SensorReading[]>([]);
  fields = signal<GrowingArea[]>([]);
  cycles = signal<CropCycle[]>([]);

  selectedField: string | null = null;
  selectedStatus: string | null = null;

  columns = ['field', 'read_at', 'temperature', 'humidity', 'source', 'status', 'summary'];

  ngOnInit(): void {
    this.fieldService.list().subscribe(f => this.fields.set(f));
    this.cropService.listCycles().subscribe(c => this.cycles.set(c));
    this.load();
  }

  load(): void {
    this.readingService.list({
      growing_area_id: this.selectedField ?? undefined,
      assessment_status: this.selectedStatus ?? undefined,
      limit: 100,
    }).subscribe(r => this.readings.set(r));
  }

  fieldName(id: string): string {
    return this.fields().find(f => f.id === id)?.name ?? '—';
  }

  sourceLabel(s: string): string {
    return ({ manual: 'Manual', noaa: 'NOAA', fiot: 'fIoT', sensor: 'Sensor' })[s] ?? s;
  }

  statusLabel(s: string): string {
    return ({ pending: 'Pending', normal: 'Normal', anomalous: 'Anomalous', error: 'Error' })[s] ?? s;
  }

  openSubmit(): void {
    this.dialog.open(ReadingSubmitDialogComponent, {
      data: { fields: this.fields(), cycles: this.cycles() },
    }).afterClosed().subscribe(result => { if (result) this.load(); });
  }
}
