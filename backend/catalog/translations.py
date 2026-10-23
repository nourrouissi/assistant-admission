"""
Traductions des données du catalogue (diplômes, spécialités, critères) pour l'anglais et l'arabe.

La base garde le texte officiel des écoles : la recherche et l'éligibilité travaillent toujours
sur le français. Seul l'affichage est traduit, et uniquement quand le prospect a choisi une
autre langue (en français, `tr()` rend le texte d'origine, à l'identique).
Les noms d'écoles (« IMSET SOUSSE ») sont des noms propres : ils ne sont pas traduits.
"""

from config.i18n import add_translations

DIPLOMAS = {
    "Bachelor": {"en": "Bachelor", "ar": "بكالوريوس"},
    "Brevet de Technicien Professionnel": {
        "en": "Professional Technician Certificate (BTP)", "ar": "شهادة تقني مهني (BTP)",
    },
    "Brevet de Technicien Supérieur": {"en": "Higher Technician Certificate (BTS)", "ar": "شهادة تقني سامٍ (BTS)"},
    "Certificat d'Aptitude Professionnelle": {
        "en": "Certificate of Professional Competence (CAP)", "ar": "شهادة الكفاءة المهنية (CAP)",
    },
    "Concepteur en architecture informatique": {
        "en": "Computer Architecture Designer", "ar": "مصمم في هندسة الأنظمة المعلوماتية",
    },
    "Diplome de LICENCE": {"en": "Bachelor's degree (Licence)", "ar": "شهادة الإجازة"},
    "INGENIEUR CNAM": {"en": "CNAM Engineering degree", "ar": "شهادة مهندس CNAM"},
    "Ingénieur": {"en": "Engineering degree", "ar": "شهادة مهندس"},
    "Licence": {"en": "Bachelor's degree (Licence)", "ar": "الإجازة"},
    "Licence Professionnelle": {"en": "Professional bachelor's degree", "ar": "الإجازة المهنية"},
    "SHORT COURSES": {"en": "Short courses", "ar": "دورات قصيرة"},
}

