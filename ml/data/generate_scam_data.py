# -*- coding: utf-8 -*-
"""Synthetic SMS / WhatsApp corpus for ScamNet: safe / suspicious / scam.

Why synthetic: there is no public labelled corpus of Indian-language financial
fraud messages, and the UCI SMS Spam Collection is English marketing spam from
2011 Singapore and the UK -- the wrong language, the wrong fraud, and the wrong
decade. What exists instead is a well-documented catalogue of the scams that
actually run in India (RBI and NPCI awareness material, cyber-crime portal
advisories): fake KYC expiry, electricity disconnection, the "army officer" who
pays you by asking you to scan a QR, lottery and KBC prizes, loan-app fees,
remote-access apps, task-based job offers. Each template below is one of those
patterns, written in each of the four languages plus romanised Hindi.

The class that makes the problem hard is not scam, it is **safe**. Real bank
messages contain an OTP, an amount, a link and a phone number too. The safe
templates are written to share surface features with the scams on purpose --
"Your OTP is 482913. Do not share it with anyone" -- so that a model which
learns "OTP means scam" is punished during training, and so the rule-only
ablation shows exactly where keyword matching fails.

Honesty note: the held-out test set (scam_test_handwritten.jsonl) was written
separately, in different words, and is the only number worth quoting. Accuracy
on data from this generator measures how well a model learned the generator.

    python ml/data/generate_scam_data.py            # writes scam_{train,val}.jsonl
"""
from __future__ import annotations

import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = 7
PER_CLASS_PER_LANG = 750   # x 3 classes x 4 languages = 9,000 rows

BANKS = ["SBI", "HDFC", "ICICI", "PNB", "Canara Bank", "Bank of Baroda", "Axis", "Union Bank", "Indian Bank"]
SCAM_LINKS = [
    "sbi-kyc-update.xyz", "hdfc-rewards.top/claim", "pmkisan-refund.online", "bijli-bill-pay.click",
    "kbc-lucky-winner.in.net", "amaz0n-gift.shop", "icici-secure-login.site", "npci-upi-verify.live",
    "rbi-refund-cell.info", "income-tax-refund.buzz", "pay-tm-cashback.win", "indiapost-redeliver.top",
]
SHORT_LINKS = ["bit.ly/3xK9pQ", "tinyurl.com/kyc-upd8", "cutt.ly/rwRd7", "rb.gy/x7k2p", "is.gd/Ab3dE",
               "bit.ly/sbi-kyc", "tiny.cc/bonus24"]
SAFE_LINKS = ["https://www.onlinesbi.sbi", "https://pmkisan.gov.in", "https://uidai.gov.in",
              "https://www.irctc.co.in", "https://www.amazon.in/orders", "https://www.sbi.co.in"]
COMPANIES = ["Flipkart", "Amazon", "Jio", "Airtel", "Meesho", "Paytm", "PhonePe"]
NAMES_HI = ["रमेश", "सुनीता", "राजू", "गीता", "मोहन", "पूजा"]
NAMES_EN = ["Ramesh", "Sunita", "Raju", "Geeta", "Mohan", "Pooja", "Arjun", "Priya"]
NAMES_TA = ["முருகன்", "லட்சுமி", "செல்வி", "கார்த்திக்", "மீனா"]
NAMES_TE = ["రాజు", "లక్ష్మి", "సురేష్", "పద్మ", "వెంకట్"]


def phone() -> str:
    return random.choice("6789") + "".join(random.choice("0123456789") for _ in range(9))


def amount(big: bool = False) -> str:
    if big:
        return f"{random.choice([25, 50, 75, 99, 150, 250, 500]) * 1000:,}"
    return str(random.choice([49, 99, 120, 150, 250, 300, 499, 500, 750, 1000, 1200, 1500, 2000, 2500, 5000]))


def fill(template: str, lang: str) -> str:
    names = {"hi": NAMES_HI, "en": NAMES_EN, "ta": NAMES_TA, "te": NAMES_TE}[lang]
    slots = {
        "bank": random.choice(BANKS),
        "link": random.choice(SCAM_LINKS),
        "short": random.choice(SHORT_LINKS),
        "safe": random.choice(SAFE_LINKS),
        "phone": phone(),
        "amt": amount(),
        "big": amount(big=True),
        "name": random.choice(names),
        "last4": f"{random.randint(1000, 9999)}",
        "otp": f"{random.randint(100000, 999999)}",
        "company": random.choice(COMPANIES),
        "date": f"{random.randint(1, 28):02d}-{random.randint(1, 12):02d}",
        "time": f"{random.randint(1, 12)}:{random.choice(['00', '15', '30', '45'])}",
        "tollfree": f"1800-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
    }
    return template.format(**slots)


