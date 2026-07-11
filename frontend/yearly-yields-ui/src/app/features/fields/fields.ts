import { Component, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatTableModule } from '@angular/material/table';
import { MatTooltipModule } from '@angular/material/tooltip';
import { FieldService, GrowingArea } from '../../core/services/field.service';
import { FieldDialogComponent } from './field-dialog';

@Component({
  selector: 'app-fields',
  standalone: true,
  imports: [
    MatTableModule,
    MatButtonModule,
    MatIconModule,
    MatTooltipModule,
  ],
  template: `
    <div class="page-header">
      <h2>Fields</h2>
      <button mat-flat-button (click)="openCreate()">
        <mat-icon>add</mat-icon> Add Field
      </button>
    </div>

    <table mat-table [dataSource]="fields()" class="fields-table mat-elevation-z1">
      <ng-container matColumnDef="name">
        <th mat-header-cell *matHeaderCellDef>Name</th>
        <td mat-cell *matCellDef="let f">{{ f.name }}</td>
      </ng-container>

      <ng-container matColumnDef="area_type">
        <th mat-header-cell *matHeaderCellDef>Type</th>
        <td mat-cell *matCellDef="let f">{{ typeLabel(f.area_type) }}</td>
      </ng-container>

      <ng-container matColumnDef="size">
        <th mat-header-cell *matHeaderCellDef>Size</th>
        <td mat-cell *matCellDef="let f">
          {{ f.area_acres ? f.area_acres + ' acres' : f.area_sqft + ' sq ft' }}
        </td>
      </ng-container>

      <ng-container matColumnDef="location">
        <th mat-header-cell *matHeaderCellDef>Location</th>
        <td mat-cell *matCellDef="let f">{{ f.latitude }}, {{ f.longitude }}</td>
      </ng-container>

      <ng-container matColumnDef="status">
        <th mat-header-cell *matHeaderCellDef>Status</th>
        <td mat-cell *matCellDef="let f">
          <span [class]="f.is_active ? 'status-active' : 'status-inactive'">
            {{ f.is_active ? 'Active' : 'Inactive' }}
          </span>
        </td>
      </ng-container>

      <ng-container matColumnDef="actions">
        <th mat-header-cell *matHeaderCellDef></th>
        <td mat-cell *matCellDef="let f">
          <button mat-icon-button matTooltip="Edit" aria-label="Edit field" (click)="openEdit(f)">
            <mat-icon>edit</mat-icon>
          </button>
        </td>
      </ng-container>

      <tr mat-header-row *matHeaderRowDef="columns"></tr>
      <tr mat-row *matRowDef="let row; columns: columns"></tr>
    </table>
  `,
  styles: [`
    .page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
    .page-header h2 { margin: 0; }
    .fields-table { width: 100%; }
    .status-active { color: var(--mat-sys-primary); font-weight: 500; }
    .status-inactive { color: var(--mat-sys-error); }
  `],
})
export class FieldsComponent implements OnInit {
  private fieldService = inject(FieldService);
  private dialog = inject(MatDialog);

  fields = signal<GrowingArea[]>([]);
  columns = ['name', 'area_type', 'size', 'location', 'status', 'actions'];

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.fieldService.list().subscribe(fields => this.fields.set(fields));
  }

  typeLabel(type: string): string {
    return type === 'open_field' ? 'Open Field' : 'DWC Greenhouse';
  }

  openCreate(): void {
    this.dialog.open(FieldDialogComponent, { data: {} })
      .afterClosed().subscribe(result => { if (result) this.load(); });
  }

  openEdit(field: GrowingArea): void {
    this.dialog.open(FieldDialogComponent, { data: { field } })
      .afterClosed().subscribe(result => { if (result) this.load(); });
  }
}
