import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export type GrowingAreaType = 'open_field' | 'dwc_greenhouse';

export interface GrowingArea {
  id: string;
  owner_id: string;
  name: string;
  area_type: GrowingAreaType;
  latitude: number;
  longitude: number;
  area_acres: number | null;
  area_sqft: number | null;
  nws_station_id: string | null;
  temp_offset_f: number | null;
  humidity_offset_pct: number | null;
  target_temp_f: number | null;
  target_humidity_pct: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface GrowingAreaCreate {
  name: string;
  area_type: GrowingAreaType;
  latitude: number;
  longitude: number;
  area_acres?: number;
  area_sqft?: number;
  nws_station_id?: string;
  temp_offset_f?: number;
  humidity_offset_pct?: number;
  target_temp_f?: number;
  target_humidity_pct?: number;
}

export interface GrowingAreaUpdate {
  name?: string;
  is_active?: boolean;
  area_acres?: number;
  area_sqft?: number;
  nws_station_id?: string;
  temp_offset_f?: number;
  humidity_offset_pct?: number;
  target_temp_f?: number;
  target_humidity_pct?: number;
}

@Injectable({ providedIn: 'root' })
export class FieldService {
  private http = inject(HttpClient);
  private base = '/api/v1/fields';

  list(): Observable<GrowingArea[]> {
    return this.http.get<GrowingArea[]>(`${this.base}/`);
  }

  create(payload: GrowingAreaCreate): Observable<GrowingArea> {
    return this.http.post<GrowingArea>(`${this.base}/`, payload);
  }

  update(id: string, payload: GrowingAreaUpdate): Observable<GrowingArea> {
    return this.http.patch<GrowingArea>(`${this.base}/${id}`, payload);
  }
}
