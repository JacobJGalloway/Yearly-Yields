import { Injectable, signal } from '@angular/core';

export type AppTheme = 'default' | 'light' | 'dark';

const STORAGE_KEY = 'yy-theme';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  readonly theme = signal<AppTheme>(this.loadTheme());

  setTheme(theme: AppTheme): void {
    this.theme.set(theme);
    localStorage.setItem(STORAGE_KEY, theme);
    this.applyTheme(theme);
  }

  init(): void {
    this.applyTheme(this.theme());
  }

  private loadTheme(): AppTheme {
    return (localStorage.getItem(STORAGE_KEY) as AppTheme) ?? 'default';
  }

  private applyTheme(theme: AppTheme): void {
    const body = document.body;
    body.classList.remove('app-theme-default', 'app-theme-light', 'app-theme-dark');
    body.classList.add(`app-theme-${theme}`);

    const scheme = theme === 'dark' ? 'dark' : theme === 'light' ? 'light' : 'light dark';
    body.style.colorScheme = scheme;
  }
}