T: dict[str, dict[str, list[str]]] = {}

# ============================================================== Hindi
T["hi"] = {
    "scam": [
        "प्रिय ग्राहक, आपका {bank} खाता आज रात बंद हो जाएगा। तुरंत केवाईसी अपडेट करें: {link}",
        "आपकी बिजली आज रात 9:30 बजे काट दी जाएगी क्योंकि पिछला बिल अपडेट नहीं है। तुरंत बिजली अधिकारी को कॉल करें {phone}",
        "बधाई हो! आपने केबीसी लॉटरी में ₹{big} जीते हैं। इनाम पाने के लिए ₹{amt} रजिस्ट्रेशन फीस जमा करें। संपर्क {phone}",
        "मैं {bank} से बोल रहा हूँ, आपके खाते में गलत लेनदेन हुआ है। अभी आए OTP को बताइए ताकि हम रोक सकें।",
        "मैं आर्मी में हूँ, आपका सामान खरीदना है। पैसे पाने के लिए यह QR स्कैन करके UPI पिन डालिए।",
        "आपका पीएम किसान का ₹{amt} रुका हुआ है। पाने के लिए इस लिंक पर अपना कार्ड नंबर और पिन भरें {short}",
        "घर बैठे रोज़ ₹{amt} कमाएं, सिर्फ़ वीडियो लाइक करें। जुड़ने के लिए ₹{amt} फीस दें। व्हाट्सएप {phone}",
        "आपका लोन ₹{big} मंज़ूर हो गया है। प्रोसेसिंग फीस ₹{amt} जमा करें, लोन 1 घंटे में खाते में आएगा।",
        "ग्राहक सेवा: आपकी समस्या हल करने के लिए AnyDesk ऐप डाउनलोड करें और कोड बताएं।",
        "आपके नाम पर पार्सल में गैरकानूनी सामान मिला है। पुलिस केस से बचने के लिए तुरंत ₹{big} भेजें वरना गिरफ्तार होंगे।",
        "आपका सिम 24 घंटे में ब्लॉक हो जाएगा। केवाईसी के लिए अभी {phone} पर कॉल करें।",
        "आपके {bank} क्रेडिट कार्ड के इनाम पॉइंट आज खत्म हो रहे हैं। अभी भुनाएं: {link}",
    ],
    "suspicious": [
        "सिर्फ़ 5 मिनट में ₹{big} तक का पर्सनल लोन, कम ब्याज। अभी अप्लाई करें {short}",
        "नमस्ते, गलती से आपके खाते में ₹{amt} चले गए हैं। कृपया चेक करके बताइए। {phone}",
        "{company} सेल! 80% तक छूट, सिर्फ़ आज। अभी खरीदें {short}",
        "आप हमारे लकी ग्राहक चुने गए हैं, और जानकारी के लिए इस नंबर पर कॉल करें {phone}",
        "पार्ट टाइम नौकरी चाहिए? रोज़ 2 घंटे काम, अच्छी कमाई। जवाब दें YES",
        "आपके लिए खास क्रेडिट कार्ड ऑफर तैयार है, बिना किसी कागज़ के। देखें {short}",
        "नया निवेश प्लान: 30 दिन में पैसा दोगुना। जुड़ने के लिए संपर्क करें {phone}",
        "कौन बोल रहा है? मेरा नंबर आपके फ़ोन में कैसे आया? यह लिंक खोलिए {short}",
    ],
    "safe": [
        "{bank}: आपके खाते XX{last4} से ₹{amt} {date} को डेबिट हुए। आपने नहीं किया? {tollfree} पर कॉल करें।",
        "{otp} आपका OTP है। यह 10 मिनट तक मान्य है। किसी के साथ साझा न करें। -{bank}",
        "आपके खाते XX{last4} में ₹{amt} जमा हुए। उपलब्ध शेष राशि देखने के लिए {bank} ऐप खोलें।",
        "पीएम किसान की किस्त ₹2000 आपके खाते में जमा कर दी गई है। जानकारी: {safe}",
        "बेटा, शाम को घर आते समय दूध और सब्ज़ी लेते आना।",
        "आपका {company} रिचार्ज ₹{amt} सफल रहा। धन्यवाद।",
        "{name}, कल सुबह {time} बजे पंचायत भवन में बैठक है, ज़रूर आइए।",
        "आपका बिजली बिल ₹{amt} जमा हो गया है। रसीद नंबर {last4}। धन्यवाद।",
        "{bank} कभी भी फ़ोन या संदेश पर आपका PIN, OTP या पासवर्ड नहीं माँगता। सावधान रहें।",
        "आपका ऑर्डर कल तक पहुँच जाएगा। ट्रैक करें: {safe}",
        "{name} ने आपको ₹{amt} भेजे हैं। UPI रेफ़ नंबर {otp}।",
    ],
}

