import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

export type AlertStatus = 'active' | 'resolved';
export type AlertType = 'temperature' | 'humidity' | 'combined';

export interface Alert {
  id: string;
  growing_area_id: string;
  crop_cycle_id: string | null;
  triggering_reading_id: string;
  alert_type: AlertType;
  status: AlertStatus;
  consecutive_normal_count: number;
  last_email_sent_at: string | null;
  resolved_at: string | null;
  assessment_summary: string | null;
  created_at: string;
  updated_at: string;
}

@Injectable({ providedIn: 'root' })
export class AlertService {
  private http = inject(HttpClient);
  private base = '/api/v1/alerts';

  list(activeOnly = false): Observable<Alert[]> {
    let params = new HttpParams();
    if (activeOnly) params = params.set('active_only', true);
    return this.http.get<Alert[]>(`${this.base}/`, { params });
  }

  resolve(id: string): Observable<Alert> {
    return this.http.patch<Alert>(`${this.base}/${id}`, { status: 'resolved' });
  }
}
