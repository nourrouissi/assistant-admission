/**
 * Contrat de l'API POST /api/chat/ (voir backend/chatbot/views.py).
 * L'interface affiche les blocs tels quels : elle n'interprète jamais les textes.
 */

export type EligibilityStatus = 'compatible' | 'a_confirmer' | 'incomplet' | 'non_compatible';

export interface Eligibility {
  status: EligibilityStatus;
  missing: string[];
  reasons: string[];
  message: string;
}

/** Carte d'une formation : diplôme, spécialité, école et critères d'éligibilité. */
export interface FormationCard {
  id: number;
  diploma: string;
  diploma_type: string | null;
  specialty: string;
  school: string;
  city: string;
  criteria: { level: string; nationality: string; bac: string };
  criteria_under_review: boolean;
  eligibility?: Eligibility;
}

export interface Applicant {
  last_name: string;
  first_name: string;
  email: string;
  phone: string;
}

export type SummaryAction = 'confirm' | 'modify' | 'cancel';
export type ChatAction = 'register' | SummaryAction;
export type Outcome = 'created' | 'duplicate' | 'unavailable' | 'cancelled';

export interface TextBlock { type: 'text'; text: string; }
export interface FormationsBlock { type: 'formations'; items: FormationCard[]; }
export interface SummaryBlock {
  type: 'registration_summary';
  formation: FormationCard;
  applicant: Applicant;
  actions: SummaryAction[];
}
export interface ResultBlock {
  type: 'registration_result';
  outcome: Outcome;
  status?: string;
  formation?: FormationCard;
}

export type Block = TextBlock | FormationsBlock | SummaryBlock | ResultBlock;

/** Étape de l'inscription en cours : coordonnées demandées, récapitulatif en attente, ou aucune. */
export type RegistrationStage = 'collect' | 'summary' | null;

export interface ChatRequest {
  session_id: string;
  message?: string;
  action?: ChatAction;
  formation_id?: number;
}

export interface ChatResponse {
  session_id: string;
  blocks: Block[];
  registration: RegistrationStage;
}

/** Une entrée du fil de conversation. `action` : message produit par un bouton. */
export interface Entry {
  id: string;
  role: 'user' | 'assistant' | 'notice';
  blocks: Block[];
  action?: boolean;
}
