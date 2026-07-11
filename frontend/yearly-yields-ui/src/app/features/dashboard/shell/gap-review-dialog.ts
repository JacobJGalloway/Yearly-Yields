import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { DataGap, DataGapService } from '../../../core/services/data-gap.service';

@Component({
  selector: 'app-gap-review-dialog',
  standalone: true,
  imports: [DatePipe, MatButtonModule, MatDialogModule, MatIconModule, MatProgressSpinnerModule],
  template: `
    <h2 mat-dialog-title>NWS Data Gaps</h2>
    <mat-dialog-content>
      <p class="hint">These open fields have not received NWS readings for 7 or more days.
        Acknowledging a gap suppresses this notice for 7 days.</p>
      @for (gap of gaps(); track gap.area_id) {
        <div class="gap-row">
          <div class="gap-info">
            <span class="area-name">{{ gap.area_name }}</span>
            <span class="gap-detail">
              {{ gap.gap_days }} day{{ gap.gap_days !== 1 ? 's' : '' }} —
              last reading {{ gap.last_reading_at ? (gap.last_reading_at | date:'MMM d, y') : 'never' }}
            </span>
          </div>
          <button mat-stroked-button [disabled]="acknowledging().has(gap.area_id)" (click)="acknowledge(gap)">
            @if (acknowledging().has(gap.area_id)) {
              <mat-spinner diameter="16" aria-label="Acknowledging gap" />
            } @else {
              Acknowledge
            }
          </button>
        </div>
      }
      @if (gaps().length === 0) {
        <p class="all-clear">All gaps acknowledged.</p>
      }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>Close</button>
    </mat-dialog-actions>
  `,
  styles: [`
    .hint { color: var(--mat-sys-on-surface-variant); font-size: 0.875rem; margin: 0 0 16px; }
    .gap-row { display: flex; align-items: center; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); }
    .gap-row:last-of-type { border-bottom: none; }
    .gap-info { display: flex; flex-direction: column; gap: 2px; }
    .area-name { font-weight: 500; }
    .gap-detail { font-size: 0.8rem; color: var(--mat-sys-on-surface-variant); }
    .all-clear { color: var(--mat-sys-primary); font-weight: 500; text-align: center; padding: 16px 0; }
    mat-dialog-content { min-width: 380px; }

    /* Field green fails WCAG AA (4.10:1) as text on parchment in default theme —
       see docs/accessibility-audit-v1.3.md. Light theme's field-green-on-white
       already passes AA, so no swap needed there. */
    :host-context(.app-theme-default) .all-clear {
      color: var(--yy-field-green-accessible);
    }
  `],
})
export class GapReviewDialogComponent {
  private gapService = inject(DataGapService);
  private dialogRef = inject(MatDialogRef<GapReviewDialogComponent>);

  gaps = signal<DataGap[]>([]);
  acknowledging = signal<Set<string>>(new Set());

  constructor() {
    this.gapService.list().subscribe(g => this.gaps.set(g));
  }

  acknowledge(gap: DataGap): void {
    this.acknowledging.update(s => new Set([...s, gap.area_id]));
    this.gapService.acknowledge(gap.area_id).subscribe({
      next: () => {
        this.gaps.update(gs => gs.filter(g => g.area_id !== gap.area_id));
        this.acknowledging.update(s => { const n = new Set(s); n.delete(gap.area_id); return n; });
      },
      error: () => {
        this.acknowledging.update(s => { const n = new Set(s); n.delete(gap.area_id); return n; });
      },
    });
  }
}
