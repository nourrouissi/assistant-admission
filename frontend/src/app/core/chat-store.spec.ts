import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';

import { ChatApi } from './chat-api';
import { ChatStore } from './chat-store';
import { ChatRequest, ChatResponse, FormationCard } from './models';

describe('ChatStore', () => {
  let requests: ChatRequest[];
  let reply: (request: ChatRequest) => Promise<ChatResponse>;

  const summary = {
    type: 'registration_summary' as const,
    formation: { id: 8, specialty: 'Informatique de gestion', school: 'IMSET GABES' } as FormationCard,
    applicant: { last_name: 'Ben Salah', first_name: 'Amira', email: 'amira@test.com', phone: '+21620123456' },
    actions: ['confirm' as const, 'modify' as const, 'cancel' as const],
  };

  function createStore(): ChatStore {
    TestBed.configureTestingModule({
      providers: [{ provide: ChatApi, useValue: { send: (request: ChatRequest) => { requests.push(request); return reply(request); } } }],
    });
    return TestBed.inject(ChatStore);
  }

  const settle = () => new Promise((resolve) => setTimeout(resolve));

  beforeEach(() => {
    localStorage.clear();
    requests = [];
    reply = async () => ({ session_id: 's-1', blocks: [{ type: 'text', text: 'Bonjour !' }], registration: null });
  });

  it('sends the message, then keeps the session returned by the API', async () => {
    const store = createStore();
    store.send('  Bonjour  ');
    await settle();
    store.send('Merci');
    await settle();
    expect(requests).toEqual([{ message: 'Bonjour', session_id: '' }, { message: 'Merci', session_id: 's-1' }]);
    expect(store.entries().map((entry) => entry.role)).toEqual(['user', 'assistant', 'user', 'assistant']);
  });

  it('sends the exact formation id when « S\'inscrire » is clicked', async () => {
    const store = createStore();
    store.register({ id: 42, specialty: 'Comptabilité', school: 'IMSET SOUSSE' } as FormationCard);
    await settle();
    expect(requests[0]).toEqual({ action: 'register', formation_id: 42, session_id: '' });
    expect(store.entries()[0].action).toBe(true);
  });

  it('keeps only the latest pending summary active', async () => {
    reply = async () => ({ session_id: 's-1', blocks: [summary], registration: 'summary' });
    const store = createStore();
    store.send('mes coordonnées');
    await settle();
    store.send('une question');
    await settle();
    const summaries = store.entries().filter((entry) => entry.role === 'assistant');
    expect(store.openSummaryId()).toBe(summaries[1].id);

    reply = async () => ({ session_id: 's-1', blocks: [{ type: 'registration_result', outcome: 'created' }], registration: null });
    store.act('confirm');
    await settle();
    expect(requests.at(-1)).toEqual({ action: 'confirm', session_id: 's-1' });
    expect(store.openSummaryId()).toBeNull();
  });

  it('shows a clear notice when too many requests are sent', async () => {
    reply = async () => { throw new HttpErrorResponse({ status: 429 }); };
    const store = createStore();
    store.send('Bonjour');
    await settle();
    const notice = store.entries().at(-1)!;
    expect(notice.role).toBe('notice');
    expect(notice.blocks[0]).toEqual(expect.objectContaining({ text: expect.stringContaining('patienter une minute') }));
    expect(store.pending()).toBe(false);
  });

  it('ignores a new message while an answer is pending', async () => {
    let release!: () => void;
    reply = () => new Promise((resolve) => { release = () => resolve({ session_id: 's-1', blocks: [], registration: null }); });
    const store = createStore();
    store.send('Premier');
    store.send('Second');
    expect(requests.length).toBe(1);
    release();
    await settle();
  });
});
