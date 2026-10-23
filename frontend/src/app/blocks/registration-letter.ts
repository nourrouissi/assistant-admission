import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatDividerModule } from '@angular/material/divider';
import { MatIconModule } from '@angular/material/icon';

import { I18n } from '../core/i18n';
import { SummaryAction, SummaryBlock } from '../core/models';
import { TidyPipe } from '../core/tidy.pipe';
import { CapMark } from '../shared/cap-mark';

/**
 * Récapitulatif de la demande, présenté comme un dossier de candidature officiel.
 * Confirmation explicite par bouton uniquement ; seul le dernier récapitulatif reste actif.
 */
@Component({
  selector: 'app-registration-letter',
  imports: [MatButtonModule, MatCardModule, MatDividerModule, MatIconModule, CapMark, TidyPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './registration-letter.html',
  styleUrl: './registration-letter.scss',
})
export class RegistrationLetter {
  readonly block = input.required<SummaryBlock>();
  readonly open = input(false);
  readonly pending = input(false);
  readonly act = output<SummaryAction>();

  protected readonly i18n = inject(I18n);
  protected readonly summaryLabel = "Récapitulatif de votre demande d'inscription";

  protected readonly fields = computed(() => {
    const applicant = this.block().applicant;
    return [
      { icon: 'badge', label: this.i18n.t('Nom'), value: applicant.last_name, ltr: false },
      { icon: 'person', label: this.i18n.t('Prénom'), value: applicant.first_name, ltr: false },
      // E-mail et téléphone toujours écrits de gauche à droite (« +216… », même en arabe)
      { icon: 'alternate_email', label: this.i18n.t('E-mail'), value: applicant.email, ltr: true },
      { icon: 'call', label: this.i18n.t('Téléphone'), value: applicant.phone, ltr: true },
    ];
  });
}
