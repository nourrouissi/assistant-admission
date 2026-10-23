import { FormationCard } from './models';

/**
 * Mise en forme légère des réponses : paragraphes, listes, **gras** et adresses e-mail cliquables.
 * Le texte est échappé avant toute transformation : aucun HTML venant de l'API n'est interprété.
 */
export function formatText(text: string): string {
  let html = '';
  let list: 'ul' | 'ol' | null = null;
  let paragraph: string[] = [];

  const flushParagraph = () => {
    if (paragraph.length) html += `<p>${paragraph.map(inline).join('<br>')}</p>`;
    paragraph = [];
  };
  const closeList = () => {
    if (list) html += `</${list}>`;
    list = null;
  };

  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    const bullet = line.match(/^[-•*]\s+(.*)$/);
    const numbered = line.match(/^\d+[.)]\s+(.*)$/);
    const item = bullet ?? numbered;
    if (item) {
      flushParagraph();
      const kind = bullet ? 'ul' : 'ol';
      if (list !== kind) {
        closeList();
        html += `<${kind}>`;
        list = kind;
      }
      html += `<li>${inline(item[1])}</li>`;
      continue;
    }
    closeList();
    if (line) paragraph.push(line);
    else flushParagraph();
  }
  flushParagraph();
  closeList();
  return html;
}

function escape(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function inline(text: string): string {
  return escape(text)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/([\w.+-]+@[\w-]+(?:\.[\w-]+)+)/g, '<a href="mailto:$1">$1</a>');
}

const DIPLOMA_SHORT: Record<string, string> = {
  CAP: 'CAP',
  BTP: 'BTP',
  BTS: 'BTS',
  LICENCE: 'LIC',
  LICENCE_PRO: 'L·PRO',
  BACHELOR: 'BACH',
  INGENIEUR: 'ING',
  TITRE_RNCP: 'RNCP',
  SHORT_COURSE: 'COURT',
};

/** Sigles français remplacés en anglais (CAP, BTS… sont des sigles officiels, gardés dans toutes les langues). */
const DIPLOMA_SHORT_EN: Record<string, string> = { INGENIEUR: 'ENG', SHORT_COURSE: 'SHORT' };

/** Sigle du diplôme, affiché dans le sceau de la carte. */
export function diplomaShort(card: FormationCard, lang = 'fr'): string {
  if (card.diploma_type && lang === 'en' && DIPLOMA_SHORT_EN[card.diploma_type]) return DIPLOMA_SHORT_EN[card.diploma_type];
  if (card.diploma_type) return DIPLOMA_SHORT[card.diploma_type] ?? card.diploma_type;
  return card.diploma.split(/\s+/).map((word) => word[0] ?? '').join('').slice(0, 4).toUpperCase();
}

/**
 * Fautes de frappe du fichier des formations, corrigées à l'affichage seulement :
 * la base garde le texte officiel, et le calcul d'éligibilité n'en dépend pas.
 */
const TYPOS: [RegExp, string][] = [
  [/\bsan bac\b/gi, 'sans bac'],
  [/\bsuccés\b/gi, 'succès'],
  [/\bBac\+ 2\/ BTS\b/g, 'Bac+2 / BTS'],
  [/\bMathématique\b/g, 'Mathématiques'],
  [/\bDiplome\b/g, 'Diplôme'],
  [/\bdiplôme de LICENCE\b/gi, 'Diplôme de Licence'],
  [/\bINGENIEUR\b/g, 'Ingénieur'],
  [/\bBatiment\b/g, 'Bâtiment'],
  [/\bControles\b/g, 'Contrôles'],
  [/\bControle\b/g, 'Contrôle'],
  [/\bpublication assisté\b/g, 'publication assistée'],
];

/** Texte du fichier des formations, sans ses fautes de frappe ni espaces en trop, avec une majuscule initiale. */
export function tidy(value: string): string {
  const text = TYPOS.reduce((result, [typo, fix]) => result.replace(typo, fix), value.trim().replace(/\s+/g, ' '));
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Critère d'une formation : « All » dans le fichier signifie « aucune exigence ». */
export function criterion(value: string, whenAll: string): string {
  return value.trim().toLowerCase() === 'all' ? whenAll : tidy(value);
}

export const ELIGIBILITY_LABELS = {
  compatible: { label: 'Critères remplis', icon: 'verified' },
  a_confirmer: { label: 'À confirmer', icon: 'hourglass_top' },
  incomplet: { label: 'Infos manquantes', icon: 'help' },
  non_compatible: { label: 'Critère non rempli', icon: 'do_not_disturb_on' },
} as const;
