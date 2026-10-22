import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';

import { ResultBlock } from '../core/models';
import { TidyPipe } from '../core/tidy.pipe';
import { CapMark } from '../shared/cap-mark';

const OTHER_OUTCOMES = {
  duplicate: { icon: 'content_copy', label: 'Demande déjà existante', tone: 'amber' },
  unavailable: { icon: 'block', label: 'Formation indisponible', tone: 'rose' },
  cancelled: { icon: 'undo', label: 'Aucune donnée enregistrée', tone: 'slate' },
} as const;

/**
 * Issue de l'inscription. Demande enregistrée : les toques s'envolent, avec le statut « Nouvelle ».
 * Autres issues : une étiquette discrète (le texte de l'assistant les explique déjà).
 */
@Component({
  selector: 'app-registration-seal',
  imports: [MatCardModule, MatIconModule, CapMark, TidyPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './registration-seal.html',
  styleUrl: './registration-seal.scss',
})
export class RegistrationSeal {
  readonly block = input.required<ResultBlock>();

  protected readonly other = computed(() => {
    const outcome = this.block().outcome;
    return outcome === 'created' ? null : OTHER_OUTCOMES[outcome];
  });

  // Toques lancées : position de départ, hauteur, rotation, délai
  protected readonly caps = [
    { x: 14, rise: 150, turn: -40, delay: 0.1, size: 30 },
    { x: 30, rise: 190, turn: 35, delay: 0.25, size: 24 },
    { x: 48, rise: 210, turn: -20, delay: 0, size: 36 },
    { x: 66, rise: 180, turn: 45, delay: 0.2, size: 26 },
    { x: 84, rise: 155, turn: -35, delay: 0.35, size: 30 },
  ];

  // Confettis rouges, bordeaux et blancs
  protected readonly confetti = Array.from({ length: 26 }, (_, index) => ({
    x: (index * 37) % 100,
    drift: ((index * 53) % 80) - 40,
    delay: ((index * 17) % 10) / 20,
    color: ['#e2231a', '#6d1f2f', '#ffffff', '#231f20'][index % 4],
    spin: 180 + ((index * 41) % 360),
  }));
}
