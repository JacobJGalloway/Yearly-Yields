import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export type UserRole = 'owner' | 'farmer' | 'hired_hand';

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  phone: string | null;
  address: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserCreate {
  email: string;
  password: string;
  full_name: string;
  role: UserRole;
}

export interface UserUpdate {
  full_name?: string;
  is_active?: boolean;
  phone?: string;
  address?: string;
}

@Injectable({ providedIn: 'root' })
export class UserService {
  private http = inject(HttpClient);
  private base = '/api/v1/users';

  me(): Observable<User> {
    return this.http.get<User>(`${this.base}/me`);
  }

  list(): Observable<User[]> {
    return this.http.get<User[]>(`${this.base}/`);
  }

  create(payload: UserCreate): Observable<User> {
    return this.http.post<User>(`${this.base}/`, payload);
  }

  update(id: string, payload: UserUpdate): Observable<User> {
    return this.http.patch<User>(`${this.base}/${id}`, payload);
  }
}
