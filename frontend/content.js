// Sample content for the schemes, learn, and safety screens.
//
// This is a placeholder that the API replaces: schemes move to
// apps/schemes/fixtures with structured eligibility rules, lessons move to
// apps/literacy, and the safety verdict comes from the trained scam model.
// It lives here so the shell demonstrates the real flow before those land, and
// so a reviewer can see the intended copy register — short sentences, no jargon,
// nothing that reads like a bank form.
//
// The scheme facts are public information about real Government of India
// schemes; the descriptions are plain-language paraphrases, not eligibility
// advice. The app never tells a user they qualify — only what the scheme is for.

export const SCHEMES = [
  {
    id: 'pm-kisan', icon: 'sprout', tone: 'var(--tone-scheme)',
    title: { hi: 'पीएम किसान', en: 'PM-KISAN', ta: 'பிஎம் கிசான்', te: 'పీఎం కిసాన్' },
    text: {
      hi: 'छोटे किसानों को साल में ₹6,000 तीन किस्तों में सीधे खाते में।',
      en: 'Small farmers receive ₹6,000 a year, in three instalments, straight to the bank account.',
      ta: 'சிறு விவசாயிகளுக்கு ஆண்டுக்கு ₹6,000, மூன்று தவணைகளாக நேரடியாக வங்கிக் கணக்கில்.',
      te: 'చిన్న రైతులకు సంవత్సరానికి ₹6,000, మూడు విడతలుగా నేరుగా ఖాతాలోకి.',
    },
  },
  {
    id: 'jan-dhan', icon: 'bank', tone: 'var(--tone-scheme)',
    title: { hi: 'जन धन खाता', en: 'Jan Dhan Account', ta: 'ஜன் தன் கணக்கு', te: 'జన్ ధన్ ఖాతా' },
    text: {
      hi: 'बिना कोई पैसा रखे बैंक खाता, साथ में दुर्घटना बीमा और रुपे कार्ड।',
      en: 'A bank account with no minimum balance, plus accident cover and a RuPay card.',
      ta: 'குறைந்தபட்ச இருப்பு தேவையில்லாத வங்கிக் கணக்கு, விபத்துக் காப்பீடு மற்றும் ருபே கார்டு.',
      te: 'కనీస నిల్వ అవసరం లేని బ్యాంకు ఖాతా, ప్రమాద బీమా, రూపే కార్డుతో.',
    },
  },
  {
    id: 'mudra', icon: 'wrench', tone: 'var(--tone-scheme)',
    title: { hi: 'मुद्रा ऋण', en: 'MUDRA Loan', ta: 'முத்ரா கடன்', te: 'ముద్ర రుణం' },
    text: {
      hi: 'छोटा धंधा शुरू करने या बढ़ाने के लिए ₹10 लाख तक का कर्ज़, बिना गारंटी।',
      en: 'Up to ₹10 lakh to start or grow a small business, with no collateral.',
      ta: 'சிறு தொழில் தொடங்க அல்லது வளர்க்க ₹10 லட்சம் வரை, அடமானம் இல்லாமல்.',
      te: 'చిన్న వ్యాపారం మొదలుపెట్టడానికి లేదా పెంచడానికి ₹10 లక్షల వరకు, హామీ లేకుండా.',
    },
  },
  {
    id: 'pmjjby', icon: 'shield', tone: 'var(--tone-scheme)',
    title: { hi: 'जीवन ज्योति बीमा', en: 'Jeevan Jyoti Insurance', ta: 'ஜீவன் ஜோதி காப்பீடு', te: 'జీవన్ జ్యోతి బీమా' },
    text: {
      hi: 'साल में ₹436 देकर ₹2 लाख का जीवन बीमा, 18 से 50 साल की उम्र तक।',
      en: '₹2 lakh of life cover for ₹436 a year, for ages 18 to 50.',
      ta: 'ஆண்டுக்கு ₹436 செலுத்தி ₹2 லட்சம் ஆயுள் காப்பீடு, 18 முதல் 50 வயது வரை.',
      te: 'సంవత్సరానికి ₹436 చెల్లించి ₹2 లక్షల జీవిత బీమా, 18 నుండి 50 ఏళ్ల వయసు వరకు.',
    },
  },
  {
    id: 'sukanya', icon: 'girl', tone: 'var(--tone-scheme)',
    title: { hi: 'सुकन्या समृद्धि', en: 'Sukanya Samriddhi', ta: 'சுகன்யா சம்ரித்தி', te: 'సుకన్య సమృద్ధి' },
    text: {
      hi: 'बेटी के नाम बचत खाता, ऊँचा ब्याज और टैक्स में छूट। 10 साल से छोटी उम्र में खोलिए।',
      en: 'A savings account in a daughter’s name with high interest and tax relief. Open it before she turns 10.',
      ta: 'மகளின் பெயரில் சேமிப்புக் கணக்கு, அதிக வட்டி மற்றும் வரிச் சலுகை. 10 வயதுக்கு முன் திறக்கவும்.',
      te: 'కుమార్తె పేరుతో పొదుపు ఖాతా, ఎక్కువ వడ్డీ, పన్ను మినహాయింపు. 10 ఏళ్లలోపు తెరవండి.',
    },
  },
  {
    id: 'nrega', icon: 'pickaxe', tone: 'var(--tone-scheme)',
    title: { hi: 'मनरेगा', en: 'MGNREGA', ta: 'மகாத்மா காந்தி வேலைத் திட்டம்', te: 'ఎంజీఎన్ఆర్ఈజీఏ' },
    text: {
      hi: 'हर ग्रामीण परिवार को साल में 100 दिन का काम, तय मज़दूरी के साथ।',
      en: '100 days of guaranteed paid work a year for every rural household.',
      ta: 'ஒவ்வொரு கிராமப்புற குடும்பத்திற்கும் ஆண்டுக்கு 100 நாள் உத்தரவாத வேலை.',
      te: 'ప్రతి గ్రామీణ కుటుంబానికి సంవత్సరానికి 100 రోజుల పని, నిర్ణీత కూలీతో.',
    },
  },
];

