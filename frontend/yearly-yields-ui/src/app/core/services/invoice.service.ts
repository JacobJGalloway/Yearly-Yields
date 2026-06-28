import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export type InvoiceStatus = 'draft' | 'sent' | 'paid' | 'voided';
export type YieldUnit = 'bushels' | 'pounds' | 'tons' | 'units';

export interface Invoice {
  id: string;
  customer_id: string | null;
  crop_cycle_id: string;
  rate_id: string;
  quantity: number;
  unit: YieldUnit;
  unit_price: number | null;
  total_amount: number | null;
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
  customer_id?: string;
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

  send(id: string): Observable<Invoice> {
    return this.http.post<Invoice>(`${this.base}/${id}/send`, {});
  }

  pay(id: string): Observable<Invoice> {
    return this.http.post<Invoice>(`${this.base}/${id}/pay`, {});
  }

  void(id: string): Observable<Invoice> {
    return this.http.post<Invoice>(`${this.base}/${id}/void`, {});
  }

  downloadPdf(id: string): Observable<Blob> {
    return this.http.get(`${this.base}/${id}/pdf`, { responseType: 'blob' });
  }

  triggerDownload(blob: Blob, invoiceId: string): void {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `invoice-${invoiceId.slice(0, 8)}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  }
}