# ============================================================== Romanised Hindi
T["hi_latin"] = {
    "scam": [
        "Aapka {bank} account aaj band ho jayega. Turant KYC update karein: {link}",
        "Bijli ka connection aaj raat kat jayega. Abhi call karein {phone}",
        "Badhai ho! Aapne KBC lottery mein Rs {big} jeete. Inaam ke liye Rs {amt} fees jama karein.",
        "Main {bank} se bol raha hoon, abhi aaya OTP batao warna account block ho jayega.",
        "Paise paane ke liye ye QR scan karke UPI PIN daalo, main army mein hoon.",
        "Ghar baithe roz Rs {amt} kamao, sirf videos like karo. Joining fees Rs {amt}. WhatsApp {phone}",
        "Customer care: AnyDesk app download karke code bata dijiye, refund mil jayega.",
    ],
    "suspicious": [
        "Sirf 5 minute mein Rs {big} ka loan, kam byaaj. Apply karein {short}",
        "Galti se aapke account mein Rs {amt} chale gaye, check karke batao. {phone}",
        "Part time job chahiye? Roz 2 ghante, achhi kamai. Reply YES",
        "Aap lucky customer chune gaye hain, details ke liye call karein {phone}",
    ],
    "safe": [
        "{bank}: A/c XX{last4} se Rs {amt} debit hue. Aapne nahi kiya? Call {tollfree}",
        "{otp} aapka OTP hai. Kisi ko na batayein. -{bank}",
        "Beta shaam ko aate waqt doodh le aana.",
        "Aapke account XX{last4} mein Rs {amt} credit hue. -{bank}",
        "{name}, kal subah {time} baje meeting hai, zaroor aana.",
        "Aapka {company} recharge Rs {amt} safal raha. Dhanyavaad.",
    ],
}

# ============================================================== English
T["en"] = {
    "scam": [
        "Dear customer, your {bank} account will be blocked today. Update your KYC immediately: {link}",
        "Your electricity will be disconnected tonight at 9:30 as your last bill is not updated. Call the officer now {phone}",
        "Congratulations! You have won Rs {big} in the KBC lucky draw. Pay Rs {amt} processing fee to claim. Contact {phone}",
        "This is {bank} fraud team. A suspicious transaction was found. Share the OTP you just received to cancel it.",
        "I am an army officer and want to buy your item. To receive the payment scan this QR and enter your UPI PIN.",
        "Your PM-KISAN amount of Rs {amt} is on hold. Enter your card number and PIN here to release it: {short}",
        "Earn Rs {amt} daily from home by liking videos. Registration fee Rs {amt}. WhatsApp {phone}",
        "Your loan of Rs {big} is approved. Pay a refundable deposit of Rs {amt} and get the money in 1 hour.",
        "Customer support here. Please install AnyDesk and tell us the 9-digit code so we can process your refund.",
        "A parcel in your name contains illegal items. Transfer Rs {big} immediately to avoid arrest.",
        "Your SIM will be blocked within 24 hours. Call {phone} now to complete KYC.",
        "Your {bank} credit card reward points expire today. Redeem now at {link}",
        "Income tax refund of Rs {big} approved. Verify your bank details to receive it: {link}",
        "Your India Post parcel could not be delivered. Pay Rs 25 redelivery fee here: {short}",
    ],
    "suspicious": [
        "Get an instant personal loan up to Rs {big} with low interest. Apply now {short}",
        "Hi, I sent Rs {amt} to your account by mistake. Please check and send it back. {phone}",
        "{company} mega sale! Up to 80% off, today only. Shop now {short}",
        "You have been selected as our lucky customer. Call {phone} for details.",
        "Looking for a part-time job? 2 hours a day, good income. Reply YES to know more.",
        "Pre-approved credit card offer with zero paperwork. Check it out {short}",
        "New investment plan: double your money in 30 days. Contact {phone}",
        "Hello, who is this? Someone gave me your number. Open this {short}",
    ],
    "safe": [
        "{bank}: Rs {amt} debited from A/c XX{last4} on {date}. Not you? Call {tollfree}.",
        "{otp} is your OTP for the transaction. Valid for 10 minutes. Do not share it with anyone. -{bank}",
        "Rs {amt} credited to your A/c XX{last4}. Check balance in the {bank} app.",
        "PM-KISAN instalment of Rs 2000 has been credited to your account. Details: {safe}",
        "Please buy milk and vegetables on your way home this evening.",
        "Your {company} recharge of Rs {amt} was successful. Thank you.",
        "{name}, there is a panchayat meeting tomorrow at {time}. Please come.",
        "Your electricity bill payment of Rs {amt} is received. Receipt no {last4}.",
        "{bank} will never ask for your PIN, OTP or password by call or message. Stay alert.",
        "Your order will arrive by tomorrow. Track it at {safe}",
        "{name} has sent you Rs {amt}. UPI ref {otp}.",
        "Reminder: your appointment at the health centre is on {date} at {time}.",
    ],
}

