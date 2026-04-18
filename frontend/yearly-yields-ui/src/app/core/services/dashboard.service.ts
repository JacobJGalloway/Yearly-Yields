import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

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

@Injectable({ providedIn: 'root' })
export class DashboardService {
  private http = inject(HttpClient);
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

  getRecentReadings(limit = 300): Observable<SensorReading[]> {
    const params = new HttpParams().set('limit', limit);
    return this.http.get<SensorReading[]>(`${this.readingsBase}/`, { params });
  }

  getWeeklySummaries(weeks = 52): Observable<WeeklySummary[]> {
    const params = new HttpParams().set('weeks', weeks);
    return this.http.get<WeeklySummary[]>(`${this.readingsBase}/weekly-summary`, { params });
  }

  sendChatMessage(
    message: string,
    history: ChatMessage[],
  ): Observable<{ response: string }> {
    return this.http.post<{ response: string }>(this.chatBase + '/', { message, history });
  }
}
