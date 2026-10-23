import { TestBed } from '@angular/core/testing';

import { I18n, TRANSLATIONS } from './i18n';

const ARABIC = /[؀-ۿ]/;
const placeholders = (text: string) => new Set(text.match(/\{\w+\}/g) ?? []);

describe('I18n', () => {
  let i18n: I18n;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({});
    i18n = TestBed.inject(I18n);
  });

  it('keeps French by default and returns the French text unchanged', () => {
    expect(i18n.lang()).toBe('fr');
    expect(i18n.t("S'inscrire")).toBe("S'inscrire");
    expect(i18n.t('Statut : {status}', { status: 'Nouvelle' })).toBe('Statut : Nouvelle');
  });

  it('translates into English and Arabic, and falls back to French for unknown texts', () => {
    i18n.lang.set('en');
    expect(i18n.t("S'inscrire")).toBe('Apply');
    expect(i18n.t('Licence en Bâtiment')).toBe('Licence en Bâtiment');   // nom officiel, non traduit
    i18n.lang.set('ar');
    expect(i18n.t('Statut : {status}', { status: i18n.t('Nouvelle') })).toBe('الحالة: جديد');
  });

  it('has an English and an Arabic version of every text, with the same placeholders', () => {
    for (const [french, translation] of Object.entries(TRANSLATIONS)) {
      expect(translation.en, french).toBeTruthy();
      expect(translation.ar, french).toMatch(ARABIC);
      expect(placeholders(translation.en), french).toEqual(placeholders(french));
      expect(placeholders(translation.ar), french).toEqual(placeholders(french));
    }
  });

  it('writes Arabic from right to left', () => {
    i18n.lang.set('ar');
    TestBed.tick();
    expect(document.documentElement.dir).toBe('rtl');
    expect(document.documentElement.lang).toBe('ar');
    i18n.lang.set('fr');
    TestBed.tick();
    expect(document.documentElement.dir).toBe('ltr');
  });
});
