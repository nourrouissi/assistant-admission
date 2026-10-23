import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatDividerModule } from '@angular/material/divider';
import { MatIconModule } from '@angular/material/icon';

import { ELIGIBILITY_LABELS, criterion, diplomaShort } from '../core/format';
import { I18n } from '../core/i18n';
import { FormationCard as Card } from '../core/models';
import { TidyPipe } from '../core/tidy.pipe';

/**
 * Carte d'une formation présentée comme un diplôme : ruban du type de diplôme, spécialité, école,
 * critères officiels, et tampon d'éligibilité quand les critères ont été vérifiés.
 */
@Component({
  selector: 'app-formation-card',
  imports: [MatButtonModule, MatCardModule, MatDividerModule, MatIconModule, TidyPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './formation-card.html',
  styleUrl: './formation-card.scss',
})
export class FormationCard {
  readonly card = input.required<Card>();
  readonly disabled = input(false);
  readonly register = output<Card>();

  protected readonly i18n = inject(I18n);

  protected readonly short = computed(() => diplomaShort(this.card(), this.i18n.lang()));
  protected readonly criteria = computed(() => {
    const { level, nationality, bac } = this.card().criteria;
    const t = (text: string) => this.i18n.t(text);
    return [
      // Critères officiels de l'école cités tels quels ; seuls « All » et les libellés sont traduits
      { icon: 'school', label: t('Niveau'), value: t(criterion(level, 'Tous niveaux')) },
      { icon: 'public', label: t('Nationalité'), value: t(criterion(nationality, 'Toutes nationalités')) },
      { icon: 'workspace_premium', label: t('Bac'), value: t(criterion(bac, 'Toutes sections')) },
    ];
  });
  protected readonly verdict = computed(() => {
    const eligibility = this.card().eligibility;
    return eligibility ? { ...ELIGIBILITY_LABELS[eligibility.status], ...eligibility } : null;
  });
}
