import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

import { SummaryAction, SummaryBlock } from '../core/models';
import { SunMark } from '../shared/sun-mark';

/**
 * Récapitulatif de la demande, présenté comme une lettre de candidature.
 * Confirmation explicite par bouton uniquement ; seul le dernier récapitulatif reste actif.
 */
@Component({
  selector: 'app-registration-letter',
  imports: [MatButtonModule, MatIconModule, SunMark],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './registration-letter.html',
  styleUrl: './registration-letter.scss',
})
export class RegistrationLetter {
  readonly block = input.required<SummaryBlock>();
  readonly open = input(false);
  readonly pending = input(false);
  readonly act = output<SummaryAction>();

  protected readonly fields = computed(() => {
    const applicant = this.block().applicant;
    return [
      { icon: 'badge', label: 'Nom', value: applicant.last_name },
      { icon: 'person', label: 'Prénom', value: applicant.first_name },
      { icon: 'alternate_email', label: 'E-mail', value: applicant.email },
      { icon: 'call', label: 'Téléphone', value: applicant.phone },
    ];
  });
}
