import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { ChatRequest, ChatResponse } from './models';

/** Appel unique au backend : POST /api/chat/ (redirigé vers Django par proxy.conf.json en développement). */
@Injectable({ providedIn: 'root' })
export class ChatApi {
  private readonly http = inject(HttpClient);

  send(body: ChatRequest): Promise<ChatResponse> {
    return firstValueFrom(this.http.post<ChatResponse>('/api/chat/', body));
  }
}