# ============================================================== Tamil
T["ta"] = {
    "scam": [
        "அன்புள்ள வாடிக்கையாளரே, உங்கள் {bank} கணக்கு இன்று முடக்கப்படும். உடனே கேஒய்சி புதுப்பிக்கவும்: {link}",
        "உங்கள் மின் இணைப்பு இன்றிரவு துண்டிக்கப்படும். உடனடியாக அதிகாரியை அழைக்கவும் {phone}",
        "வாழ்த்துக்கள்! நீங்கள் லாட்டரியில் ரூ {big} வென்றீர்கள். பரிசைப் பெற ரூ {amt} கட்டணம் செலுத்துங்கள். {phone}",
        "நான் {bank} வங்கியிலிருந்து பேசுகிறேன். இப்போது வந்த OTP-ஐ சொல்லுங்கள், இல்லையெனில் கணக்கு முடக்கப்படும்.",
        "நான் ராணுவ அதிகாரி. பணம் பெற இந்த QR-ஐ ஸ்கேன் செய்து UPI பின் போடுங்கள்.",
        "உங்கள் பிஎம் கிசான் பணம் ரூ {amt} நிறுத்தப்பட்டுள்ளது. பெற இந்த இணைப்பில் கார்டு எண் மற்றும் பின் உள்ளிடவும் {short}",
        "வீட்டிலிருந்தே தினமும் ரூ {amt} சம்பாதிக்கலாம். சேர கட்டணம் ரூ {amt}. வாட்ஸ்அப் {phone}",
        "உங்கள் கடன் ரூ {big} அனுமதிக்கப்பட்டது. செயலாக்கக் கட்டணம் ரூ {amt} செலுத்துங்கள்.",
        "வாடிக்கையாளர் சேவை: AnyDesk செயலியை நிறுவி குறியீட்டைச் சொல்லுங்கள், பணம் திரும்ப வரும்.",
        "உங்கள் பெயரில் வந்த பார்சலில் சட்டவிரோதப் பொருள் உள்ளது. கைது ஆகாமல் இருக்க உடனே ரூ {big} அனுப்புங்கள்.",
        "உங்கள் சிம் 24 மணி நேரத்தில் முடக்கப்படும். கேஒய்சிக்கு இப்போதே அழைக்கவும் {phone}",
    ],
    "suspicious": [
        "5 நிமிடத்தில் ரூ {big} வரை தனிநபர் கடன், குறைந்த வட்டி. இப்போதே விண்ணப்பிக்கவும் {short}",
        "வணக்கம், தவறுதலாக உங்கள் கணக்கிற்கு ரூ {amt} அனுப்பிவிட்டேன். சரிபார்த்துச் சொல்லுங்கள். {phone}",
        "{company} பெரும் தள்ளுபடி! 80% வரை, இன்று மட்டும். {short}",
        "நீங்கள் எங்கள் அதிர்ஷ்ட வாடிக்கையாளராகத் தேர்ந்தெடுக்கப்பட்டீர்கள். விவரங்களுக்கு அழைக்கவும் {phone}",
        "பகுதி நேர வேலை வேண்டுமா? தினமும் 2 மணி நேரம், நல்ல வருமானம். YES என்று பதில் அனுப்பவும்.",
        "30 நாளில் பணம் இரட்டிப்பு. புதிய முதலீட்டுத் திட்டம். அழைக்கவும் {phone}",
        "யார் நீங்கள்? என் எண் எப்படி கிடைத்தது? இந்த இணைப்பைத் திறங்கள் {short}",
    ],
    "safe": [
        "{bank}: உங்கள் கணக்கு XX{last4} இலிருந்து ரூ {amt} {date} அன்று பற்று வைக்கப்பட்டது. நீங்கள் இல்லையெனில் {tollfree} அழைக்கவும்.",
        "{otp} உங்கள் OTP. 10 நிமிடம் செல்லும். யாரிடமும் பகிர வேண்டாம். -{bank}",
        "உங்கள் கணக்கு XX{last4} இல் ரூ {amt} வரவு வைக்கப்பட்டது. -{bank}",
        "பிஎம் கிசான் தவணை ரூ 2000 உங்கள் கணக்கில் வரவு வைக்கப்பட்டது. விவரம்: {safe}",
        "மாலை வீட்டுக்கு வரும்போது பால் வாங்கி வா.",
        "உங்கள் {company} ரீசார்ஜ் ரூ {amt} வெற்றிகரமாக முடிந்தது. நன்றி.",
        "{name}, நாளை காலை {time} மணிக்கு பஞ்சாயத்துக் கூட்டம். அவசியம் வாருங்கள்.",
        "உங்கள் மின் கட்டணம் ரூ {amt} பெறப்பட்டது. ரசீது எண் {last4}.",
        "{bank} ஒருபோதும் தொலைபேசியிலோ செய்தியிலோ உங்கள் PIN, OTP கேட்காது. கவனமாக இருங்கள்.",
        "{name} உங்களுக்கு ரூ {amt} அனுப்பியுள்ளார். UPI எண் {otp}.",
    ],
}

