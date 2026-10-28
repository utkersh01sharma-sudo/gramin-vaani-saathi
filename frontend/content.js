// Static content that does not need the server: the safety tips shown beside
// the scam checker, and the example phrases on the help screen.
//
// Schemes and lessons used to live here as placeholders. They now come from
// the API (apps/schemes/fixtures, apps/literacy/fixtures), where eligibility
// is evaluated and quiz answers are graded.

export const TIPS = [
  {
    id: 'otp', icon: 'noOtp', tone: 'var(--tone-safety)',
    title: { hi: 'ओटीपी कभी मत बताइए', en: 'Never share an OTP', ta: 'ஓடிபியை ஒருபோதும் சொல்லாதீர்கள்', te: 'ఓటీపీ ఎప్పుడూ చెప్పకండి' },
    text: {
      hi: 'कोई भी असली बैंक ओटीपी या पिन नहीं माँगता। जो माँगे, वही ठग है।',
      en: 'No genuine bank ever asks for an OTP or a PIN. Whoever asks is the fraudster.',
      ta: 'உண்மையான வங்கி ஓடிபியோ பின்னோ கேட்காது. கேட்பவரே மோசடிக்காரர்.',
      te: 'నిజమైన బ్యాంకు ఓటీపీ లేదా పిన్ అడగదు. అడిగేవాడే మోసగాడు.',
    },
  },
  {
    id: 'receive', icon: 'arrowIn', tone: 'var(--tone-safety)',
    title: { hi: 'पैसा लेने में पिन नहीं लगता', en: 'Receiving money needs no PIN', ta: 'பணம் பெற பின் தேவையில்லை', te: 'డబ్బు అందుకోవడానికి పిన్ అవసరం లేదు' },
    text: {
      hi: '“पैसा भेजने के लिए पिन डालिए” — यह सबसे आम ठगी है। पिन डालते ही पैसा आपके खाते से जाएगा।',
      en: '“Enter your PIN so I can send you money” is the most common scam there is. Entering a PIN always takes money *out*.',
      ta: '“பணம் அனுப்ப பின் போடுங்கள்” என்பதே மிகவும் பொதுவான மோசடி. பின் போட்டால் பணம் வெளியே போகும்.',
      te: '“డబ్బు పంపడానికి పిన్ వేయండి” — ఇదే అత్యంత సాధారణ మోసం. పిన్ వేస్తే డబ్బు బయటకు పోతుంది.',
    },
  },
  {
    id: 'urgency', icon: 'clock', tone: 'var(--tone-safety)',
    title: { hi: 'जल्दबाज़ी ठगी की निशानी है', en: 'Urgency is the warning sign', ta: 'அவசரமே எச்சரிக்கை அறிகுறி', te: 'తొందర పెట్టడమే ప్రమాద సంకేతం' },
    text: {
      hi: '“दो घंटे में खाता बंद हो जाएगा” जैसे संदेश डराने के लिए होते हैं। रुकिए, फ़ोन काटिए, बैंक जाकर पूछिए।',
      en: 'Messages like “your account closes in two hours” exist to frighten you. Stop, hang up, and ask at the branch.',
      ta: '“இரண்டு மணி நேரத்தில் கணக்கு மூடப்படும்” போன்ற செய்திகள் பயமுறுத்தவே. நிறுத்துங்கள், போனை வையுங்கள், கிளையில் கேளுங்கள்.',
      te: '“రెండు గంటల్లో ఖాతా మూసివేయబడుతుంది” లాంటి సందేశాలు భయపెట్టడానికే. ఆగండి, ఫోన్ పెట్టేయండి, బ్యాంకులో అడగండి.',
    },
  },
  {
    id: 'qr', icon: 'qr', tone: 'var(--tone-safety)',
    title: { hi: 'दुकान का क्यूआर जाँचिए', en: 'Check the shop’s QR', ta: 'கடையின் க்யூஆரை சரிபாருங்கள்', te: 'దుకాణం క్యూఆర్ తనిఖీ చేయండి' },
    text: {
      hi: 'ठग असली क्यूआर के ऊपर अपना स्टिकर चिपका देते हैं। पैसे भेजने से पहले स्क्रीन पर दुकानदार का नाम पढ़कर मिलाइए।',
      en: 'Fraudsters paste their own sticker over the shop’s QR. Read the payee name on your screen and check it matches the shop before you pay.',
      ta: 'மோசடிக்காரர்கள் கடையின் க்யூஆர் மேல் தங்கள் ஸ்டிக்கரை ஒட்டுவார்கள். பணம் அனுப்பும் முன் திரையில் உள்ள பெயரைப் படித்துச் சரிபாருங்கள்.',
      te: 'మోసగాళ్లు దుకాణం క్యూఆర్ మీద తమ స్టిక్కర్ అంటిస్తారు. డబ్బు పంపే ముందు స్క్రీన్‌పై పేరు చదివి సరిపోల్చండి.',
    },
  },
  {
    id: 'lottery', icon: 'gift', tone: 'var(--tone-safety)',
    title: { hi: 'मुफ़्त इनाम कोई नहीं देता', en: 'Nobody gives free prizes', ta: 'யாரும் இலவசப் பரிசு தர மாட்டார்கள்', te: 'ఉచిత బహుమతులు ఎవరూ ఇవ్వరు' },
    text: {
      hi: 'लॉटरी, इनाम या नौकरी के लिए पहले पैसा माँगा जाए — तो वह ठगी ही है, चाहे संदेश कितना भी असली लगे।',
      en: 'If a lottery, a prize or a job asks you to pay first, it is a scam — however official the message looks.',
      ta: 'லாட்டரி, பரிசு அல்லது வேலைக்கு முதலில் பணம் கேட்டால் அது மோசடியே — செய்தி எவ்வளவு உண்மையாகத் தோன்றினாலும்.',
      te: 'లాటరీ, బహుమతి లేదా ఉద్యోగం కోసం ముందు డబ్బు అడిగితే అది మోసమే — సందేశం ఎంత నిజంగా కనిపించినా.',
    },
  },
];

// Phrases the help screen offers. Tapping one runs it through the same NLU path
// as speech, so the help screen doubles as a live test harness.
export const PHRASES = {
  hi: ['मेरा बैलेंस बताओ', 'रमेश को 500 रुपये भेजो', 'सरकारी योजना बताओ', 'यूपीआई क्या होता है', 'कोड स्कैन करो'],
  en: ['what is my balance', 'send 500 rupees to Ramesh', 'find a government scheme', 'what is UPI', 'scan a code'],
  ta: ['என் இருப்பு என்ன', 'ரமேஷ் க்கு 500 ரூபாய் அனுப்பு', 'அரசுத் திட்டம் சொல்', 'யுபிஐ என்றால் என்ன', 'கோடு ஸ்கேன் செய்'],
  te: ['నా బ్యాలెన్స్ చెప్పు', 'రమేష్ కి 500 రూపాయలు పంపు', 'ప్రభుత్వ పథకం చెప్పు', 'యూపీఐ అంటే ఏమిటి', 'కోడ్ స్కాన్ చేయి'],
};
