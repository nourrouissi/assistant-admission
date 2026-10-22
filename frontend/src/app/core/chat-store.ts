import { HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, effect, inject, signal } from '@angular/core';

import { ChatApi } from './chat-api';
import { journeyFrom } from './journey';
import { Block, ChatRequest, Entry, FormationCard, RegistrationStage, SummaryAction } from './models';

const STORAGE_KEY = 'lumen.conversation.v1';

interface Saved {
  sessionId: string;
  entries: Entry[];
  registration: RegistrationStage;
}

/** Texte affiché dans le fil quand le prospect clique sur un bouton du récapitulatif. */
const ACTION_LABELS: Record<SummaryAction, string> = {
  confirm: 'Je confirme ma demande.',
  modify: 'Je souhaite modifier mes informations.',
  cancel: "J'annule ma demande.",
};

/**
 * État de la conversation (signals).
 * La conversation est aussi gardée dans le navigateur : le backend la conserve,
 * mais ne permet pas de la relire, et un rafraîchissement ne doit rien effacer.
 */
@Injectable({ providedIn: 'root' })
export class ChatStore {
  private readonly api = inject(ChatApi);

  readonly sessionId = signal('');
  readonly entries = signal<Entry[]>([]);
  readonly registration = signal<RegistrationStage>(null);
  readonly pending = signal(false);

  readonly started = computed(() => this.entries().length > 0);
  readonly journey = computed(() => journeyFrom(this.entries(), this.registration()));

  /** Seul le dernier récapitulatif, encore en attente, garde ses boutons actifs. */
  readonly openSummaryId = computed(() => {
    if (this.registration() !== 'summary') return null;
    const entry = [...this.entries()].reverse().find(
      (item) => item.role === 'assistant' && item.blocks.some((block) => block.type === 'registration_summary'),
    );
    return entry?.id ?? null;
  });

  constructor() {
    this.restore();
    effect(() => this.save({
      sessionId: this.sessionId(),
      entries: this.entries(),
      registration: this.registration(),
    }));
  }

  send(text: string): void {
    const message = text.trim();
    if (!message || this.pending()) return;
    this.push('user', [{ type: 'text', text: message }]);
    void this.call({ message });
  }

  /** Bouton « S'inscrire » d'une carte : la formation exacte est connue. */
  register(card: FormationCard): void {
    if (this.pending()) return;
    this.push('user', [{ type: 'text', text: `Je souhaite m'inscrire à « ${card.specialty} » (${card.school}).` }], true);
    void this.call({ action: 'register', formation_id: card.id });
  }

  /** Boutons Confirmer / Modifier / Annuler (Annuler aussi pendant la collecte des coordonnées). */
  act(action: SummaryAction): void {
    if (this.pending()) return;
    this.push('user', [{ type: 'text', text: ACTION_LABELS[action] }], true);
    void this.call({ action });
  }

  reset(): void {
    this.entries.set([]);
    this.sessionId.set('');
    this.registration.set(null);
  }

  private async call(body: Omit<ChatRequest, 'session_id'>): Promise<void> {
    this.pending.set(true);
    try {
      const response = await this.api.send({ ...body, session_id: this.sessionId() });
      this.sessionId.set(response.session_id);
      this.registration.set(response.registration ?? null);
      if (response.blocks.length) this.push('assistant', response.blocks);
    } catch (error) {
      this.push('notice', [{ type: 'text', text: errorMessage(error) }]);
    } finally {
      this.pending.set(false);
    }
  }

  private push(role: Entry['role'], blocks: Block[], action = false): void {
    const entry: Entry = { id: crypto.randomUUID(), role, blocks, ...(action ? { action } : {}) };
    this.entries.update((entries) => [...entries, entry]);
  }

  private restore(): void {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null') as Saved | null;
      if (!saved || !Array.isArray(saved.entries)) return;
      this.sessionId.set(saved.sessionId ?? '');
      this.entries.set(saved.entries);
      this.registration.set(saved.registration ?? null);
    } catch {
      // Stockage indisponible ou illisible : nouvelle conversation
    }
  }

  private save(state: Saved): void {
    try {
      if (state.entries.length) localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      else localStorage.removeItem(STORAGE_KEY);
    } catch {
      // Stockage indisponible (navigation privée) : la conversation reste en mémoire
    }
  }
}

export function errorMessage(error: unknown): string {
  const status = error instanceof HttpErrorResponse ? error.status : -1;
  if (status === 429) {
    return 'Vous avez envoyé beaucoup de messages en peu de temps. Merci de patienter une minute avant de réessayer.';
  }
  if (status === 0) return 'Le serveur ne répond pas. Vérifiez votre connexion, puis réessayez.';
  if (status === 400) return "Votre message n'a pas pu être traité. Merci de le reformuler.";
  return 'Une erreur est survenue. Merci de réessayer dans un instant.';
}
