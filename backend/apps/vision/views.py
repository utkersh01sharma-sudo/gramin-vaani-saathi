# -*- coding: utf-8 -*-
"""QR and banknote endpoints. Multipart upload in, a spoken sentence out.

The uploaded image is written to a temp file, read, and deleted before the
response is sent. Nothing is kept: a photo of a shop counter or a hand holding
money is not data this app has any reason to store.
"""
from __future__ import annotations

import os
import tempfile

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ai.registry import get_vision
from apps.banking.models import SandboxAccount

WARNINGS = {
    "no_qr_found": {"hi": "कोई QR कोड नहीं मिला। कोड को पास से, सीधा और साफ़ रोशनी में दिखाइए।",
                    "en": "No QR code found. Hold the code closer, straight, and in good light.",
                    "ta": "QR குறியீடு கிடைக்கவில்லை. அருகில், நேராக, நல்ல வெளிச்சத்தில் காட்டுங்கள்.",
                    "te": "QR కోడ్ కనిపించలేదు. దగ్గరగా, నేరుగా, మంచి వెలుతురులో చూపించండి."},
    "not_upi": {"hi": "यह पैसे भेजने वाला UPI कोड नहीं है।", "en": "This is not a UPI payment code.",
                "ta": "இது UPI பணம் செலுத்தும் குறியீடு அல்ல.", "te": "ఇది UPI చెల్లింపు కోడ్ కాదు."},
    "is_web_link": {"hi": "यह कोड एक वेबसाइट खोलता है। अनजान लिंक मत खोलिए।",
                    "en": "This code opens a website. Do not open unknown links.",
                    "ta": "இந்தக் குறியீடு ஒரு இணையதளத்தைத் திறக்கிறது. தெரியாத இணைப்புகளைத் திறக்காதீர்கள்.",
                    "te": "ఈ కోడ్ ఒక వెబ్‌సైట్ తెరుస్తుంది. తెలియని లింక్‌లు తెరవకండి."},
    "malformed_upi": {"hi": "इस कोड का UPI पता सही नहीं है।", "en": "The UPI address in this code is not valid.",
                      "ta": "இந்தக் குறியீட்டின் UPI முகவரி சரியில்லை.", "te": "ఈ కోడ్‌లోని UPI చిరునామా సరైనది కాదు."},
    "amount_prefilled": {"hi": "इस कोड में रकम पहले से भरी है। भेजने से पहले रकम ज़रूर जाँचिए।",
                         "en": "This code already has an amount filled in. Check the amount before paying.",
                         "ta": "இந்தக் குறியீட்டில் தொகை முன்பே நிரப்பப்பட்டுள்ளது. செலுத்தும் முன் சரிபாருங்கள்.",
                         "te": "ఈ కోడ్‌లో మొత్తం ముందే నింపబడింది. చెల్లించే ముందు సరిచూడండి."},
    "embedded_url": {"hi": "कोड के अंदर एक वेबसाइट का लिंक छिपा है। यह ठगी हो सकती है।",
                     "en": "A website link is hidden inside the code. This may be fraud.",
                     "ta": "குறியீட்டுக்குள் ஒரு இணைப்பு மறைந்துள்ளது. இது மோசடியாக இருக்கலாம்.",
                     "te": "కోడ్ లోపల ఒక లింక్ దాగి ఉంది. ఇది మోసం కావచ్చు."},
    "multiple_qr": {"hi": "एक से ज़्यादा QR कोड दिख रहे हैं। हो सकता है किसी ने दुकान के कोड पर अपना कोड चिपकाया हो।",
                    "en": "More than one QR code is visible. Someone may have stuck their own code over the shop's.",
                    "ta": "ஒன்றுக்கு மேற்பட்ட QR குறியீடுகள் தெரிகின்றன. கடையின் குறியீட்டின் மேல் வேறொருவர் ஒட்டியிருக்கலாம்.",
                    "te": "ఒకటి కంటే ఎక్కువ QR కోడ్‌లు కనిపిస్తున్నాయి. దుకాణం కోడ్‌పై ఎవరో వేరే కోడ్ అతికించి ఉండవచ్చు."},
    "possible_sticker": {"hi": "यह कोड ऊपर से चिपकाया हुआ लगता है। दुकानदार से नाम पूछकर मिलाइए।",
                         "en": "This code may have been stuck on top. Ask the shopkeeper their name and compare.",
                         "ta": "இந்தக் குறியீடு மேலே ஒட்டப்பட்டது போலத் தெரிகிறது. கடைக்காரரிடம் பெயர் கேட்டு ஒப்பிடுங்கள்.",
                         "te": "ఈ కోడ్ పైన అతికించినట్లు ఉంది. దుకాణదారుని పేరు అడిగి సరిచూడండి."},
    "unknown_payee": {"hi": "यह UPI पता हमारी सूची में नहीं है। पैसे भेजने से पहले नाम ज़रूर पूछिए।",
                      "en": "This UPI address is not in our directory. Confirm the name before paying.",
                      "ta": "இந்த UPI முகவரி எங்கள் பட்டியலில் இல்லை. செலுத்தும் முன் பெயரை உறுதி செய்யுங்கள்.",
                      "te": "ఈ UPI చిరునామా మా జాబితాలో లేదు. చెల్లించే ముందు పేరు నిర్ధారించుకోండి."},
    "name_mismatch": {"hi": "कोड पर लिखा नाम और खाते का असली नाम अलग है।",
                      "en": "The name written in the code is different from the account holder's name.",
                      "ta": "குறியீட்டில் உள்ள பெயரும் கணக்கின் உண்மையான பெயரும் வேறு.",
                      "te": "కోడ్‌లోని పేరు, ఖాతాదారు అసలు పేరు వేరు."},
}

