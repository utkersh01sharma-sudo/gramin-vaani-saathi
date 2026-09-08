# -*- coding: utf-8 -*-
"""Utterance templates per intent per language.

Placeholders: {person} {amount} {topic} {scheme} {language}

Keys ending in ``_latin`` hold Latin-script / code-mixed variants of the same
language -- how people actually type, and how ASR sometimes renders Indic speech.
They are emitted under the parent language code.
"""

TEMPLATES = {
    # ------------------------------------------------------------------ balance
    "check_balance": {
        "hi": [
            "मेरा बैलेंस क्या है", "खाते में कितने पैसे हैं", "बैलेंस बताओ",
            "मेरे खाते में कितना पैसा बचा है", "पैसे कितने हैं", "बैलेंस चेक करो",
            "अकाउंट बैलेंस दिखाओ", "कितना पैसा है मेरे पास", "मेरा खाता कितना है",
            "बताओ कितने रुपये हैं खाते में", "बैंक में कितना पैसा है",
        ],
        "hi_latin": [
            "mera balance kya hai", "balance batao", "khate mein kitne paise hain",
            "account balance check karo", "kitna paisa hai", "balance dikhao",
            "mere account mein kitne rupaye hain",
        ],
        "en": [
            "what is my balance", "show my account balance", "how much money do I have",
            "check balance", "tell me my balance", "current balance please",
            "how much is left in my account", "balance enquiry",
        ],
        "ta": [
            "என் இருப்பு என்ன", "கணக்கில் எவ்வளவு பணம் உள்ளது", "பேலன்ஸ் சொல்லுங்கள்",
            "என் கணக்கில் எவ்வளவு இருக்கு", "பணம் எவ்வளவு உள்ளது", "இருப்பு காட்டு",
        ],
        "te": [
            "నా బ్యాలెన్స్ ఎంత", "ఖాతాలో ఎంత డబ్బు ఉంది", "బ్యాలెన్స్ చెప్పు",
            "నా ఖాతాలో ఎంత మిగిలింది", "డబ్బు ఎంత ఉంది", "బ్యాలెన్స్ చూపించు",
        ],
    },
    # ---------------------------------------------------------------- send money
    "send_money": {
        "hi": [
            "{person} को {amount} रुपये भेजो", "{amount} रुपये {person} को भेज दो",
            "{person} को पैसे भेजने हैं {amount}", "भेजो {amount} {person} को",
            "{person} को {amount} ट्रांसफर करो", "{amount} रुपए {person} के खाते में डालो",
            "मुझे {person} को {amount} रुपये देने हैं", "{person} को पेमेंट करो {amount}",
            "यूपीआई से {person} को {amount} भेजो",
        ],
        "hi_latin": [
            "{person} ko {amount} rupaye bhejo", "{amount} rupees {person} ko send karo",
            "{person} ko paise bhejo {amount}", "transfer {amount} to {person}",
            "{person} ko {amount} transfer kar do",
        ],
        "en": [
            "send {amount} rupees to {person}", "transfer {amount} to {person}",
            "pay {person} {amount}", "I want to send {amount} to {person}",
            "make a payment of {amount} to {person}", "send money to {person}",
            "UPI transfer {amount} rupees to {person}",
        ],
        "ta": [
            "{person} க்கு {amount} ரூபாய் அனுப்பு", "{amount} ரூபாய் {person} க்கு அனுப்பவும்",
            "{person} க்கு பணம் அனுப்பு {amount}", "{person} க்கு {amount} செலுத்து",
            "{amount} ரூபாயை {person} கணக்கிற்கு மாற்று",
        ],
        "te": [
            "{person} కి {amount} రూపాయలు పంపు", "{amount} రూపాయలు {person} కి పంపించు",
            "{person} కి డబ్బు పంపు {amount}", "{person} కి {amount} చెల్లించు",
            "{amount} రూపాయలు {person} ఖాతాకు బదిలీ చేయి",
        ],
    },
    # ------------------------------------------------------------------- history
    "transaction_history": {
        "hi": [
            "पिछले लेनदेन दिखाओ", "मेरा स्टेटमेंट दिखाओ", "पिछले पेमेंट क्या थे",
            "आखिरी लेनदेन बताओ", "मैंने किसे पैसे भेजे", "लेनदेन का इतिहास दिखाओ",
            "पिछले महीने का हिसाब बताओ", "कौन कौन से पैसे आए",
        ],
        "hi_latin": [
            "pichle transaction dikhao", "mera statement batao", "last payment kya tha",
            "transaction history dikhao", "maine kise paise bheje",
        ],
        "en": [
            "show my transactions", "transaction history", "show last payments",
            "what was my last transaction", "mini statement", "show my statement",
            "who did I pay recently",
        ],
        "ta": [
            "எனது பரிவர்த்தனைகளைக் காட்டு", "கடைசி பரிவர்த்தனை என்ன", "அறிக்கை காட்டு",
            "நான் யாருக்கு பணம் அனுப்பினேன்", "பரிவர்த்தனை வரலாறு",
        ],
        "te": [
            "నా లావాదేవీలు చూపించు", "చివరి లావాదేవీ ఏమిటి", "స్టేట్‌మెంట్ చూపించు",
            "నేను ఎవరికి డబ్బు పంపాను", "లావాదేవీల చరిత్ర",
        ],
    },
    # --------------------------------------------------------------- find scheme
    "find_scheme": {
        "hi": [
            "सरकारी योजना बताओ", "मेरे लिए कौन सी योजना है", "{scheme} के बारे में बताओ",
            "किसानों के लिए कोई योजना है क्या", "मुझे खेती के लिए पैसा चाहिए",
            "सरकार से मदद कैसे मिलेगी", "लोन की कोई सरकारी स्कीम है",
            "बेटी के लिए कोई योजना बताओ", "पेंशन योजना के बारे में बताओ",
            "मुझे घर बनाने के लिए योजना चाहिए",
        ],
        "hi_latin": [
            "sarkari yojana batao", "mere liye kaun si scheme hai",
            "{scheme} ke bare mein batao", "kisan ke liye scheme hai kya",
            "government scheme chahiye",
        ],
        "en": [
            "show me government schemes", "which scheme is for me",
            "tell me about {scheme}", "is there a scheme for farmers",
            "I need money for farming", "government help for small business",
            "pension schemes available", "scheme for girl child",
        ],
        "ta": [
            "அரசு திட்டங்களைக் காட்டு", "எனக்கு எந்த திட்டம் பொருந்தும்",
            "{scheme} பற்றி சொல்லுங்கள்", "விவசாயிகளுக்கு திட்டம் உள்ளதா",
            "வேளாண்மைக்கு பணம் வேண்டும்",
        ],
        "te": [
            "ప్రభుత్వ పథకాలు చూపించు", "నాకు ఏ పథకం వర్తిస్తుంది",
            "{scheme} గురించి చెప్పు", "రైతులకు పథకం ఉందా",
            "వ్యవసాయానికి డబ్బు కావాలి",
        ],
    },
    # ---------------------------------------------------------- check eligibility
    "check_eligibility": {
        "hi": [
            "क्या मैं {scheme} के लिए योग्य हूं", "मुझे {scheme} मिल सकता है क्या",
            "क्या मैं इस योजना के लिए पात्र हूं", "मेरी पात्रता जांचो",
            "{scheme} के लिए क्या शर्तें हैं", "क्या मुझे यह योजना मिलेगी",
        ],
        "hi_latin": [
            "kya main {scheme} ke liye eligible hoon", "mujhe {scheme} mil sakta hai kya",
            "meri eligibility check karo",
        ],
        "en": [
            "am I eligible for {scheme}", "can I get {scheme}",
            "check my eligibility", "do I qualify for this scheme",
            "what are the conditions for {scheme}",
        ],
        "ta": [
            "நான் {scheme} க்கு தகுதியானவனா", "எனக்கு {scheme} கிடைக்குமா",
            "என் தகுதியை சரிபார்க்கவும்",
        ],
        "te": [
            "నేను {scheme} కి అర్హుడినా", "నాకు {scheme} వస్తుందా",
            "నా అర్హతను తనిఖీ చేయి",
        ],
    },
    # ------------------------------------------------------------------- scan QR
    "scan_qr": {
        "hi": [
            "क्यूआर कोड स्कैन करो", "यह क्यूआर चेक करो", "कैमरा खोलो क्यूआर के लिए",
            "यह कोड सही है क्या", "दुकान का क्यूआर स्कैन करना है",
            "क्यूआर से पेमेंट करना है", "यह क्यूआर किसका है",
        ],
        "hi_latin": [
            "qr code scan karo", "ye qr check karo", "qr se payment karna hai",
            "scan karo ye code",
        ],
        "en": [
            "scan this QR code", "check this QR", "open camera to scan",
            "is this QR code safe", "whose QR code is this", "scan and pay",
        ],
        "ta": [
            "இந்த க்யூஆர் கோடை ஸ்கேன் செய்", "இந்த க்யூஆர் சரியானதா",
            "கேமராவைத் திற ஸ்கேன் செய்ய", "இது யாருடைய க்யூஆர்",
        ],
        "te": [
            "ఈ క్యూఆర్ కోడ్ స్కాన్ చేయి", "ఈ క్యూఆర్ సరైనదా",
            "కెమెరా తెరువు స్కాన్ చేయడానికి", "ఇది ఎవరి క్యూఆర్",
        ],
    },
    # -------------------------------------------------------------- identify note
    "identify_note": {
        "hi": [
            "यह कितने का नोट है", "यह नोट पहचानो", "बताओ यह कौन सा नोट है",
            "यह कितने रुपये का है", "नोट की कीमत बताओ", "यह नोट कितने का है भाई",
            "मेरे हाथ में कौन सा नोट है",
        ],
        "hi_latin": [
            "ye kitne ka note hai", "note pehchano", "ye kaun sa note hai",
            "batao ye note kitne ka hai",
        ],
        "en": [
            "what note is this", "identify this currency note",
            "how much is this note worth", "tell me the denomination",
            "which rupee note is this",
        ],
        "ta": [
            "இது எவ்வளவு நோட்டு", "இந்த நோட்டை அடையாளம் காணு",
            "இது எத்தனை ரூபாய் நோட்டு", "நோட்டின் மதிப்பு சொல்",
        ],
        "te": [
            "ఇది ఎంత నోటు", "ఈ నోటును గుర్తించు",
            "ఇది ఎన్ని రూపాయల నోటు", "నోటు విలువ చెప్పు",
        ],
    },
    # --------------------------------------------------------------- report scam
    "report_scam": {
        "hi": [
            "मेरे साथ धोखा हुआ है", "किसी ने मेरे पैसे चुरा लिए",
            "मुझे ठगा गया है", "फ्रॉड की शिकायत करनी है",
            "मेरे खाते से पैसे गायब हो गए", "किसी ने ओटीपी लेकर पैसे निकाल लिए",
            "मुझे धोखाधड़ी रिपोर्ट करनी है",
        ],
        "hi_latin": [
            "mere sath dhokha hua hai", "mujhe thaga gaya hai",
            "fraud ki shikayat karni hai", "mere account se paise gayab ho gaye",
        ],
        "en": [
            "I have been scammed", "someone stole my money",
            "I want to report a fraud", "money disappeared from my account",
            "someone took my OTP and withdrew money", "report cyber fraud",
        ],
        "ta": [
            "நான் ஏமாற்றப்பட்டேன்", "யாரோ என் பணத்தை திருடிவிட்டார்கள்",
            "மோசடியை புகார் செய்ய வேண்டும்", "என் கணக்கிலிருந்து பணம் போய்விட்டது",
        ],
        "te": [
            "నేను మోసపోయాను", "ఎవరో నా డబ్బు దొంగిలించారు",
            "మోసంపై ఫిర్యాదు చేయాలి", "నా ఖాతా నుండి డబ్బు పోయింది",
        ],
    },
    # ---------------------------------------------------------------- check scam
    "check_scam": {
        "hi": [
            "यह मैसेज सही है क्या", "क्या यह एसएमएस असली है",
            "यह कॉल फ्रॉड तो नहीं", "यह मैसेज चेक करो",
            "किसी ने ओटीपी मांगा है क्या करूं", "यह लिंक सुरक्षित है क्या",
            "बैंक से मैसेज आया है सही है क्या", "यह नंबर धोखेबाज है क्या",
        ],
        "hi_latin": [
            "ye message sahi hai kya", "kya ye sms asli hai",
            "ye link safe hai kya", "koi otp maang raha hai kya karu",
            "ye call fraud to nahi hai",
        ],
        "en": [
            "is this message genuine", "is this SMS a scam",
            "check if this message is fraud", "someone is asking for my OTP",
            "is this link safe", "is this call a fraud", "verify this message",
        ],
        "ta": [
            "இந்த செய்தி உண்மையானதா", "இது மோசடி எஸ்எம்எஸ்ஸா",
            "இந்த இணைப்பு பாதுகாப்பானதா", "யாரோ ஓடிபி கேட்கிறார்கள்",
        ],
        "te": [
            "ఈ సందేశం నిజమైనదా", "ఇది మోసపు ఎస్ఎంఎస్ ఆ",
            "ఈ లింక్ సురక్షితమేనా", "ఎవరో ఓటీపీ అడుగుతున్నారు",
        ],
    },
    # --------------------------------------------------------------- learn topic
    "learn_topic": {
        "hi": [
            "{topic} के बारे में बताओ", "{topic} क्या होता है",
            "मुझे {topic} सीखना है", "{topic} कैसे काम करता है",
            "{topic} समझाओ", "{topic} के बारे में सिखाओ",
        ],
        "hi_latin": [
            "{topic} ke bare mein batao", "{topic} kya hota hai",
            "mujhe {topic} sikhna hai", "{topic} samjhao",
        ],
        "en": [
            "teach me about {topic}", "what is {topic}",
            "explain {topic}", "how does {topic} work",
            "I want to learn about {topic}",
        ],
        "ta": [
            "{topic} பற்றி சொல்லுங்கள்", "{topic} என்றால் என்ன",
            "{topic} விளக்கவும்", "எனக்கு {topic} கற்றுக்கொடு",
        ],
        "te": [
            "{topic} గురించి చెప్పు", "{topic} అంటే ఏమిటి",
            "{topic} వివరించు", "నాకు {topic} నేర్పించు",
        ],
    },
    # -------------------------------------------------------------- set language
    "set_language": {
        "hi": [
            "भाषा बदलो", "{language} में बात करो", "मुझे {language} चाहिए",
            "भाषा {language} कर दो", "{language} में बोलो",
        ],
        "hi_latin": [
            "bhasha badlo", "{language} mein baat karo", "language change karo",
        ],
        "en": [
            "change language", "speak in {language}", "switch to {language}",
            "I want {language}", "set language to {language}",
        ],
        "ta": [
            "மொழியை மாற்று", "{language} இல் பேசு", "எனக்கு {language} வேண்டும்",
        ],
        "te": [
            "భాష మార్చు", "{language} లో మాట్లాడు", "నాకు {language} కావాలి",
        ],
    },
    # ---------------------------------------------------------------------- help
    "help": {
        "hi": [
            "मदद चाहिए", "मुझे समझ नहीं आ रहा", "यह ऐप कैसे चलाएं",
            "क्या क्या कर सकते हो", "मदद करो", "मुझे नहीं पता क्या करूं",
            "आप क्या क्या कर सकते हैं",
        ],
        "hi_latin": [
            "madad chahiye", "help karo", "ye app kaise chalaye",
            "aap kya kar sakte ho",
        ],
        "en": [
            "help me", "I need help", "what can you do",
            "how do I use this app", "show me the options", "I am confused",
        ],
        "ta": [
            "எனக்கு உதவி வேண்டும்", "இந்த செயலியை எப்படி பயன்படுத்துவது",
            "நீங்கள் என்ன செய்ய முடியும்", "உதவி செய்யுங்கள்",
        ],
        "te": [
            "నాకు సహాయం కావాలి", "ఈ యాప్ ఎలా వాడాలి",
            "మీరు ఏమి చేయగలరు", "సహాయం చేయండి",
        ],
    },
    # -------------------------------------------------------------------- repeat
    "repeat": {
        "hi": [
            "फिर से बोलो", "दोबारा कहो", "मैंने सुना नहीं",
            "एक बार और बोलो", "फिर से बताओ", "क्या कहा आपने",
        ],
        "hi_latin": ["phir se bolo", "dobara kaho", "maine suna nahi", "repeat karo"],
        "en": [
            "say that again", "repeat please", "I did not hear you",
            "one more time", "what did you say", "come again",
        ],
        "ta": ["மீண்டும் சொல்", "திரும்ப சொல்லுங்கள்", "நான் கேட்கவில்லை", "என்ன சொன்னீர்கள்"],
        "te": ["మళ్లీ చెప్పు", "మరోసారి చెప్పండి", "నేను వినలేదు", "ఏమన్నారు"],
    },
    # ------------------------------------------------------------------- unknown
    # Out-of-scope chatter. Without this class the model confidently misroutes
    # every unrelated sentence into a banking action.
    "unknown": {
        "hi": [
            "आज मौसम कैसा है", "क्रिकेट का स्कोर बताओ", "गाना बजाओ",
            "तुम कौन हो", "खाना क्या बनाऊं", "कल छुट्टी है क्या",
            "बस कब आएगी", "मेरा फोन खराब है", "टीवी चालू करो",
            "अच्छा ठीक है", "नमस्ते", "धन्यवाद", "बाजार कितनी दूर है",
        ],
        "hi_latin": [
            "aaj mausam kaisa hai", "cricket score batao", "gana bajao",
            "tum kaun ho", "namaste", "thank you", "theek hai",
        ],
        "en": [
            "what is the weather today", "tell me a joke", "play some music",
            "who are you", "what time is it", "hello", "thanks", "okay fine",
            "how far is the market", "my phone is broken",
        ],
        "ta": [
            "இன்று வானிலை எப்படி", "பாட்டு போடு", "நீங்கள் யார்",
            "வணக்கம்", "நன்றி", "நேரம் என்ன",
        ],
        "te": [
            "ఈరోజు వాతావరణం ఎలా ఉంది", "పాట పెట్టు", "మీరు ఎవరు",
            "నమస్కారం", "ధన్యవాదాలు", "సమయం ఎంత",
        ],
    },
}
