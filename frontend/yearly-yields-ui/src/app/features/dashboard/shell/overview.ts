import { Component } from '@angular/core';
import { MatCardModule } from '@angular/material/card';

@Component({
  selector: 'app-overview',
  standalone: true,
  imports: [MatCardModule],
  template: `
    <h2>Overview</h2>
    <mat-card>
      <mat-card-content>
        <p>Dashboard components coming soon.</p>
      </mat-card-content>
    </mat-card>
  `,
})
export class OverviewComponent {}
