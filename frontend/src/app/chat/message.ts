import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';

import { FormationsCarousel } from '../blocks/formations-carousel';
import { RegistrationLetter } from '../blocks/registration-letter';
import { RegistrationSeal } from '../blocks/registration-seal';
import { formatText } from '../core/format';
import { Entry, FormationCard, SummaryAction } from '../core/models';
import { CapMark } from '../shared/cap-mark';

/** Une entrée du fil : message du prospect, réponse de l'assistant (blocs) ou avertissement. */
@Component({
  selector: 'app-message',
  imports: [MatIconModule, CapMark, FormationsCarousel, RegistrationLetter, RegistrationSeal],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './message.html',
  styleUrl: './message.scss',
})
export class Message {
  readonly entry = input.required<Entry>();
  readonly summaryOpen = input(false);
  readonly pending = input(false);
  readonly register = output<FormationCard>();
  readonly act = output<SummaryAction>();

  protected readonly formatText = formatText;
}
