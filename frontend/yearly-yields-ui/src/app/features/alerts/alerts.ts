import { DatePipe, TitleCasePipe } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatTableModule } from '@angular/material/table';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Alert, AlertService } from '../../core/services/alert.service';
import { FieldService, GrowingArea } from '../../core/services/field.service';

@Component({
  selector: 'app-alerts',
  standalone: true,
  imports: [
    DatePipe,
    TitleCasePipe,
    FormsModule,
    MatTableModule,
    MatButtonModule,
    MatIconModule,
    MatSlideToggleModule,
    MatTooltipModule,
  ],
  template: `
    <div class="page-header">
      <h2>Alerts</h2>
      <mat-slide-toggle [(ngModel)]="activeOnly" (ngModelChange)="load()">
        Active only
      </mat-slide-toggle>
    </div>

    <table mat-table [dataSource]="alerts()" class="alerts-table mat-elevation-z1">
      <ng-container matColumnDef="field">
        <th mat-header-cell *matHeaderCellDef>Field</th>
        <td mat-cell *matCellDef="let a">{{ fieldName(a.growing_area_id) }}</td>
      </ng-container>

      <ng-container matColumnDef="alert_type">
        <th mat-header-cell *matHeaderCellDef>Type</th>
        <td mat-cell *matCellDef="let a">{{ typeLabel(a.alert_type) }}</td>
      </ng-container>

      <ng-container matColumnDef="status">
        <th mat-header-cell *matHeaderCellDef>Status</th>
        <td mat-cell *matCellDef="let a">
          <span [class]="'status-' + a.status">{{ a.status | titlecase }}</span>
        </td>
      </ng-container>

      <ng-container matColumnDef="created_at">
        <th mat-header-cell *matHeaderCellDef>Raised</th>
        <td mat-cell *matCellDef="let a">{{ a.created_at | date:'short' }}</td>
      </ng-container>

      <ng-container matColumnDef="resolved_at">
        <th mat-header-cell *matHeaderCellDef>Resolved</th>
        <td mat-cell *matCellDef="let a">{{ a.resolved_at ? (a.resolved_at | date:'short') : '—' }}</td>
      </ng-container>

      <ng-container matColumnDef="normal_count">
        <th mat-header-cell *matHeaderCellDef>Normal Readings</th>
        <td mat-cell *matCellDef="let a">{{ a.consecutive_normal_count }} / 3</td>
      </ng-container>

      <ng-container matColumnDef="summary">
        <th mat-header-cell *matHeaderCellDef>Summary</th>
        <td mat-cell *matCellDef="let a" class="summary-cell" [matTooltip]="a.assessment_summary ?? ''">
          {{ a.assessment_summary ? (a.assessment_summary.length > 60 ? a.assessment_summary.slice(0, 60) + '…' : a.assessment_summary) : '—' }}
        </td>
      </ng-container>

      <ng-container matColumnDef="actions">
        <th mat-header-cell *matHeaderCellDef></th>
        <td mat-cell *matCellDef="let a">
          @if (a.status === 'active') {
            <button mat-icon-button matTooltip="Resolve manually" (click)="resolve(a)">
              <mat-icon>check_circle</mat-icon>
            </button>
          }
        </td>
      </ng-container>

      <tr mat-header-row *matHeaderRowDef="columns"></tr>
      <tr mat-row *matRowDef="let row; columns: columns"></tr>
    </table>

    @if (alerts().length === 0) {
      <p class="empty-state">No alerts found.</p>
    }
  `,
  styles: [`
    .page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1em; }
    .page-header h2 { margin: 0; }
    .alerts-table { width: 100%; }
    .summary-cell { max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .status-active { color: var(--mat-sys-error); font-weight: 500; }
    .status-resolved { color: var(--mat-sys-primary); font-weight: 500; }
    .empty-state { color: var(--mat-sys-on-surface-variant); margin-top: 2em; text-align: center; }
  `],
})
export class AlertsComponent implements OnInit {
  private alertService = inject(AlertService);
  private fieldService = inject(FieldService);

  alerts = signal<Alert[]>([]);
  fields = signal<GrowingArea[]>([]);
  activeOnly = false;
  columns = ['field', 'alert_type', 'status', 'created_at', 'resolved_at', 'normal_count', 'summary', 'actions'];

  ngOnInit(): void {
    this.fieldService.list().subscribe(f => this.fields.set(f));
    this.load();
  }

  load(): void {
    this.alertService.list(this.activeOnly).subscribe(a => this.alerts.set(a));
  }

  fieldName(id: string): string {
    return this.fields().find(f => f.id === id)?.name ?? '—';
  }

  typeLabel(t: string): string {
    return ({ temperature: 'Temperature', humidity: 'Humidity', combined: 'Combined' })[t] ?? t;
  }

  resolve(alert: Alert): void {
    this.alertService.resolve(alert.id).subscribe(() => this.load());
  }
}
