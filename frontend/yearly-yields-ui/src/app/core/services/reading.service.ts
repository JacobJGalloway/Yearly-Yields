import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

export type AssessmentStatus = 'pending' | 'normal' | 'anomaly' | 'error';
export type ReadingSource = 'manual' | 'nws' | 'fiot' | 'sensor';

export interface SensorReading {
  id: string;
  growing_area_id: string;
  crop_cycle_id: string | null;
  temperature: number;
  humidity: number;
  ph: number | null;
  reading_source: ReadingSource;
  read_at: string;
  received_at: string;
  assessment_status: AssessmentStatus;
  assessment_summary: string | null;
  created_at: string;
}

export interface SensorReadingCreate {
  growing_area_id: string;
  crop_cycle_id?: string;
  temperature: number;
  humidity: number;
  ph?: number;
  reading_source: ReadingSource;
  read_at: string;
}

@Injectable({ providedIn: 'root' })
export class ReadingService {
  private http = inject(HttpClient);
  private base = '/api/v1/sensor-readings';

  list(filters: { growing_area_id?: string; assessment_status?: string; limit?: number } = {}): Observable<SensorReading[]> {
    let params = new HttpParams();
    if (filters.growing_area_id) params = params.set('growing_area_id', filters.growing_area_id);
    if (filters.assessment_status) params = params.set('assessment_status', filters.assessment_status);
    if (filters.limit) params = params.set('limit', filters.limit);
    return this.http.get<SensorReading[]>(`${this.base}/`, { params });
  }

  create(payload: SensorReadingCreate): Observable<SensorReading> {
    return this.http.post<SensorReading>(`${this.base}/`, payload);
  }
}