SPECIALTIES = {
    "Agent d'entrepot": {"en": "Warehouse operative", "ar": "عون مخزن"},
    "Agent d'entretien en climatisation": {"en": "Air-conditioning maintenance technician", "ar": "عون صيانة في التكييف"},
    "Analyste programmeur option programmeur mobiles": {
        "en": "Analyst programmer, mobile programming option", "ar": "محلل مبرمج، اختصاص برمجة الهواتف الجوالة",
    },
    "BTS-Analyste programmeur option programmeur mobiles": {
        "en": "BTS – Analyst programmer, mobile programming option",
        "ar": "BTS – محلل مبرمج، اختصاص برمجة الهواتف الجوالة",
    },
    "BTS-Comptabilité et Finances": {"en": "BTS – Accounting and Finance", "ar": "BTS – المحاسبة والمالية"},
    "BTS-Décoration et design d'intérieur": {
        "en": "BTS – Interior decoration and design", "ar": "BTS – الديكور والتصميم الداخلي",
    },
    "BTS_Bioanalyses et Controles": {"en": "BTS – Bioanalysis and testing", "ar": "BTS – التحاليل البيولوجية والمراقبة"},
    "Bioanalyses et Controles": {"en": "Bioanalysis and testing", "ar": "التحاليل البيولوجية والمراقبة"},
    "Biologie et Biotechnologie": {"en": "Biology and biotechnology", "ar": "البيولوجيا والتكنولوجيا الحيوية"},
    "Climatisation": {"en": "Air conditioning", "ar": "التكييف"},
    "Climatisation (cours du soir)": {"en": "Air conditioning (evening classes)", "ar": "التكييف (دروس مسائية)"},
    "Commerce International": {"en": "International trade", "ar": "التجارة الدولية"},
    "Commerce international": {"en": "International trade", "ar": "التجارة الدولية"},
    "Commerce de distribution": {"en": "Retail and distribution", "ar": "تجارة التوزيع"},
    "Commercial de distribution": {"en": "Distribution sales representative", "ar": "مندوب تجاري في التوزيع"},
    "Comptabilité et Finances": {"en": "Accounting and finance", "ar": "المحاسبة والمالية"},
    "Comptable d'Entreprise": {"en": "Company accountant", "ar": "محاسب مؤسسة"},
    "Comptable d'entreprise": {"en": "Company accountant", "ar": "محاسب مؤسسة"},
    "Concepteur en Architecture Informatique": {
        "en": "Computer architecture designer", "ar": "مصمم في هندسة الأنظمة المعلوماتية",
    },
    "Conception et Optimisation des Systèmes Logistiques": {
        "en": "Design and optimisation of logistics systems", "ar": "تصميم وتحسين الأنظمة اللوجستية",
    },
    "Conception et Optimisation des Systèmes Logistiques Industriels": {
        "en": "Design and optimisation of industrial logistics systems", "ar": "تصميم وتحسين الأنظمة اللوجستية الصناعية",
    },
    "Controle qualité dans les industries agroalimentaires": {
        "en": "Quality control in the food industry", "ar": "مراقبة الجودة في الصناعات الغذائية",
    },
    "Décoration d'intérieur": {"en": "Interior decoration", "ar": "الديكور الداخلي"},
    "Décoration et Design d'Intérieur": {"en": "Interior decoration and design", "ar": "الديكور والتصميم الداخلي"},
    "Décoration et design d'intérieur": {"en": "Interior decoration and design", "ar": "الديكور والتصميم الداخلي"},
    "Développement sur Internet": {"en": "Web development", "ar": "تطوير الويب"},
    "Formalités Douanières": {"en": "Customs procedures", "ar": "الإجراءات الديوانية"},
    "Formation cableur automobile Leoni": {"en": "Automotive wiring training (Leoni)", "ar": "تكوين في كوابل السيارات (Leoni)"},
    "Froid et Climatisation": {"en": "Refrigeration and air conditioning", "ar": "التبريد والتكييف"},
    "Froid et Climatisation (Cours du soir)": {
        "en": "Refrigeration and air conditioning (evening classes)", "ar": "التبريد والتكييف (دروس مسائية)",
    },
    "Infographie et publication assisté par ordinateur": {
        "en": "Computer graphics and desktop publishing", "ar": "الغرافيك والنشر المكتبي بالحاسوب",
    },
    "Informatique de Gestion": {"en": "Business computing", "ar": "إعلامية التصرف"},
    "Informatique de gestion": {"en": "Business computing", "ar": "إعلامية التصرف"},
    "Informatique de gestion (cours du soir)": {
        "en": "Business computing (evening classes)", "ar": "إعلامية التصرف (دروس مسائية)",
    },
    "Ingénierie": {"en": "Engineering", "ar": "الهندسة"},
    "Ingénieur en informatique": {"en": "Computer engineering", "ar": "مهندس في الإعلامية"},
    "Licence STS Informatique Parcours Développement web et Logiciel": {
        "en": "Bachelor in Science, Technology and Health – Computer science, web and software development track",
        "ar": "إجازة في العلوم والتكنولوجيا والصحة – إعلامية، مسار تطوير الويب والبرمجيات",
    },
    "Licence en Batiment": {"en": "Bachelor in building and construction", "ar": "إجازة في البناء"},
    "Licence sciences, technologies, santé mention informatique générale": {
        "en": "Bachelor in Science, Technology and Health – General computer science",
        "ar": "إجازة في العلوم والتكنولوجيا والصحة – إعلامية عامة",
    },
    "Logisticien de distribution": {"en": "Distribution logistician", "ar": "مختص لوجستي في التوزيع"},
    "Maintenance Electronique des Systèmes Automatisés": {
        "en": "Electronic maintenance of automated systems", "ar": "الصيانة الإلكترونية للأنظمة الآلية",
    },
    "Maintenance Industrielle": {"en": "Industrial maintenance", "ar": "الصيانة الصناعية"},
    "Maintenance Micro-système Informatique": {
        "en": "Computer micro-systems maintenance", "ar": "صيانة الأنظمة المعلوماتية الدقيقة",
    },
    "Management de Projet et Travaux Publics": {
        "en": "Project management and public works", "ar": "إدارة المشاريع والأشغال العمومية",
    },
    "Montage Vidéo": {"en": "Video editing", "ar": "المونتاج السمعي البصري"},
    "Promotion et Gestion de Ventes de voyage": {
        "en": "Travel sales promotion and management", "ar": "ترويج وتسيير مبيعات الأسفار",
    },
    "Prothèse Dentaire": {"en": "Dental prosthetics", "ar": "تركيب الأسنان"},
    "Préparateur en Laboratoires de Biologie Médicale": {
        "en": "Medical biology laboratory technician", "ar": "مُحضِّر في مخابر البيولوجيا الطبية",
    },
    "Préparateur en Pharmacie": {"en": "Pharmacy technician", "ar": "مُحضِّر في الصيدلة"},
    "RNCP - Niveau II Concepteur en Architecture Informatique": {
        "en": "RNCP Level II – Computer architecture designer", "ar": "RNCP المستوى الثاني – مصمم في هندسة الأنظمة المعلوماتية",
    },
    "Réseaux et Sécurité Informatiques(cours du soir)": {
        "en": "Computer networks and security (evening classes)", "ar": "الشبكات والسلامة المعلوماتية (دروس مسائية)",
    },
    "Réseaux et sécurité Informatiques": {"en": "Computer networks and security", "ar": "الشبكات والسلامة المعلوماتية"},
    "Soutien en Informatique de Gestion": {"en": "Business computing support", "ar": "الدعم في إعلامية التصرف"},
    "Technicien en soutien informatique de gestion": {
        "en": "Business computing support technician", "ar": "تقني في دعم إعلامية التصرف",
    },
    "Vendeur caissier étalagiste": {"en": "Sales assistant, cashier and merchandiser", "ar": "بائع وأمين صندوق ومنسق واجهات"},
}