# ============================================================== Telugu
T["te"] = {
    "scam": [
        "ప్రియమైన కస్టమర్, మీ {bank} ఖాతా ఈరోజు బ్లాక్ అవుతుంది. వెంటనే కేవైసీ అప్‌డేట్ చేయండి: {link}",
        "మీ కరెంట్ కనెక్షన్ ఈ రాత్రి కట్ చేయబడుతుంది. వెంటనే అధికారికి ఫోన్ చేయండి {phone}",
        "అభినందనలు! మీరు లాటరీలో రూ {big} గెలుచుకున్నారు. బహుమతి పొందడానికి రూ {amt} రుసుము కట్టండి. {phone}",
        "నేను {bank} నుండి మాట్లాడుతున్నాను. ఇప్పుడు వచ్చిన OTP చెప్పండి, లేకపోతే ఖాతా బ్లాక్ అవుతుంది.",
        "నేను ఆర్మీ ఆఫీసర్‌ని. డబ్బు అందుకోవడానికి ఈ QR స్కాన్ చేసి UPI పిన్ వేయండి.",
        "మీ పీఎం కిసాన్ డబ్బు రూ {amt} ఆగిపోయింది. పొందడానికి ఈ లింక్‌లో కార్డు నంబర్, పిన్ ఇవ్వండి {short}",
        "ఇంటి నుండే రోజుకు రూ {amt} సంపాదించండి. చేరడానికి ఫీజు రూ {amt}. వాట్సాప్ {phone}",
        "మీ రుణం రూ {big} మంజూరైంది. ప్రాసెసింగ్ ఫీజు రూ {amt} కట్టండి.",
        "కస్టమర్ కేర్: AnyDesk యాప్ వేసి కోడ్ చెప్పండి, మీ డబ్బు తిరిగి వస్తుంది.",
        "మీ పేరు మీద వచ్చిన పార్సెల్‌లో చట్టవిరుద్ధమైన వస్తువులు ఉన్నాయి. అరెస్ట్ కాకుండా ఉండాలంటే వెంటనే రూ {big} పంపండి.",
        "మీ సిమ్ 24 గంటల్లో బ్లాక్ అవుతుంది. కేవైసీ కోసం ఇప్పుడే ఫోన్ చేయండి {phone}",
    ],
    "suspicious": [
        "5 నిమిషాల్లో రూ {big} వరకు పర్సనల్ లోన్, తక్కువ వడ్డీ. ఇప్పుడే అప్లై చేయండి {short}",
        "నమస్తే, పొరపాటున మీ ఖాతాకు రూ {amt} పంపాను. చూసి చెప్పండి. {phone}",
        "{company} భారీ సేల్! 80% వరకు తగ్గింపు, ఈరోజు మాత్రమే. {short}",
        "మీరు మా లక్కీ కస్టమర్‌గా ఎంపికయ్యారు. వివరాలకు ఫోన్ చేయండి {phone}",
        "పార్ట్ టైమ్ ఉద్యోగం కావాలా? రోజుకు 2 గంటలు, మంచి సంపాదన. YES అని జవాబివ్వండి.",
        "30 రోజుల్లో డబ్బు రెట్టింపు. కొత్త పెట్టుబడి పథకం. ఫోన్ చేయండి {phone}",
        "మీరు ఎవరు? నా నంబర్ ఎలా వచ్చింది? ఈ లింక్ తెరవండి {short}",
    ],
    "safe": [
        "{bank}: మీ ఖాతా XX{last4} నుండి రూ {amt} {date}న డెబిట్ అయింది. మీరు చేయకపోతే {tollfree}కు ఫోన్ చేయండి.",
        "{otp} మీ OTP. 10 నిమిషాలు చెల్లుతుంది. ఎవరితోనూ పంచుకోవద్దు. -{bank}",
        "మీ ఖాతా XX{last4}లో రూ {amt} జమ అయింది. -{bank}",
        "పీఎం కిసాన్ విడత రూ 2000 మీ ఖాతాలో జమ అయింది. వివరాలు: {safe}",
        "సాయంత్రం ఇంటికి వచ్చేటప్పుడు పాలు తీసుకురా.",
        "మీ {company} రీఛార్జ్ రూ {amt} విజయవంతమైంది. ధన్యవాదాలు.",
        "{name}, రేపు ఉదయం {time}కి పంచాయతీ సమావేశం ఉంది. తప్పకుండా రండి.",
        "మీ కరెంట్ బిల్లు రూ {amt} చెల్లించబడింది. రసీదు నంబర్ {last4}.",
        "{bank} ఎప్పుడూ ఫోన్ లేదా సందేశం ద్వారా మీ PIN, OTP అడగదు. జాగ్రత్తగా ఉండండి.",
        "{name} మీకు రూ {amt} పంపారు. UPI రెఫ్ {otp}.",
    ],
}

