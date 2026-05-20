import { Injectable, NgZone, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { BehaviorSubject, Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { CropCycle } from './crop.service';
import { SensorReading } from './reading.service';

export interface WeeklySummary {
  iso_week: number;
  year: number;
  week_label: string;
  avg_temp_f: number | null;
  avg_humidity_pct: number | null;
  reading_count: number;
  growing_area_id: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatSeries {
  name: string;
  data: (number | null)[];
}

export interface ChatResponse {
  type: 'chart' | 'table' | 'link' | 'clarifying_question' | 'text';
  content?: string;
  url?: string;
  title?: string;
  chart_type?: 'bar_grouped' | 'bar_stacked' | 'line_multi' | 'bar_single';
  x_labels?: string[];
  series?: ChatSeries[];
  y_axis_label?: string;
  columns?: string[];
  rows?: (string | number | null)[][];
  options?: string[];
}

@Injectable({ providedIn: 'root' })
export class DashboardService {
  private http = inject(HttpClient);
  private ngZone = inject(NgZone);
  private cyclesBase = '/api/v1/crops/cycles';
  private readingsBase = '/api/v1/readings';
  private chatBase = '/api/v1/agent/chat';

  getCurrentSeasonCycles(): Observable<CropCycle[]> {
    const year = new Date().getFullYear();
    const params = new HttpParams().set('season_year', year).set('status', 'active');
    return this.http.get<CropCycle[]>(`${this.cyclesBase}`, { params });
  }

  getAllCycles(): Observable<CropCycle[]> {
    return this.http.get<CropCycle[]>(`${this.cyclesBase}`);
  }

  getRecentReadings(limit = environment.dashboardReadingsLimit): Observable<SensorReading[]> {
    const params = new HttpParams().set('limit', limit);
    return this.http.get<SensorReading[]>(`${this.readingsBase}/`, { params });
  }

  getWeeklySummaries(weeks = 52): Observable<WeeklySummary[]> {
    const params = new HttpParams().set('weeks', weeks);
    return this.http.get<WeeklySummary[]>(`${this.readingsBase}/weekly-summary`, { params });
  }

  // ── Chat UI state ─────────────────────────────────────────────────────────
  chatOpen$ = new BehaviorSubject(false);
  chatLoading$ = new BehaviorSubject(false);
  chatResponse$ = new BehaviorSubject<ChatResponse | null>(null);
  chatHistory: ChatMessage[] = [];

  sendChat(message: string): void {
    if (this.chatLoading$.value) return;
    const historyBeforeSend = [...this.chatHistory];
    this.chatHistory = [...this.chatHistory, { role: 'user', content: message }];
    this.chatOpen$.next(true);
    this.chatResponse$.next(null);
    this.chatLoading$.next(true);

    this.http.post<ChatResponse>(this.chatBase + '/', { message, history: historyBeforeSend }).subscribe({
      next: res => this.ngZone.run(() => {
        this.chatResponse$.next(res);
        this.chatHistory = [...this.chatHistory, { role: 'assistant', content: this._chatHistoryText(res) }];
        this.chatLoading$.next(false);
      }),
      error: () => this.ngZone.run(() => {
        this.chatResponse$.next({ type: 'text', content: 'Something went wrong. Please try again.' });
        this.chatHistory = [...this.chatHistory, { role: 'assistant', content: 'Error retrieving response.' }];
        this.chatLoading$.next(false);
      }),
    });
  }

  closeChat(): void {
    this.chatOpen$.next(false);
    this.chatResponse$.next(null);
    this.chatHistory = [];
  }

  private _chatHistoryText(res: ChatResponse): string {
    switch (res.type) {
      case 'chart': return `[Chart: ${res.title ?? 'data visualization'}]`;
      case 'table': return `[Table: ${res.title ?? 'data table'}]`;
      case 'link':  return `[Link provided: ${res.content ?? res.url}]`;
      case 'clarifying_question': return `[Asked for clarification: ${res.content}]`;
      default: return res.content ?? '';
    }
  }
}
