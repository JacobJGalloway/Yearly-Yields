import { Component, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { AppTheme } from '../../../core/services/theme.service';

@Component({
  selector: 'app-theme-dialog',
  standalone: true,
  imports: [MatDialogModule, MatButtonModule, MatIconModule],
  template: `
    <h2 mat-dialog-title>Choose Display Mode</h2>
    <mat-dialog-content>
      <div class="theme-options">
        @for (option of options; track option.value) {
          <button mat-stroked-button
            [class.active]="data.current === option.value"
            (click)="pick(option.value)">
            <mat-icon>{{ option.icon }}</mat-icon>
            {{ option.label }}
          </button>
        }
      </div>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>Cancel</button>
    </mat-dialog-actions>
  `,
  styles: [`
    .theme-options { display: flex; flex-direction: column; gap: 8px; min-width: 240px; padding-top: 8px; }
    button.active { border-color: var(--mat-sys-primary); color: var(--mat-sys-primary); font-weight: 600; }

    /* Field green fails WCAG AA (4.10:1) as text on parchment in default theme —
       see docs/accessibility-audit-v1.3.md. Light theme's field-green-on-white
       already passes AA, so no swap needed there. Border-color is unaffected —
       3:1 non-text contrast requirement, which 4.10:1 already clears. */
    :host-context(.app-theme-default) button.active {
      color: var(--yy-field-green-accessible);
    }
  `],
})
export class ThemeDialogComponent {
  data: { current: AppTheme } = inject(MAT_DIALOG_DATA);
  private dialogRef = inject(MatDialogRef<ThemeDialogComponent>);

  options = [
    { value: 'default' as AppTheme, label: 'Default',  icon: 'contrast'      },
    { value: 'light'   as AppTheme, label: 'Light',    icon: 'light_mode'    },
    { value: 'dark'    as AppTheme, label: 'Dark',      icon: 'dark_mode'     },
  ];

  pick(theme: AppTheme): void {
    this.dialogRef.close(theme);
  }
}