SENDERS = ["VM-SBIINB", "AD-HDFCBK", "JD-ICICIB", "BZ-PNBSMS", "VK-CANBNK", "+91 {phone}", "JX-AIRTEL"]


def augment(text: str) -> str:
    """Surface noise real messages carry: sender ids, casing, missing punctuation."""
    r = random.random()
    if r < 0.15:
        text = f"{random.choice(SENDERS).format(phone=phone())}: {text}"
    elif r < 0.22:
        text = text.upper() if text.isascii() else text
    if random.random() < 0.1:
        text = text.replace("।", "").replace(".", "")
    if random.random() < 0.06:
        text = text + " " + random.choice(["!!", "🙏", "👇", "⚠️"])
    return text


def generate() -> list[dict]:
    random.seed(SEED)
    rows = []
    for lang in ("hi", "en", "ta", "te"):
        for label in ("scam", "suspicious", "safe"):
            for i in range(PER_CLASS_PER_LANG):
                # A quarter of Hindi rows are romanised: "aapka account band ho jayega"
                # is how a lot of Hindi is actually typed on a phone keyboard.
                source = "hi_latin" if lang == "hi" and i % 4 == 0 else lang
                template = random.choice(T[source][label])
                rows.append({
                    "text": augment(fill(template, lang)),
                    "label": label,
                    "language": lang,
                    "script": "latin" if source == "hi_latin" else "native",
                })
    random.shuffle(rows)
    return rows


def main() -> None:
    rows = generate()
    # Deduplicate: template x slot collisions produce identical rows, and an
    # exact duplicate across train and val would inflate validation.
    seen, unique = set(), []
    for row in rows:
        if row["text"] not in seen:
            seen.add(row["text"])
            unique.append(row)
    split = int(len(unique) * 0.9)
    for name, part in (("scam_train.jsonl", unique[:split]), ("scam_val.jsonl", unique[split:])):
        with (HERE / name).open("w", encoding="utf-8") as handle:
            for row in part:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"wrote {name}: {len(part)} rows")
    n_templates = sum(len(v) for lang in T.values() for v in lang.values())
    print(f"{n_templates} templates, {len(rows) - len(unique)} duplicates dropped")


if __name__ == "__main__":
    main()
