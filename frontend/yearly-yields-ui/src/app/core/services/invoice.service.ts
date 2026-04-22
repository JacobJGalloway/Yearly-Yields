import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export type InvoiceStatus = 'draft' | 'sent' | 'paid' | 'voided';
export type YieldUnit = 'bushels' | 'pounds' | 'tons' | 'units';

export interface Invoice {
  id: string;
  customer_id: string;
  crop_cycle_id: string;
  rate_id: string;
  quantity: number;
  unit: YieldUnit;
  unit_price: number;
  total_amount: number;
  status: InvoiceStatus;
  invoice_date: string;
  due_date: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface InvoiceUpdate {
  quantity?: number;
  notes?: string;
  status?: InvoiceStatus;
}

@Injectable({ providedIn: 'root' })
export class InvoiceService {
  private http = inject(HttpClient);
  private base = '/api/v1/invoices';

  list(): Observable<Invoice[]> {
    return this.http.get<Invoice[]>(`${this.base}/`);
  }

  update(id: string, payload: InvoiceUpdate): Observable<Invoice> {
    return this.http.patch<Invoice>(`${this.base}/${id}`, payload);
  }
}