# Critères officiels (« All » n'est pas traduit ici : l'interface l'affiche comme « aucune exigence »)
CRITERIA = {
    "2ème année secondaire avec succés": {
        "en": "Successful completion of 2nd year of secondary school", "ar": "النجاح في السنة الثانية ثانوي",
    },
    "2ème avec succés ou CAP dans le même secteur": {
        "en": "Successful 2nd year of secondary school, or a CAP in the same field",
        "ar": "النجاح في السنة الثانية ثانوي أو شهادة CAP في نفس الاختصاص",
    },
    "4ème année secondaire": {"en": "4th year of secondary school", "ar": "السنة الرابعة ثانوي"},
    "9ème année accomplie": {"en": "Completed 9th grade", "ar": "إتمام السنة التاسعة أساسي"},
    "Bac+ 2/ BTS": {"en": "Bac+2 / BTS", "ar": "باكالوريا + 2 / BTS"},
    "Bac+2 / BTS": {"en": "Bac+2 / BTS", "ar": "باكالوريا + 2 / BTS"},
    "Licence +1 année d'approfondissement": {
        "en": "Bachelor's degree + 1 year of further study", "ar": "إجازة + سنة تعميق",
    },
    "Licence+1 année d'approfondissement": {
        "en": "Bachelor's degree + 1 year of further study", "ar": "إجازة + سنة تعميق",
    },
    "Licence ou équivalent": {"en": "Bachelor's degree or equivalent", "ar": "إجازة أو ما يعادلها"},
    "bac ou BTP dans le même secteur": {
        "en": "Baccalaureate, or a BTP in the same field", "ar": "باكالوريا أو شهادة BTP في نفس الاختصاص",
    },
    "Tunisienne": {"en": "Tunisian", "ar": "تونسية"},
    "Sciences expérimentales ou Mathèmatique": {
        "en": "Experimental sciences or Mathematics", "ar": "علوم تجريبية أو رياضيات",
    },
    "san bac": {"en": "Without baccalaureate", "ar": "بدون باكالوريا"},
}

# Villes des écoles en arabe : le prospect peut écrire « سوسة » au lieu de « Sousse » (voir services.search_catalog)
CITIES_AR = {"تونس": "Tunis", "سوسة": "Sousse", "صفاقس": "Sfax", "نابل": "Nabeul", "قابس": "Gabes"}

add_translations(DIPLOMAS)
add_translations(SPECIALTIES)
add_translations(CRITERIA)