QR_OK = {
    "hi": "यह कोड {name} का है।", "en": "This code belongs to {name}.",
    "ta": "இந்தக் குறியீடு {name} உடையது.", "te": "ఈ కోడ్ {name} ది.",
}
# Used when the VPA is not in the registry. The name inside a QR is free text
# that whoever printed it chose -- a fraudster's sticker carries the shop's own
# name. So an unverified name is reported as a claim, never as a fact.
QR_CLAIMS = {
    "hi": "यह कोड कहता है कि यह {name} का है, पर हम इसकी पुष्टि नहीं कर सके।",
    "en": "This code says it is for {name}, but we could not confirm that.",
    "ta": "இந்தக் குறியீடு {name} உடையது என்று சொல்கிறது, ஆனால் உறுதிப்படுத்த முடியவில்லை.",
    "te": "ఈ కోడ్ {name} ది అని చెబుతోంది, కానీ మేము నిర్ధారించలేకపోయాం.",
}
QR_AMOUNT = {
    "hi": " रकम {amount} रुपये।", "en": " Amount {amount} rupees.",
    "ta": " தொகை {amount} ரூபாய்.", "te": " మొత్తం {amount} రూపాయలు.",
}
NOTE_SAY = {
    "hi": "यह {d} रुपये का नोट लगता है।", "en": "This looks like a {d} rupee note.",
    "ta": "இது {d} ரூபாய் நோட்டு போலத் தெரிகிறது.", "te": "ఇది {d} రూపాయల నోటులా ఉంది.",
}
NOTE_UNSURE = {
    "hi": " पक्का नहीं है, खुद भी देख लीजिए।", "en": " I am not sure, please check it yourself.",
    "ta": " உறுதியாகத் தெரியவில்லை, நீங்களும் பாருங்கள்.", "te": " ఖచ్చితంగా తెలియదు, మీరూ చూడండి.",
}
NOTE_NONE = {
    "hi": "नोट पहचान नहीं पाया। नोट को सीधा, पूरा और रोशनी में दिखाइए।",
    "en": "I could not recognise a note. Show the whole note, flat, in good light.",
    "ta": "நோட்டை அடையாளம் காண முடியவில்லை. முழு நோட்டையும் நேராக வெளிச்சத்தில் காட்டுங்கள்.",
    "te": "నోటును గుర్తించలేకపోయాను. మొత్తం నోటును నేరుగా వెలుతురులో చూపించండి.",
}
NOTE_CONFIDENT = 0.75


