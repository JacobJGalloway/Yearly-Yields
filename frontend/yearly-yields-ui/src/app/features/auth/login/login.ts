import { Component, OnInit, inject } from '@angular/core';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { Store } from '@ngrx/store';
import { Observable } from 'rxjs';
import { AsyncPipe, NgIf } from '@angular/common';
import { RouterLink } from '@angular/router';
import { AuthActions } from '../../../store/auth/auth.actions';
import { selectAuthError, selectAuthLoading, selectIsAuthenticated } from '../../../store/auth/auth.selectors';
import { ActivatedRoute, Router } from '@angular/router';
import { ThemeService, AppTheme } from '../../../core/services/theme.service';

const LOGO_MAP: Record<AppTheme, string> = {
  default: 'brand/Logo Work Default Mode.png',
  light:   'brand/Logo Work Light Mode.png',
  dark:    'brand/Logo Work Dark Mode.png',
};

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatProgressSpinnerModule,
    AsyncPipe,
    NgIf,
  ],
  templateUrl: './login.html',
  styleUrl: './login.scss',
})
export class LoginComponent implements OnInit {
  private fb = inject(FormBuilder);
  private store = inject(Store);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  readonly themeService = inject(ThemeService);

  form: FormGroup;
  loading$: Observable<boolean>;
  error$: Observable<string | null>;
  resetSuccess = false;

  constructor() {
    this.form = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      password: ['', Validators.required],
    });
    this.loading$ = this.store.select(selectAuthLoading);
    this.error$ = this.store.select(selectAuthError);
  }

  get logoSrc(): string {
    return LOGO_MAP[this.themeService.theme()];
  }

  ngOnInit(): void {
    this.themeService.init();
    this.resetSuccess = this.route.snapshot.queryParamMap.get('reset') === 'success';
    this.store.select(selectIsAuthenticated).subscribe(isAuth => {
      if (isAuth) this.router.navigate(['/dashboard']);
    });
  }

  submit(): void {
    if (this.form.invalid) return;
    const { email, password } = this.form.value;
    this.store.dispatch(AuthActions.login({ email, password }));
  }
}
