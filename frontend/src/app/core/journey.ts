import { Entry, RegistrationStage } from './models';

export type StepState = 'done' | 'active' | 'todo';

export interface JourneyStep {
  title: string;
  hint: string;
  icon: string;
  state: StepState;
}

const STEPS = [
  { title: 'Découvrir', hint: 'Procédure et formations', icon: 'explore' },
  { title: 'Vérifier', hint: "Critères d'éligibilité", icon: 'fact_check' },
  { title: 'Candidater', hint: "Demande d'inscription", icon: 'history_edu' },
];

/**
 * Étapes du parcours, déduites des blocs reçus et de l'étape d'inscription
 * transmise par l'API : jamais du texte des messages.
 */
export function journeyFrom(entries: Entry[], stage: RegistrationStage): JourneyStep[] {
  const blocks = entries.filter((entry) => entry.role === 'assistant').flatMap((entry) => entry.blocks);
  const verified = blocks.some(
    (block) => block.type === 'formations' && block.items.some((card) => card.eligibility),
  );
  const submitted = blocks.some((block) => block.type === 'registration_result' && block.outcome === 'created');
  const current = submitted ? STEPS.length : stage !== null ? 2 : verified ? 1 : 0;
  return STEPS.map((step, index) => ({
    ...step,
    state: index < current ? 'done' : index === current ? 'active' : 'todo',
  }));
}