def _lang(request) -> str:
    lang = request.data.get("language") or request.query_params.get("lang")
    if lang in settings.SUPPORTED_LANGUAGES:
        return lang
    profile = getattr(request.user, "profile", None)
    return getattr(profile, "language", None) or settings.DEFAULT_LANGUAGE


def _save_upload(request):
    upload = request.FILES.get("image")
    if upload is None:
        return None, Response({"detail": "image is required"}, status=status.HTTP_400_BAD_REQUEST)
    if upload.size > settings.VISION_MAX_UPLOAD_BYTES:
        return None, Response({"detail": "image too large"}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
    suffix = os.path.splitext(upload.name or "")[1][:8] or ".jpg"
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    for chunk in upload.chunks():
        handle.write(chunk)
    handle.close()
    return handle.name, None


def _name_matches(written: str, registered: str) -> bool:
    a, b = written.strip().lower(), registered.strip().lower()
    return not a or a in b or b in a


@extend_schema(tags=["vision"])
class QRView(APIView):
    """Decode a UPI QR from a photo, check it, and say who it pays."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        path, error = _save_upload(request)
        if error:
            return error
        try:
            result = get_vision().read_qr(path)
        except ValueError:
            return Response({"detail": "not an image"}, status=status.HTTP_400_BAD_REQUEST)
        finally:
            os.unlink(path)

        lang = _lang(request)
        warnings = list(result.warnings)
        registered_name = ""
        if result.is_valid_upi:
            account = SandboxAccount.objects.select_related("user").filter(vpa=result.payee_vpa).first()
            if account is None:
                warnings.append("unknown_payee")
            else:
                registered_name = account.user.get_full_name() or account.user.first_name or account.user.username
                if not _name_matches(result.payee_name, registered_name):
                    warnings.append("name_mismatch")

        name = registered_name or result.payee_name or result.payee_vpa
        sentences = []
        if result.is_valid_upi and name:
            template = QR_OK if registered_name else QR_CLAIMS
            sentences.append(template[lang].format(name=name))
            if result.amount is not None:
                sentences.append(QR_AMOUNT[lang].format(amount=f"{result.amount:g}").strip())
        sentences += [WARNINGS[w][lang] for w in warnings if w in WARNINGS]

        danger = {"embedded_url", "multiple_qr", "possible_sticker", "name_mismatch", "malformed_upi"}
        caution = {"unknown_payee", "amount_prefilled", "not_upi", "is_web_link"}
        level = ("danger" if danger & set(warnings) else
                 "caution" if caution & set(warnings) or not result.is_valid_upi else "ok")
        return Response({
            "level": level,
            "payee_vpa": result.payee_vpa,
            "payee_name_in_code": result.payee_name,
            "payee_name_registered": registered_name,
            "amount": result.amount,
            "is_valid_upi": result.is_valid_upi,
            "tamper_score": result.tamper_score,
            "warnings": warnings,
            "reply_text": " ".join(sentences),
            "language": lang,
            # Lets the client offer "pay this person" through the normal
            # confirm-then-execute path. It never pays from here.
            "can_pay": result.is_valid_upi and bool(registered_name) and level != "danger",
        })


@extend_schema(tags=["vision"])
class NoteView(APIView):
    """Recognise a banknote's denomination from a photo."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        path, error = _save_upload(request)
        if error:
            return error
        vision = get_vision()
        try:
            pred = vision.identify_note(path)
        except ValueError:
            return Response({"detail": "not an image"}, status=status.HTTP_400_BAD_REQUEST)
        finally:
            os.unlink(path)

        lang = _lang(request)
        if not pred.is_note or pred.denomination is None:
            reply = NOTE_NONE[lang]
        else:
            reply = NOTE_SAY[lang].format(d=pred.denomination)
            if pred.confidence < NOTE_CONFIDENT:
                reply += NOTE_UNSURE[lang]
        return Response({
            "denomination": pred.denomination,
            "confidence": pred.confidence,
            "is_note": pred.is_note,
            "confident": pred.confidence >= NOTE_CONFIDENT,
            "backend": getattr(vision, "note_backend", "unknown"),
            "reply_text": reply,
            "language": lang,
        })
