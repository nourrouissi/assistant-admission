import { ChangeDetectionStrategy, Component, output } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';

import { SunMark } from '../shared/sun-mark';

/** Écran d'accueil : une porte d'entrée par partie du parcours, et des exemples de questions. */
@Component({
  selector: 'app-welcome',
  imports: [MatIconModule, SunMark],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './welcome.html',
  styleUrl: './welcome.scss',
})
export class Welcome {
  readonly pick = output<string>();

  protected readonly doors = [
    {
      icon: 'menu_book',
      title: "Comprendre l'admission",
      text: 'Étapes, pièces justificatives, dates et frais.',
      prompt: 'Quels documents dois-je fournir pour déposer une candidature ?',
    },
    {
      icon: 'travel_explore',
      title: 'Trouver ma formation',
      text: 'Diplômes, spécialités et écoles qui vous correspondent.',
      prompt: 'Quelles spécialités proposez-vous en informatique ?',
    },
    {
      icon: 'history_edu',
      title: 'Déposer ma candidature',
      text: "Votre demande d'inscription, pas à pas.",
      prompt: "Je souhaite déposer une demande d'inscription.",
    },
  ];

  protected readonly examples = [
    "J'ai un bac informatique, quelles spécialités me correspondent ?",
    'Quelles formations proposez-vous à Sousse ?',
    'Quelles sont les étapes de la procédure d\'admission ?',
  ];
}
