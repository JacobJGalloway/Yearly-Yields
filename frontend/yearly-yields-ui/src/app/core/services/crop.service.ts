import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

export type CropCycleStatus = 'active' | 'fallow' | 'harvested' | 'transplanted' | 'abandoned';
export type YieldUnit = 'bushels' | 'pounds' | 'tons' | 'units';

export interface SubPhase {
  name: string;
  label: string;
  day_start: number;
  day_end: number;
}

export interface Crop {
  id: string;
  name: string;
  greenhouse_compatible: boolean;
  typical_cycle_days: number;
  seeding_days: number;
  growing_days: number;
  harvest_days: number;
  sub_phases: SubPhase[];
}

export interface CropCycle {
  id: string;
  growing_area_id: string;
  crop_id: string | null;
  planned_crop_id: string | null;
  season_year: number;
  cycle_number: number;
  planted_at: string;
  harvested_at: string | null;
  forecasted_end_date: string | null;
  yield_unit: YieldUnit;
  target_yield: number | null;
  actual_yield: number | null;
  status: CropCycleStatus;
  created_at: string;
  updated_at: string;
}

export interface CropCycleCreate {
  growing_area_id: string;
  crop_id?: string;
  planned_crop_id?: string;
  season_year: number;
  cycle_number: number;
  planted_at: string;
  yield_unit: YieldUnit;
  target_yield?: number;
  forecasted_end_date?: string;
}

export interface CropCycleUpdate {
  status?: CropCycleStatus;
  actual_yield?: number;
  harvested_at?: string;
  target_yield?: number;
  planned_crop_id?: string;
  forecasted_end_date?: string;
}

@Injectable({ providedIn: 'root' })
export class CropService {
  private http = inject(HttpClient);
  private base = '/api/v1/crops';

  listCrops(): Observable<Crop[]> {
    return this.http.get<Crop[]>(`${this.base}/`);
  }

  listCycles(filters: { growing_area_id?: string; season_year?: number; status?: string } = {}): Observable<CropCycle[]> {
    let params = new HttpParams();
    if (filters.growing_area_id) params = params.set('growing_area_id', filters.growing_area_id);
    if (filters.season_year) params = params.set('season_year', filters.season_year);
    if (filters.status) params = params.set('status', filters.status);
    return this.http.get<CropCycle[]>(`${this.base}/cycles`, { params });
  }

  createCycle(payload: CropCycleCreate): Observable<CropCycle> {
    return this.http.post<CropCycle>(`${this.base}/cycles`, payload);
  }

  updateCycle(id: string, payload: CropCycleUpdate): Observable<CropCycle> {
    return this.http.patch<CropCycle>(`${this.base}/cycles/${id}`, payload);
  }
}
