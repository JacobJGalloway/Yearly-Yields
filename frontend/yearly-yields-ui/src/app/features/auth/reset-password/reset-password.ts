import { Component, OnInit, inject } from '@angular/core';
import { AbstractControl, FormBuilder, ReactiveFormsModule, ValidationErrors, Validators } from '@angular/forms';
import { Router, RouterLink, ActivatedRoute } from '@angular/router';
import { NgIf } from '@angular/common';
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

function passwordsMatch(control: AbstractControl): ValidationErrors | null {
  const pw = control.get('new_password')?.value;
  const confirm = control.get('confirm_password')?.value;
  return pw && confirm && pw !== confirm ? { mismatch: true } : null;
}

@Component({
  selector: 'app-reset-password',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    NgIf,
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: './reset-password.html',
  styleUrl: '../login/login.scss',
})
export class ResetPasswordComponent implements OnInit {
  private fb = inject(FormBuilder);
  private authService = inject(AuthService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  readonly themeService = inject(ThemeService);

  form = this.fb.group({
    new_password:     ['', [Validators.required, Validators.minLength(8)]],
    confirm_password: ['', Validators.required],
  }, { validators: passwordsMatch });

  loading = false;
  error: string | null = null;
  token = '';

  get logoSrc(): string { return LOGO_MAP[this.themeService.theme()]; }

  ngOnInit(): void {
    this.token = this.route.snapshot.queryParamMap.get('token') ?? '';
    if (!this.token) this.router.navigate(['/login']);
  }

  submit(): void {
    if (this.form.invalid || this.loading) return;
    this.loading = true;
    this.error = null;
    this.authService.resetPassword(this.token, this.form.value.new_password!).subscribe({
      next: () => this.router.navigate(['/login'], { queryParams: { reset: 'success' } }),
      error: (err) => {
        this.error = err.error?.detail ?? 'Reset link is invalid or has expired.';
        this.loading = false;
      },
    });
  }
}
