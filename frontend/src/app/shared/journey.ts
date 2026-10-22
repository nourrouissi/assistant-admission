import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';

import { JourneyStep } from '../core/journey';

/** Fil « Votre parcours » : Découvrir → Vérifier → Candidater. Vertical (colonne) ou compact (mobile). */
@Component({
  selector: 'app-journey',
  imports: [MatIconModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ol [class.compact]="compact()" aria-label="Votre parcours">
      @for (step of steps(); track step.title; let index = $index) {
        <li [attr.data-state]="step.state" [attr.aria-current]="step.state === 'active' ? 'step' : null">
          <span class="marker">
            @if (step.state === 'done') {
              <mat-icon>check</mat-icon>
            } @else {
              <mat-icon>{{ step.icon }}</mat-icon>
            }
          </span>
          <span class="text">
            <span class="title">{{ step.title }}</span>
            @if (!compact()) {
              <span class="hint">{{ step.hint }}</span>
            }
          </span>
          <span class="sr-only">
            {{ step.state === 'done' ? '(terminée)' : step.state === 'active' ? '(en cours)' : '(à venir)' }}
          </span>
        </li>
      }
    </ol>
  `,
  styleUrl: './journey.scss',
})
export class Journey {
  readonly steps = input.required<JourneyStep[]>();
  readonly compact = input(false);
}
