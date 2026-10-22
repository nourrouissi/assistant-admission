import { Pipe, PipeTransform } from '@angular/core';

import { tidy } from './format';

/** Texte du fichier des formations sans ses fautes de frappe (voir tidy()). */
@Pipe({ name: 'tidy' })
export class TidyPipe implements PipeTransform {
  transform(value: string | null | undefined): string {
    return value ? tidy(value) : '';
  }
}
