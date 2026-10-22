import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

import { ELIGIBILITY_LABELS, criterion, diplomaShort } from '../core/format';
import { FormationCard as Card } from '../core/models';

/**
 * Carte « diplôme » d'une formation : sceau du type de diplôme, spécialité, école,
 * critères officiels, et tampon d'éligibilité quand les critères ont été vérifiés.
 */
@Component({
  selector: 'app-formation-card',
  imports: [MatButtonModule, MatIconModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './formation-card.html',
  styleUrl: './formation-card.scss',
})
export class FormationCard {
  readonly card = input.required<Card>();
  readonly disabled = input(false);
  readonly register = output<Card>();

  protected readonly short = computed(() => diplomaShort(this.card()));
  protected readonly criteria = computed(() => {
    const { level, nationality, bac } = this.card().criteria;
    return [
      { icon: 'school', label: 'Niveau', value: criterion(level, 'Tous niveaux') },
      { icon: 'public', label: 'Nationalité', value: criterion(nationality, 'Toutes nationalités') },
      { icon: 'workspace_premium', label: 'Bac', value: criterion(bac, 'Toutes sections') },
    ];
  });
  protected readonly verdict = computed(() => {
    const eligibility = this.card().eligibility;
    return eligibility ? { ...ELIGIBILITY_LABELS[eligibility.status], ...eligibility } : null;
  });
}
