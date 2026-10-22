import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/**
 * Soleil signature de Lumen : un anneau et des rayons, dans la couleur du texte (currentColor).
 * `spin` : rotation lente décorative ; `thinking` : rotation rapide et rayons pulsés (réponse en cours).
 */
@Component({
  selector: 'app-sun-mark',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <svg viewBox="0 0 100 100" [attr.width]="size()" [attr.height]="size()" aria-hidden="true"
         [class.spin]="spin()" [class.thinking]="thinking()">
      @if (ring()) {
        <circle class="ring" cx="50" cy="50" r="44" />
      }
      <g class="rays">
        @for (angle of angles; track angle) {
          <polygon points="48.6,12 51.4,12 50.35,40 49.65,40" [attr.transform]="'rotate(' + angle + ' 50 50)'" />
        }
      </g>
      <circle class="core" cx="50" cy="50" r="9" />
    </svg>
  `,
  styles: `
    :host { display: inline-flex; line-height: 0; }
    svg { overflow: visible; }
    .ring { fill: none; stroke: currentColor; stroke-width: 7; }
    .rays, .core { fill: currentColor; }
    .rays { transform-origin: 50px 50px; }
    .spin .rays { animation: turn 60s linear infinite; }
    .thinking .rays { animation: turn 3.2s linear infinite, breathe 1.6s ease-in-out infinite; }
    .thinking .core { animation: breathe 1.6s ease-in-out infinite reverse; }
    @keyframes turn { to { transform: rotate(360deg); } }
    @keyframes breathe { 50% { opacity: 0.45; } }
  `,
})
export class SunMark {
  readonly size = input(40);
  readonly ring = input(true);
  readonly spin = input(false);
  readonly thinking = input(false);

  protected readonly angles = Array.from({ length: 24 }, (_, index) => index * 15);
}
