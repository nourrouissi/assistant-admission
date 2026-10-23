import { DOCUMENT } from '@angular/common';
import { Injectable, effect, inject, signal } from '@angular/core';

/**
 * Langue de l'interface : français (par défaut), anglais, arabe (de droite à gauche).
 *
 * Le texte français reste la référence, écrit tel quel dans les composants : t(texte)
 * le renvoie inchangé en français, sa traduction sinon. Les noms officiels des
 * formations et les critères des écoles ne sont pas traduits (données de l'établissement).
 */
export type Lang = 'fr' | 'en' | 'ar';

export const LANGUAGES: { code: Lang; label: string; name: string }[] = [
  { code: 'fr', label: 'FR', name: 'Français' },
  { code: 'en', label: 'EN', name: 'English' },
  { code: 'ar', label: 'ع', name: 'العربية' },
];

const STORAGE_KEY = 'cap-diplome.lang';

type Translations = Record<string, { en: string; ar: string }>;

export const TRANSLATIONS: Translations = {
  // --- En-tête, fil de conversation, saisie ---
  'Votre cap vers le diplôme': { en: 'Your path to your diploma', ar: 'طريقك نحو الشهادة' },
  'Nouvelle conversation': { en: 'New conversation', ar: 'محادثة جديدة' },
  'Réponse en cours': { en: 'Answer in progress', ar: 'جارٍ إعداد الرد' },
  'Conversation avec Cap Diplôme': { en: 'Conversation with Cap Diplôme', ar: 'محادثة مع Cap Diplôme' },
  'Cap Diplôme rédige sa réponse': { en: 'Cap Diplôme is writing its answer', ar: 'Cap Diplôme يكتب رده' },
  "Demande d'inscription en cours": { en: 'Application in progress', ar: 'طلب التسجيل قيد الإنجاز' },
  'indiquez votre nom, prénom, e-mail et téléphone.': {
    en: 'give your last name, first name, email and phone number.',
    ar: 'اذكر اسم العائلة والاسم الأول والبريد الإلكتروني ورقم الهاتف.',
  },
  'Dossier en attente': { en: 'Application pending', ar: 'الملف في الانتظار' },
  'confirmez, modifiez ou annulez avec les boutons du dossier.': {
    en: 'confirm, edit or cancel with the buttons of the application.',
    ar: 'أكّد أو عدّل أو ألغِ باستخدام أزرار الملف.',
  },
  Annuler: { en: 'Cancel', ar: 'إلغاء' },
  "Réponses issues des documents officiels des admissions. La décision d'admission appartient toujours à l'équipe des admissions.": {
    en: 'Answers based on the official admissions documents. The admission decision always rests with the admissions team.',
    ar: 'إجابات مستندة إلى الوثائق الرسمية للقبول. قرار القبول يعود دائمًا إلى فريق القبول.',
  },
  'Nom, prénom, e-mail, téléphone…': { en: 'Last name, first name, email, phone…', ar: 'اسم العائلة، الاسم الأول، البريد الإلكتروني، الهاتف…' },
  'Posez votre question…': { en: 'Ask your question…', ar: 'اطرح سؤالك…' },
  'Votre message': { en: 'Your message', ar: 'رسالتك' },
  Envoyer: { en: 'Send', ar: 'إرسال' },
  'Envoyer (Entrée)': { en: 'Send (Enter)', ar: 'إرسال (Enter)' },
  'Cap Diplôme :': { en: 'Cap Diplôme:', ar: 'رد Cap Diplôme:' },
  Langue: { en: 'Language', ar: 'اللغة' },

  // --- Accueil ---
  "Assistant d'admission": { en: 'Admissions assistant', ar: 'مساعد القبول' },
  'Votre cap vers le': { en: 'Your path to your', ar: 'طريقك نحو' },
  diplôme: { en: 'diploma', ar: 'الشهادة' },
  "Procédure d'admission, choix de la formation, vérification de votre profil et demande d'inscription : je vous accompagne à chaque étape, jusqu'au jour de votre remise de diplôme.": {
    en: 'Admission procedure, choice of program, profile check and application: I guide you at every step, all the way to your graduation day.',
    ar: 'إجراءات القبول، اختيار البرنامج، التحقق من ملفك وطلب التسجيل: أرافقك في كل خطوة حتى يوم تسلّم شهادتك.',
  },
  'Étape 1': { en: 'Step 1', ar: 'الخطوة 1' },
  'Étape 2': { en: 'Step 2', ar: 'الخطوة 2' },
  'Étape 3': { en: 'Step 3', ar: 'الخطوة 3' },
  "Comprendre l'admission": { en: 'Understand admission', ar: 'فهم القبول' },
  'Étapes, pièces justificatives, dates limites et frais.': {
    en: 'Steps, supporting documents, deadlines and fees.',
    ar: 'المراحل، الوثائق المطلوبة، الآجال والرسوم.',
  },
  'Quels documents dois-je fournir pour déposer une candidature ?': {
    en: 'Which documents do I need to submit an application?',
    ar: 'ما هي الوثائق التي يجب تقديمها لإيداع طلب الترشح؟',
  },
  'Trouver ma formation': { en: 'Find my program', ar: 'إيجاد برنامجي' },
  'Diplômes, spécialités et écoles, selon votre profil.': {
    en: 'Diplomas, specialties and schools, based on your profile.',
    ar: 'الشهادات والاختصاصات والمدارس حسب ملفك.',
  },
  'Quelles spécialités proposez-vous en informatique ?': {
    en: 'Which computer science specialties do you offer?',
    ar: 'ما هي الاختصاصات التي تقترحونها في الإعلامية؟',
  },
  'Déposer ma candidature': { en: 'Submit my application', ar: 'إيداع ترشحي' },
  "Votre demande d'inscription, pas à pas, jusqu'à la confirmation.": {
    en: 'Your application, step by step, until confirmation.',
    ar: 'طلب تسجيلك، خطوة بخطوة، حتى التأكيد.',
  },
  "Je souhaite déposer une demande d'inscription.": {
    en: 'I would like to submit an application.',
    ar: 'أرغب في تقديم طلب تسجيل.',
  },
  'Essayez aussi': { en: 'Also try', ar: 'جرّب أيضًا' },
  "J'ai un bac informatique, quelles spécialités me correspondent ?": {
    en: 'I have a computer science baccalaureate, which specialties suit me?',
    ar: 'لدي بكالوريا إعلامية، ما هي الاختصاصات المناسبة لي؟',
  },
  'Quelles formations proposez-vous à Sousse ?': {
    en: 'Which programs do you offer in Sousse?',
    ar: 'ما هي البرامج التي تقترحونها في سوسة؟',
  },
  "Quelles sont les étapes de la procédure d'admission ?": {
    en: 'What are the steps of the admission procedure?',
    ar: 'ما هي مراحل إجراءات القبول؟',
  },

  // --- Parcours ---
  'Votre parcours': { en: 'Your journey', ar: 'مسارك' },
  Découvrir: { en: 'Discover', ar: 'اكتشف' },
  Vérifier: { en: 'Check', ar: 'تحقّق' },
  Candidater: { en: 'Apply', ar: 'ترشّح' },
  Diplôme: { en: 'Diploma', ar: 'الشهادة' },
  '(terminée)': { en: '(done)', ar: '(منتهية)' },
  '(en cours)': { en: '(in progress)', ar: '(جارية)' },
  '(à venir)': { en: '(upcoming)', ar: '(قادمة)' },

  // --- Cartes de formations ---
  'formation pour vous': { en: 'program for you', ar: 'برنامج لك' },
  'formations pour vous': { en: 'programs for you', ar: 'برامج لك' },
  'formation vérifiée pour votre profil': { en: 'program checked for your profile', ar: 'برنامج تم التحقق منه لملفك' },
  'formations vérifiées pour votre profil': { en: 'programs checked for your profile', ar: 'برامج تم التحقق منها لملفك' },
  'Formations précédentes': { en: 'Previous programs', ar: 'البرامج السابقة' },
  'Formations suivantes': { en: 'Next programs', ar: 'البرامج التالية' },
  Niveau: { en: 'Level', ar: 'المستوى' },
  Nationalité: { en: 'Nationality', ar: 'الجنسية' },
  Bac: { en: 'Baccalaureate', ar: 'البكالوريا' },
  'Tous niveaux': { en: 'All levels', ar: 'كل المستويات' },
  'Toutes nationalités': { en: 'All nationalities', ar: 'كل الجنسيات' },
  'Toutes sections': { en: 'All tracks', ar: 'كل الشعب' },
  "Critères en cours de vérification par l'équipe des admissions": {
    en: 'Criteria being checked by the admissions team',
    ar: 'الشروط قيد التحقق من قبل فريق القبول',
  },
  "S'inscrire": { en: 'Apply', ar: 'سجّل' },
  'Critères remplis': { en: 'Criteria met', ar: 'الشروط مستوفاة' },
  'À confirmer': { en: 'To be confirmed', ar: 'يحتاج إلى تأكيد' },
  'Infos manquantes': { en: 'Missing information', ar: 'معلومات ناقصة' },
  'Critère non rempli': { en: 'Criterion not met', ar: 'شرط غير مستوفى' },

  // --- Récapitulatif ---
  "Récapitulatif de votre demande d'inscription": { en: 'Summary of your application', ar: 'ملخص طلب تسجيلك' },
  'Dossier de candidature': { en: 'Application file', ar: 'ملف الترشح' },
  'Récapitulatif de votre demande': { en: 'Summary of your application', ar: 'ملخص طلبك' },
  'À vérifier': { en: 'To check', ar: 'للتحقق' },
  'Formation demandée': { en: 'Requested program', ar: 'البرنامج المطلوب' },
  Candidat: { en: 'Applicant', ar: 'المترشح' },
  Nom: { en: 'Last name', ar: 'اسم العائلة' },
  Prénom: { en: 'First name', ar: 'الاسم الأول' },
  'E-mail': { en: 'Email', ar: 'البريد الإلكتروني' },
  Téléphone: { en: 'Phone', ar: 'الهاتف' },
  "Vérifiez vos informations : la demande n'est enregistrée qu'après votre confirmation.": {
    en: 'Check your details: the application is only saved after your confirmation.',
    ar: 'تحقق من معلوماتك: لا يتم تسجيل الطلب إلا بعد تأكيدك.',
  },
  'Confirmer ma demande': { en: 'Confirm my application', ar: 'تأكيد طلبي' },
  Modifier: { en: 'Edit', ar: 'تعديل' },
  "Ce récapitulatif n'est plus en attente.": { en: 'This summary is no longer pending.', ar: 'لم يعد هذا الملخص في الانتظار.' },

  // --- Issue de l'inscription ---
  "Demande d'inscription transmise": { en: 'Application submitted', ar: 'تم إرسال طلب التسجيل' },
  'Première étape franchie': { en: 'First step completed', ar: 'تم اجتياز الخطوة الأولى' },
  'Votre demande est transmise': { en: 'Your application has been sent', ar: 'تم إرسال طلبك' },
  'Statut : {status}': { en: 'Status: {status}', ar: 'الحالة: {status}' },
  Nouvelle: { en: 'New', ar: 'جديد' },
  "Votre demande va être étudiée par l'équipe des admissions, à qui appartient la décision finale.": {
    en: 'Your application will be reviewed by the admissions team, who make the final decision.',
    ar: 'سيدرس فريق القبول طلبك، وله القرار النهائي.',
  },
  'Demande déjà existante': { en: 'Application already exists', ar: 'الطلب موجود مسبقًا' },
  'Formation indisponible': { en: 'Program unavailable', ar: 'البرنامج غير متاح' },
  'Aucune donnée enregistrée': { en: 'No data saved', ar: 'لم يتم حفظ أي بيانات' },

  // --- Messages du prospect envoyés par les boutons ---
  'Je confirme ma demande.': { en: 'I confirm my application.', ar: 'أؤكد طلبي.' },
  'Je souhaite modifier mes informations.': { en: 'I would like to edit my details.', ar: 'أرغب في تعديل معلوماتي.' },
  "J'annule ma demande.": { en: 'I cancel my application.', ar: 'ألغي طلبي.' },
  "Je souhaite m'inscrire à « {specialty} » ({school}).": {
    en: 'I would like to apply to “{specialty}” ({school}).',
    ar: 'أرغب في التسجيل في «{specialty}» ({school}).',
  },

  // --- Erreurs ---
  'Vous avez envoyé beaucoup de messages en peu de temps. Merci de patienter une minute avant de réessayer.': {
    en: 'You have sent many messages in a short time. Please wait a minute before trying again.',
    ar: 'لقد أرسلت رسائل كثيرة في وقت قصير. يُرجى الانتظار دقيقة قبل المحاولة مرة أخرى.',
  },
  'Le serveur ne répond pas. Vérifiez votre connexion, puis réessayez.': {
    en: 'The server is not responding. Check your connection, then try again.',
    ar: 'الخادم لا يستجيب. تحقق من اتصالك ثم أعد المحاولة.',
  },
  "Votre message n'a pas pu être traité. Merci de le reformuler.": {
    en: 'Your message could not be processed. Please rephrase it.',
    ar: 'تعذّرت معالجة رسالتك. يُرجى إعادة صياغتها.',
  },
  'Une erreur est survenue. Merci de réessayer dans un instant.': {
    en: 'An error occurred. Please try again in a moment.',
    ar: 'حدث خطأ. يُرجى المحاولة بعد لحظات.',
  },
};

