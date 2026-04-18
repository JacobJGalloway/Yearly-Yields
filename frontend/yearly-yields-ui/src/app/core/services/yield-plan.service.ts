import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

export type ConfidenceLevel = 'high' | 'medium' | 'low';

export interface YieldPlan {
  id: string;
  growing_area_id: string;
  crop_cycle_id: string;
  recommended_plant_quantity: number;
  target_yield: number;
  confidence_level: ConfidenceLevel;
  reasoning: string;
  created_at: string;
  updated_at: string;
}

export interface YieldPlanCreate {
  crop_cycle_id: string;
  target_yield: number;
}

@Injectable({ providedIn: 'root' })
export class YieldPlanService {
  private http = inject(HttpClient);
  private base = '/api/v1/yield-plans';

  list(crop_cycle_id?: string): Observable<YieldPlan[]> {
    let params = new HttpParams();
    if (crop_cycle_id) params = params.set('crop_cycle_id', crop_cycle_id);
    return this.http.get<YieldPlan[]>(`${this.base}/`, { params });
  }

  create(payload: YieldPlanCreate): Observable<YieldPlan> {
    return this.http.post<YieldPlan>(`${this.base}/`, payload);
  }
}
