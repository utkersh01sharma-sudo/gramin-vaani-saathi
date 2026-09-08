"""Slot fillers and per-language surface forms used by the dataset generator.

Rural speech is heavily code-mixed: a Hindi speaker says "balance" in English and
"paise" in Hindi in the same sentence, and often types Hindi in Latin script.
The generator therefore emits native-script, transliterated, and code-mixed
variants so the model sees all three at training time.
"""

PERSONS = {
    "hi": ["रमेश", "सीता", "मोहन", "गीता", "सुरेश", "कमला", "राजू", "लक्ष्मी", "अनिल", "शांति"],
    "en": ["Ramesh", "Sita", "Mohan", "Geeta", "Suresh", "Kamala", "Raju", "Lakshmi"],
    "ta": ["ரமேஷ்", "சீதா", "முருகன்", "கீதா", "செல்வம்", "கமலா", "ராஜு", "லட்சுமி"],
    "te": ["రమేష్", "సీత", "మోహన్", "గీత", "సురేష్", "కమల", "రాజు", "లక్ష్మి"],
}

# Latin-script renderings, for transliterated input.
PERSONS_LATIN = ["Ramesh", "Sita", "Mohan", "Geeta", "Suresh", "Kamala", "Raju", "Lakshmi"]

AMOUNTS_DIGIT = ["50", "100", "200", "250", "500", "1000", "1500", "2000", "5000"]

AMOUNTS_WORD = {
    "hi": ["पचास", "सौ", "दो सौ", "पांच सौ", "हजार", "दो हजार", "पांच हजार"],
    "en": ["fifty", "hundred", "two hundred", "five hundred", "thousand", "two thousand"],
    "ta": ["ஐம்பது", "நூறு", "இருநூறு", "ஐநூறு", "ஆயிரம்", "இரண்டாயிரம்"],
    "te": ["యాభై", "వంద", "రెండు వందలు", "ఐదు వందలు", "వెయ్యి", "రెండు వేలు"],
}

AMOUNTS_LATIN_WORD = ["pachas", "sau", "do sau", "paanch sau", "hazaar", "do hazaar"]

TOPICS = {
    "hi": ["यूपीआई", "बचत", "ब्याज", "लोन", "बीमा", "पासबुक", "एटीएम", "धोखाधड़ी", "बजट"],
    "en": ["UPI", "savings", "interest", "loan", "insurance", "passbook", "ATM", "fraud", "budget"],
    "ta": ["யுபிஐ", "சேமிப்பு", "வட்டி", "கடன்", "காப்பீடு", "பாஸ்புக்", "மோசடி"],
    "te": ["యూపీఐ", "పొదుపు", "వడ్డీ", "రుణం", "బీమా", "పాస్‌బుక్", "మోసం"],
}

SCHEMES = {
    "hi": ["पीएम किसान", "मुद्रा लोन", "जन धन", "अटल पेंशन", "उज्ज्वला", "आवास योजना", "सुकन्या समृद्धि"],
    "en": ["PM Kisan", "Mudra loan", "Jan Dhan", "Atal Pension", "Ujjwala", "housing scheme"],
    "ta": ["பிஎம் கிசான்", "முத்ரா கடன்", "ஜன் தன்", "அடல் ஓய்வூதியம்", "உஜ்வாலா"],
    "te": ["పీఎం కిసాన్", "ముద్ర రుణం", "జన్ ధన్", "అటల్ పెన్షన్", "ఉజ్వల"],
}

LANGUAGE_NAMES = {
    "hi": ["हिंदी", "हिन्दी"],
    "en": ["English", "angrezi", "अंग्रेजी"],
    "ta": ["தமிழ்", "Tamil", "तमिल"],
    "te": ["తెలుగు", "Telugu", "तेलुगु"],
}