export const LESSONS = [
  {
    id: 'upi', icon: 'upi', tone: 'var(--tone-learn)',
    title: { hi: 'यूपीआई क्या है?', en: 'What is UPI?', ta: 'யுபிஐ என்றால் என்ன?', te: 'యూపీఐ అంటే ఏమిటి?' },
    text: {
      hi: 'यूपीआई से आप फ़ोन से सीधे किसी के बैंक खाते में पैसा भेज सकते हैं। इसके लिए बस उनका यूपीआई नाम या क्यूआर कोड चाहिए। पैसा तुरंत पहुँचता है और कोई फ़ीस नहीं लगती।',
      en: 'UPI lets you send money straight from your phone into someone’s bank account. You only need their UPI name or their QR code. The money arrives at once and there is no fee.',
      ta: 'யுபிஐ மூலம் உங்கள் ஃபோனிலிருந்து நேரடியாக ஒருவரின் வங்கிக் கணக்கிற்குப் பணம் அனுப்பலாம். அவரது யுபிஐ பெயர் அல்லது க்யூஆர் கோடு மட்டும் போதும். பணம் உடனே சேரும், கட்டணம் இல்லை.',
      te: 'యూపీఐ ద్వారా మీ ఫోన్ నుండి నేరుగా ఒకరి బ్యాంకు ఖాతాలోకి డబ్బు పంపవచ్చు. వారి యూపీఐ పేరు లేదా క్యూఆర్ కోడ్ మాత్రమే కావాలి. డబ్బు వెంటనే చేరుతుంది, ఎలాంటి రుసుము లేదు.',
    },
  },
  {
    id: 'pin', icon: 'lock', tone: 'var(--tone-learn)',
    title: { hi: 'पिन कभी मत बताइए', en: 'Never share your PIN', ta: 'உங்கள் பின்னை ஒருபோதும் சொல்லாதீர்கள்', te: 'మీ పిన్ ఎప్పుడూ చెప్పకండి' },
    text: {
      hi: 'आपका यूपीआई पिन और ओटीपी सिर्फ़ आपका है। बैंक, पुलिस या कोई सरकारी अफ़सर कभी फ़ोन पर पिन नहीं माँगता। पैसा लेने के लिए कभी पिन नहीं डालना पड़ता — पिन सिर्फ़ पैसा देने के लिए होता है।',
      en: 'Your UPI PIN and OTP belong only to you. No bank, police officer or government official will ever ask for them on a call. You never enter a PIN to *receive* money — a PIN only ever sends money out.',
      ta: 'உங்கள் யுபிஐ பின்னும் ஓடிபியும் உங்களுக்கு மட்டுமே. வங்கியோ, காவல்துறையோ, அரசு அதிகாரியோ போனில் பின் கேட்க மாட்டார்கள். பணம் பெற பின் தேவையில்லை — பின் பணம் அனுப்பவே பயன்படும்.',
      te: 'మీ యూపీఐ పిన్, ఓటీపీ మీవి మాత్రమే. బ్యాంకు, పోలీసు, ప్రభుత్వ అధికారి ఎవరూ ఫోన్‌లో పిన్ అడగరు. డబ్బు అందుకోవడానికి పిన్ అవసరం లేదు — పిన్ డబ్బు పంపడానికి మాత్రమే.',
    },
  },
  {
    id: 'interest', icon: 'growth', tone: 'var(--tone-learn)',
    title: { hi: 'ब्याज क्या होता है?', en: 'What is interest?', ta: 'வட்டி என்றால் என்ன?', te: 'వడ్డీ అంటే ఏమిటి?' },
    text: {
      hi: 'ब्याज कर्ज़ की कीमत है। ₹10,000 का कर्ज़ 12% ब्याज पर लिया, तो साल भर में ₹1,200 ज़्यादा लौटाने होंगे। बचत खाते में उल्टा होता है — बैंक आपको ब्याज देता है।',
      en: 'Interest is the price of borrowing. Borrow ₹10,000 at 12% and you repay ₹1,200 more over a year. In a savings account it works the other way: the bank pays you.',
      ta: 'வட்டி என்பது கடன் வாங்குவதற்கான விலை. ₹10,000 கடனை 12% வட்டியில் வாங்கினால், ஒரு ஆண்டில் ₹1,200 கூடுதலாகத் திருப்பித் தர வேண்டும். சேமிப்புக் கணக்கில் நேர்மாறாக — வங்கி உங்களுக்கு வட்டி தரும்.',
      te: 'వడ్డీ అంటే అప్పు తీసుకోవడానికి చెల్లించే ఖరీదు. ₹10,000 అప్పును 12% వడ్డీకి తీసుకుంటే, ఏడాదిలో ₹1,200 ఎక్కువ తిరిగి చెల్లించాలి. పొదుపు ఖాతాలో దీనికి వ్యతిరేకం — బ్యాంకు మీకు వడ్డీ ఇస్తుంది.',
    },
  },
  {
    id: 'saving', icon: 'coins', tone: 'var(--tone-learn)',
    title: { hi: 'थोड़ा-थोड़ा बचाइए', en: 'Save a little, often', ta: 'கொஞ்சம் கொஞ்சமாகச் சேமியுங்கள்', te: 'కొంచెం కొంచెం దాచుకోండి' },
    text: {
      hi: 'रोज़ ₹20 बचाने से साल में ₹7,300 जमा हो जाते हैं। बड़ी रकम का इंतज़ार मत कीजिए — छोटी और नियमित बचत ही काम आती है, ख़ास तौर पर अचानक बीमारी या फ़सल ख़राब होने पर।',
      en: 'Saving ₹20 a day adds up to ₹7,300 in a year. Do not wait for a large sum — small, regular saving is what carries a household through an illness or a failed crop.',
      ta: 'நாளொன்றுக்கு ₹20 சேமித்தால் ஆண்டுக்கு ₹7,300 சேரும். பெரிய தொகைக்குக் காத்திருக்க வேண்டாம் — சிறிய, தொடர்ச்சியான சேமிப்பே நோய் அல்லது பயிர் இழப்பின் போது உதவும்.',
      te: 'రోజుకు ₹20 దాచితే ఏడాదికి ₹7,300 అవుతుంది. పెద్ద మొత్తం కోసం ఎదురుచూడకండి — చిన్న, క్రమమైన పొదుపే అనారోగ్యం లేదా పంట నష్టం సమయంలో ఆదుకుంటుంది.',
    },
  },
  {
    id: 'passbook', icon: 'passbook', tone: 'var(--tone-learn)',
    title: { hi: 'पासबुक कैसे पढ़ें', en: 'How to read a passbook', ta: 'பாஸ்புக்கை எப்படிப் படிப்பது', te: 'పాస్‌బుక్ ఎలా చదవాలి' },
    text: {
      hi: 'पासबुक में तीन बातें देखिए: तारीख़, कितना आया या गया, और उसके बाद कितना बचा। अगर कोई ऐसा लेनदेन दिखे जो आपने नहीं किया, तो उसी दिन बैंक जाइए।',
      en: 'Look at three things in a passbook: the date, how much went in or out, and the balance left after it. If you see an entry you did not make, go to the bank that same day.',
      ta: 'பாஸ்புக்கில் மூன்று விஷயங்களைப் பாருங்கள்: தேதி, எவ்வளவு வந்தது அல்லது போனது, அதன் பின் மீதி எவ்வளவு. நீங்கள் செய்யாத பரிவர்த்தனை தெரிந்தால் அன்றே வங்கிக்குச் செல்லுங்கள்.',
      te: 'పాస్‌బుక్‌లో మూడు విషయాలు చూడండి: తేదీ, ఎంత వచ్చింది లేదా పోయింది, ఆ తర్వాత మిగిలింది ఎంత. మీరు చేయని లావాదేవీ కనిపిస్తే అదే రోజు బ్యాంకుకు వెళ్లండి.',
    },
  },
];

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
