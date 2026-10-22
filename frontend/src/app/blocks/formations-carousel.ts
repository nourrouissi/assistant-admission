import { ChangeDetectionStrategy, Component, ElementRef, computed, input, output, viewChild } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

import { FormationCard as Card } from '../core/models';
import { FormationCard } from './formation-card';

/** Cartes de formations, défilant horizontalement, qui apparaissent l'une après l'autre. */
@Component({
  selector: 'app-formations-carousel',
  imports: [FormationCard, MatButtonModule, MatIconModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="carousel" [attr.aria-label]="title()">
      <header>
        <h4><span class="count">{{ items().length }}</span>{{ title() }}</h4>
        @if (items().length > 1) {
          <div class="nav">
            <button mat-icon-button type="button" aria-label="Formations précédentes" (click)="scroll(-1)">
              <mat-icon>chevron_left</mat-icon>
            </button>
            <button mat-icon-button type="button" aria-label="Formations suivantes" (click)="scroll(1)">
              <mat-icon>chevron_right</mat-icon>
            </button>
          </div>
        }
      </header>
      <div class="track" #track>
        @for (card of items(); track card.id; let index = $index) {
          <app-formation-card [card]="card" [disabled]="disabled()" (register)="register.emit($event)"
                              [style.animation-delay.ms]="Math.min(index, 8) * 90" />
        }
      </div>
    </section>
  `,
  styles: `
    :host { display: block; min-width: 0; }
    header { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin: 0 2px 10px; }
    h4 { display: flex; align-items: center; gap: 10px; font-size: 1.08rem; color: var(--gown); }
    .count {
      display: grid; place-items: center; min-width: 28px; height: 28px; padding: 0 8px; border-radius: 999px;
      font-family: var(--font-text); font-size: 0.8rem; font-weight: 700;
      color: #ffffff; background: linear-gradient(135deg, var(--red), var(--burgundy));
      box-shadow: 0 6px 14px -6px rgba(226, 35, 26, 0.8);
    }
    .nav { display: flex; gap: 2px; color: var(--gown); }
    .track {
      display: flex; gap: 16px; overflow-x: auto; scroll-snap-type: x mandatory; scroll-behavior: smooth;
      padding: 8px 4px 20px; margin: 0 -4px;
      mask-image: linear-gradient(to right, transparent, #000 10px, #000 calc(100% - 28px), transparent);
    }
    app-formation-card {
      flex: 0 0 292px; scroll-snap-align: start;
      animation: enter 0.6s var(--ease-out) both;
    }
    @keyframes enter { from { opacity: 0; transform: translateY(18px) scale(0.97); } }
    @media (max-width: 520px) { app-formation-card { flex-basis: 84%; } .nav { display: none; } }
  `,
})
export class FormationsCarousel {
  readonly items = input.required<Card[]>();
  readonly disabled = input(false);
  readonly register = output<Card>();

  protected readonly Math = Math;
  protected readonly title = computed(() => {
    const evaluated = this.items().some((card) => card.eligibility);
    const plural = this.items().length > 1 ? 's' : '';
    return evaluated ? `formation${plural} vérifiée${plural} pour votre profil` : `formation${plural} pour vous`;
  });

  private readonly track = viewChild.required<ElementRef<HTMLElement>>('track');

  protected scroll(direction: 1 | -1): void {
    const element = this.track().nativeElement;
    element.scrollBy({ left: direction * Math.max(element.clientWidth * 0.8, 300), behavior: 'smooth' });
  }
}
