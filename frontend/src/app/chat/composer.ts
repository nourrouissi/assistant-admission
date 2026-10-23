import { TextFieldModule } from '@angular/cdk/text-field';
import { ChangeDetectionStrategy, Component, ElementRef, inject, input, output, signal, viewChild } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatTooltipModule } from '@angular/material/tooltip';

import { I18n } from '../core/i18n';

const MAX_LENGTH = 2000;

/** Zone de saisie (champ Material) : Entrée pour envoyer, Maj + Entrée pour aller à la ligne. */
@Component({
  selector: 'app-composer',
  imports: [TextFieldModule, MatButtonModule, MatFormFieldModule, MatIconModule, MatInputModule, MatTooltipModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <form (submit)="submit($event)">
      <mat-form-field appearance="outline" class="field" subscriptSizing="dynamic">
        <mat-icon matPrefix class="prefix">school</mat-icon>
        <textarea #field matInput cdkTextareaAutosize cdkAutosizeMinRows="1" cdkAutosizeMaxRows="6"
                  [attr.aria-label]="i18n.t('Votre message')" [maxLength]="maxLength" [placeholder]="placeholder()"
                  [value]="text()" (input)="text.set(field.value)" (keydown.enter)="onEnter($event)"></textarea>
        <button matSuffix mat-flat-button class="send" type="submit" [disabled]="!text().trim() || pending()"
                [attr.aria-label]="i18n.t('Envoyer')" [matTooltip]="i18n.t('Envoyer (Entrée)')" matTooltipPosition="above">
          <mat-icon>send</mat-icon>
        </button>
        @if (text().length > maxLength - 200) {
          <mat-hint align="end">{{ text().length }} / {{ maxLength }}</mat-hint>
        }
      </mat-form-field>
    </form>
  `,
  styleUrl: './composer.scss',
})
export class Composer {
  readonly pending = input(false);
  readonly placeholder = input('Posez votre question…');
  readonly send = output<string>();

  protected readonly i18n = inject(I18n);

  protected readonly maxLength = MAX_LENGTH;
  protected readonly text = signal('');
  private readonly field = viewChild.required<ElementRef<HTMLTextAreaElement>>('field');

  focus(): void {
    this.field().nativeElement.focus();
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
    this.field().nativeElement.value = '';
  }
}
