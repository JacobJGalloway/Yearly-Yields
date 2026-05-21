import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface DataGap {
  area_id: string;
  area_name: string;
  last_reading_at: string | null;
  gap_days: number;
}

@Injectable({ providedIn: 'root' })
export class DataGapService {
  private http = inject(HttpClient);
  private base = '/api/v1/data-gaps';

  list(): Observable<DataGap[]> {
    return this.http.get<DataGap[]>(`${this.base}/`);
  }

  acknowledge(areaId: string): Observable<void> {
    return this.http.post<void>(`${this.base}/${areaId}/acknowledge`, {});
  }
}
