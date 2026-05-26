import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { AuthService } from '../../../core/services/auth.service';
import { ThemeService, AppTheme } from '../../../core/services/theme.service';

const LOGO_MAP: Record<AppTheme, string> = {
  default: 'brand/Logo Work Default Mode.png',
  light:   'brand/Logo Work Light Mode.png',
  dark:    'brand/Logo Work Dark Mode.png',
};

@Component({
  selector: 'app-forgot-password',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: './forgot-password.html',
  styleUrl: '../login/login.scss',
})
export class ForgotPasswordComponent {
  private fb = inject(FormBuilder);
  private authService = inject(AuthService);
  readonly themeService = inject(ThemeService);

  form = this.fb.group({ email: ['', [Validators.required, Validators.email]] });
  loading = false;
  submitted = false;

  get logoSrc(): string { return LOGO_MAP[this.themeService.theme()]; }

  submit(): void {
    if (this.form.invalid || this.loading) return;
    this.loading = true;
    this.authService.forgotPassword(this.form.value.email!).subscribe({
      next: () => { this.submitted = true; this.loading = false; },
      error: () => { this.submitted = true; this.loading = false; }, // don't leak errors
    });
  }
}
