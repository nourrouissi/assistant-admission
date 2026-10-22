import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';

import { ResultBlock } from '../core/models';

const OTHER_OUTCOMES = {
  duplicate: { icon: 'content_copy', label: 'Demande déjà existante', tone: 'amber' },
  unavailable: { icon: 'block', label: 'Formation indisponible', tone: 'rose' },
  cancelled: { icon: 'undo', label: 'Aucune donnée enregistrée', tone: 'slate' },
} as const;

/**
 * Issue de l'inscription. Demande enregistrée : un sceau de cire se pose, avec le statut « Nouvelle ».
 * Autres issues : une étiquette discrète (le texte de l'assistant les explique déjà).
 */
@Component({
  selector: 'app-registration-seal',
  imports: [MatIconModule],
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

  // Bord de la cire (festons) et rayons du soleil frappé dans le sceau
  protected readonly bumps = Array.from({ length: 18 }, (_, index) => {
    const angle = (index * 20 * Math.PI) / 180;
    return { x: 60 + 47 * Math.cos(angle), y: 60 + 47 * Math.sin(angle) };
  });
  protected readonly rays = Array.from({ length: 16 }, (_, index) => index * 22.5);
  protected readonly sparks = Array.from({ length: 12 }, (_, index) => {
    const angle = (index * 30 * Math.PI) / 180;
    return { dx: Math.round(Math.cos(angle) * 110), dy: Math.round(Math.sin(angle) * 80) };
  });
}
