import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface Customer {
  id: string;
  owner_id: string;
  name: string;
  email: string;
  phone: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CustomerCreate {
  name: string;
  email: string;
  phone?: string;
}

export interface CustomerUpdate {
  name?: string;
  email?: string;
  phone?: string;
  is_active?: boolean;
}

@Injectable({ providedIn: 'root' })
export class CustomerService {
  private http = inject(HttpClient);
  private base = '/api/v1/customers';

  list(): Observable<Customer[]> {
    return this.http.get<Customer[]>(`${this.base}/`);
  }

  create(payload: CustomerCreate): Observable<Customer> {
    return this.http.post<Customer>(`${this.base}/`, payload);
  }

  update(id: string, payload: CustomerUpdate): Observable<Customer> {
    return this.http.patch<Customer>(`${this.base}/${id}`, payload);
  }
}
