import { criterion, diplomaShort, formatText } from './format';
import { FormationCard } from './models';

describe('formatText', () => {
  it('turns lines starting with a dash into a list', () => {
    expect(formatText('Pièces :\n- identité ;\n- diplôme.')).toBe(
      '<p>Pièces :</p><ul><li>identité ;</li><li>diplôme.</li></ul>',
    );
  });

  it('never interprets HTML coming from the API', () => {
    expect(formatText('<img src=x onerror=alert(1)>')).toBe('<p>&lt;img src=x onerror=alert(1)&gt;</p>');
  });

  it('makes the admissions e-mail clickable, without the final period', () => {
    expect(formatText('Contact : admissions@test.local.')).toBe(
      '<p>Contact : <a href="mailto:admissions@test.local">admissions@test.local</a>.</p>',
    );
  });

  it('keeps bold text', () => {
    expect(formatText('vos **relevés de notes**')).toBe('<p>vos <strong>relevés de notes</strong></p>');
  });
});

describe('formation card helpers', () => {
  const card = { diploma: 'Brevet de Technicien Supérieur', diploma_type: 'BTS' } as FormationCard;

  it('shows the diploma type in the seal, or the initials of the label when it is unknown', () => {
    expect(diplomaShort(card)).toBe('BTS');
    expect(diplomaShort({ ...card, diploma_type: null })).toBe('BDTS');
  });

  it('translates « All » and keeps any other official criterion as written', () => {
    expect(criterion('All', 'Toutes nationalités')).toBe('Toutes nationalités');
    expect(criterion('san bac', 'Toutes sections')).toBe('san bac');
  });
});
