import { ChangeDetectionStrategy, Component, output } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';

import { CapMark } from '../shared/cap-mark';

/**
 * Accueil : la scène de la remise de diplôme (photo, projecteurs, toques lancées),
 * puis une porte d'entrée par partie du parcours et des exemples de questions.
 */
@Component({
  selector: 'app-welcome',
  imports: [MatButtonModule, MatCardModule, MatIconModule, CapMark],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './welcome.html',
  styleUrl: './welcome.scss',
})
export class Welcome {
  readonly pick = output<string>();

  protected readonly doors = [
    {
      step: 'Étape 1',
      icon: 'menu_book',
      title: "Comprendre l'admission",
      text: 'Étapes, pièces justificatives, dates limites et frais.',
      prompt: 'Quels documents dois-je fournir pour déposer une candidature ?',
    },
    {
      step: 'Étape 2',
      icon: 'school',
      title: 'Trouver ma formation',
      text: 'Diplômes, spécialités et écoles, selon votre profil.',
      prompt: 'Quelles spécialités proposez-vous en informatique ?',
    },
    {
      step: 'Étape 3',
      icon: 'history_edu',
      title: 'Déposer ma candidature',
      text: "Votre demande d'inscription, pas à pas, jusqu'à la confirmation.",
      prompt: "Je souhaite déposer une demande d'inscription.",
    },
  ];

  protected readonly examples = [
    "J'ai un bac informatique, quelles spécialités me correspondent ?",
    'Quelles formations proposez-vous à Sousse ?',
    "Quelles sont les étapes de la procédure d'admission ?",
  ];

  // Toques lancées au-dessus de la scène : position, taille, durée et délai de chacune
  protected readonly caps = [
    { left: 8, size: 34, duration: 7.5, delay: 0, turn: -25 },
    { left: 19, size: 24, duration: 9, delay: 2.4, turn: 30 },
    { left: 31, size: 40, duration: 8.2, delay: 1.1, turn: -15 },
    { left: 63, size: 28, duration: 9.5, delay: 3.2, turn: 25 },
    { left: 76, size: 44, duration: 7.8, delay: 0.6, turn: -30 },
    { left: 88, size: 26, duration: 8.8, delay: 2, turn: 20 },
  ];
}
