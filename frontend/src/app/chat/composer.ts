import { ChangeDetectionStrategy, Component, ElementRef, input, output, signal, viewChild } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';

const MAX_LENGTH = 2000;

/** Zone de saisie : Entrée pour envoyer, Maj + Entrée pour aller à la ligne. */
@Component({
  selector: 'app-composer',
  imports: [MatIconModule, MatTooltipModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <form class="box" (submit)="submit($event)">
      <label class="sr-only" for="composer-input">Votre message</label>
      <textarea #field id="composer-input" rows="1" [maxLength]="maxLength" [placeholder]="placeholder()"
                [value]="text()" (input)="onInput(field)" (keydown.enter)="onEnter($event)"></textarea>
      @if (text().length > maxLength - 200) {
        <span class="count">{{ text().length }} / {{ maxLength }}</span>
      }
      <button class="send" type="submit" [disabled]="!text().trim() || pending()"
              aria-label="Envoyer" matTooltip="Envoyer" matTooltipPosition="above">
        <mat-icon>arrow_upward</mat-icon>
      </button>
    </form>
  `,
  styles: `
    .box {
      display: flex; align-items: flex-end; gap: 10px;
      padding: 8px 8px 8px 20px;
      background: var(--paper); border: 1px solid var(--line-strong); border-radius: 26px;
      box-shadow: var(--shadow-soft);
      transition: border-color 0.25s, box-shadow 0.25s;
    }
    .box:focus-within {
      border-color: var(--gold);
      box-shadow: 0 0 0 4px rgba(201, 162, 74, 0.18), var(--shadow-soft);
    }
    textarea {
      flex: 1; min-height: 44px; max-height: 168px; padding: 11px 0; resize: none;
      border: 0; outline: 0; background: transparent;
      font: inherit; font-size: 1rem; line-height: 1.5; color: var(--ink);
    }
    textarea::placeholder { color: #9a878b; }
    .count { align-self: center; font-size: 0.72rem; color: var(--ink-soft); white-space: nowrap; }
    .send {
      flex: none; width: 44px; height: 44px; border: 0; border-radius: 50%; cursor: pointer;
      display: grid; place-items: center; color: var(--ivory);
      background: linear-gradient(135deg, var(--burgundy), var(--burgundy-deep));
      box-shadow: 0 8px 18px -8px rgba(107, 30, 46, 0.8);
      transition: transform 0.2s var(--ease-out), opacity 0.2s, background 0.3s;
    }
    .send:not(:disabled):hover { transform: translateY(-2px) rotate(-8deg); }
    .send:not(:disabled):hover mat-icon { color: var(--gold-light); }
    .send:disabled { cursor: default; opacity: 0.35; box-shadow: none; }
  `,
})
export class Composer {
  readonly pending = input(false);
  readonly placeholder = input('Posez votre question…');
  readonly send = output<string>();

  protected readonly maxLength = MAX_LENGTH;
  protected readonly text = signal('');
  private readonly field = viewChild.required<ElementRef<HTMLTextAreaElement>>('field');

  focus(): void {
    this.field().nativeElement.focus();
  }

  protected onInput(field: HTMLTextAreaElement): void {
    this.text.set(field.value);
    this.resize();
  }

  protected onEnter(event: Event): void {
    if ((event as KeyboardEvent).shiftKey || (event as KeyboardEvent).isComposing) return;
    this.submit(event);
  }

  protected submit(event: Event): void {
    event.preventDefault();
    const text = this.text().trim();
    if (!text || this.pending()) return;
    this.send.emit(text);
    this.text.set('');
    this.field().nativeElement.value = '';      // vidé tout de suite pour recalculer la hauteur
    this.resize();
  }

  private resize(): void {
    const element = this.field().nativeElement;
    element.style.height = 'auto';
    element.style.height = `${Math.min(element.scrollHeight, 168)}px`;
  }
}
