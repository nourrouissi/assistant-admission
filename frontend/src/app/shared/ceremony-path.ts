import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';

import { JourneyStep } from '../core/journey';
import { CapMark } from './cap-mark';

/**
 * Chemin vers le diplôme : Découvrir → Vérifier → Candidater → toque.
 * Une barre rouge avance d'étape en étape ; une petite toque la suit.
 */
@Component({
  selector: 'app-ceremony-path',
  imports: [MatIconModule, CapMark],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <nav class="path" [class.compact]="compact()" aria-label="Votre parcours">
      <div class="track" aria-hidden="true">
        <div class="fill" [style.width.%]="progress()"></div>
      </div>
      <ol>
        @for (step of steps(); track step.title) {
          <li [attr.data-state]="step.state" [attr.aria-current]="step.state === 'active' ? 'step' : null">
            <span class="node">
              <mat-icon>{{ step.state === 'done' ? 'check' : step.icon }}</mat-icon>
            </span>
            <span class="label">{{ step.title }}</span>
            <span class="sr-only">
              {{ step.state === 'done' ? '(terminée)' : step.state === 'active' ? '(en cours)' : '(à venir)' }}
            </span>
          </li>
        }
        <li class="goal" [attr.data-state]="complete() ? 'done' : 'todo'">
          <span class="node"><app-cap-mark [size]="compact() ? 18 : 22" /></span>
          <span class="label">Diplôme</span>
        </li>
      </ol>
    </nav>
  `,
  styleUrl: './ceremony-path.scss',
})
export class CeremonyPath {
  readonly steps = input.required<JourneyStep[]>();
  readonly compact = input(false);

  protected readonly complete = computed(() => this.steps().every((step) => step.state === 'done'));
  /** Avancée de la barre : jusqu'au nœud de l'étape en cours, jusqu'à la toque quand tout est fait. */
  protected readonly progress = computed(() => {
    const steps = this.steps();
    const active = steps.findIndex((step) => step.state === 'active');
    const reached = active === -1 ? steps.length : active;
    return (reached / steps.length) * 100;
  });
}
