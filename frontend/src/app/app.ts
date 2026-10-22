import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  afterRenderEffect,
  computed,
  inject,
  viewChild,
} from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule, MatIconRegistry } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatTooltipModule } from '@angular/material/tooltip';

import { Composer } from './chat/composer';
import { Message } from './chat/message';
import { Welcome } from './chat/welcome';
import { ChatStore } from './core/chat-store';
import { CapMark } from './shared/cap-mark';
import { CeremonyPath } from './shared/ceremony-path';

@Component({
  selector: 'app-root',
  imports: [
    MatButtonModule, MatIconModule, MatProgressBarModule, MatToolbarModule, MatTooltipModule,
    Composer, Message, Welcome, CapMark, CeremonyPath,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  protected readonly store = inject(ChatStore);

  private readonly scroller = viewChild<ElementRef<HTMLElement>>('scroller');
  private readonly composer = viewChild(Composer);
  private firstScroll = true;

  /** Texte d'aide de la zone de saisie, selon l'étape de l'inscription. */
  protected readonly placeholder = computed(() =>
    this.store.registration() === 'collect' ? 'Nom, prénom, e-mail, téléphone…' : 'Posez votre question…',
  );

  constructor() {
    inject(MatIconRegistry).setDefaultFontSetClass('material-symbols-rounded');

    // Après chaque nouvelle entrée : une longue réponse est montrée depuis son début, sinon on va en bas.
    afterRenderEffect(() => {
      this.store.entries();
      this.store.pending();
      const scroller = this.scroller()?.nativeElement;
      if (!scroller) return;
      if (!this.store.started()) {
        scroller.scrollTo({ top: 0 });       // accueil : toujours affiché depuis le haut
        return;
      }
      const behavior: ScrollBehavior = this.firstScroll ? 'auto' : 'smooth';
      this.firstScroll = false;
      const entries = scroller.querySelectorAll<HTMLElement>('[data-entry]');
      const last = entries[entries.length - 1];
      if (last?.dataset['role'] === 'assistant' && last.offsetHeight > scroller.clientHeight * 0.6) {
        scroller.scrollTo({ top: last.offsetTop - 24, behavior });
      } else {
        scroller.scrollTo({ top: scroller.scrollHeight, behavior });
      }
    });
  }

  protected ask(text: string): void {
    this.store.send(text);
    this.composer()?.focus();
  }

  protected restart(): void {
    this.store.reset();
    this.firstScroll = true;
  }
}
