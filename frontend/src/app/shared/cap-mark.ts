import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/**
 * Toque de diplômé, signature visuelle de Cap Diplôme.
 * Couleur de la toque : currentColor ; couleur du gland : --tassel (rouge par défaut).
 * `swing` : le gland se balance (réponse en cours).
 */
@Component({
  selector: 'app-cap-mark',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <svg viewBox="0 0 64 64" [attr.width]="size()" [attr.height]="size()" aria-hidden="true" [class.swing]="swing()">
      <path class="crown" d="M17 29v9.5c0 4.7 6.7 8.5 15 8.5s15-3.8 15-8.5V29l-15 6.6z" />
      <path class="board" d="M32 12 59 24 32 36 5 24Z" />
      <circle class="button" cx="32" cy="24" r="2" />
      <g class="tassel">
        <path d="M32 24 51 28.5V42" fill="none" stroke-width="2.2" stroke-linecap="round" />
        <path d="M48.6 41.5h4.8l-.9 8.5h-3z" />
      </g>
    </svg>
  `,
  styles: `
    :host { display: inline-flex; line-height: 0; }
    svg { overflow: visible; }
    .board { fill: currentColor; }
    .crown { fill: currentColor; opacity: 0.82; }
    .button { fill: var(--tassel, #e2231a); }
    .tassel { fill: var(--tassel, #e2231a); stroke: var(--tassel, #e2231a); transform-origin: 51px 28.5px; }
    .swing .tassel { animation: swing 1.1s ease-in-out infinite alternate; }
    @keyframes swing { from { transform: rotate(14deg); } to { transform: rotate(-14deg); } }
  `,
})
export class CapMark {
  readonly size = input(32);
  readonly swing = input(false);
}
