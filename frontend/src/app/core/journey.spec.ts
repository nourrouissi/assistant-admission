import { journeyFrom } from './journey';
import { Block, Entry, FormationCard } from './models';

const card = { id: 1 } as FormationCard;
const assistant = (...blocks: Block[]): Entry => ({ id: crypto.randomUUID(), role: 'assistant', blocks });
const states = (entries: Entry[], stage: 'collect' | 'summary' | null = null) =>
  journeyFrom(entries, stage).map((step) => step.state);

describe('journeyFrom', () => {
  it('starts on « Découvrir »', () => {
    expect(states([])).toEqual(['active', 'todo', 'todo']);
  });

  it('moves to « Vérifier » once eligibility has been checked on a card', () => {
    const checked = { ...card, eligibility: { status: 'compatible', missing: [], reasons: [], message: '' } } as FormationCard;
    expect(states([assistant({ type: 'formations', items: [card] })])).toEqual(['active', 'todo', 'todo']);
    expect(states([assistant({ type: 'formations', items: [checked] })])).toEqual(['done', 'active', 'todo']);
  });

  it('moves to « Candidater » while a registration is in progress, whatever the texts say', () => {
    expect(states([], 'collect')).toEqual(['done', 'done', 'active']);
    expect(states([], 'summary')).toEqual(['done', 'done', 'active']);
  });

  it('completes the journey only when the application has been created', () => {
    expect(states([assistant({ type: 'registration_result', outcome: 'duplicate' })])).toEqual(['active', 'todo', 'todo']);
    expect(states([assistant({ type: 'registration_result', outcome: 'created' })])).toEqual(['done', 'done', 'done']);
  });
});