function restore(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved === 'en' || saved === 'ar' ? saved : 'fr';
  } catch {
    return 'fr';
  }
}

@Injectable({ providedIn: 'root' })
export class I18n {
  private readonly document = inject(DOCUMENT);

  readonly lang = signal<Lang>(restore());

  constructor() {
    // Langue et sens d'écriture de la page (l'arabe s'écrit de droite à gauche)
    effect(() => {
      const lang = this.lang();
      this.document.documentElement.lang = lang;
      this.document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
      try {
        if (lang === 'fr') localStorage.removeItem(STORAGE_KEY);
        else localStorage.setItem(STORAGE_KEY, lang);
      } catch {
        // Stockage indisponible : la langue reste choisie pour cette visite
      }
    });
  }

  /** Texte dans la langue choisie ; le français est renvoyé tel quel. `{nom}` est remplacé par params.nom. */
  t(text: string, params: Record<string, string | number> = {}): string {
    const lang = this.lang();
    const template = lang === 'fr' ? text : (TRANSLATIONS[text]?.[lang] ?? text);
    return template.replace(/\{(\w+)\}/g, (match, name: string) => (name in params ? String(params[name]) : match));
  }

  /** Citation avec les guillemets de la langue (« … » ou “…”). */
  quote(text: string): string {
    return this.lang() === 'en' ? `“${text}”` : `« ${text} »`;
  }
}
