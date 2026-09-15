"""
advice_engine.py

Farmer-facing advice helpers, tailored to this project's actual data shapes:

  - fertility labels are the strings "Low" / "Medium" / "High" (see
    backend/models/class_names.joblib)
  - FEATURES = ["latitude", "longitude", "ph", "moisture", "nitrogen", "cec"]
  - explain() in app.py already returns {"shap": [{"feature":..., "value":...}, ...]}
  - predict_soil() in app.py already returns model_agreement (bool) and
    lgb_prediction / cat_prediction (strings)

Multilingual: English, Hindi (hi) and Kannada (kn).

Translation is TEMPLATE-BASED, not whole-sentence lookup. Every message is
assembled from a format string plus parameters, so each language defines the
same set of template keys. This is the maintainable approach — a whole-sentence
lookup table breaks the moment a number or feature name inside the sentence
changes.

To add another language, add one entry to each of LANG_NAMES, FERTILITY_LABELS,
FEATURE_VOCAB, WORDS and TEMPLATES. Any key you leave out falls back to English
rather than crashing or showing a blank.

No new dependencies. Import into app.py with:

    import advice_engine
"""

from __future__ import annotations

DEFAULT_LANG = "en"
SUPPORTED_LANGS = ("en", "hi", "kn")

LANG_NAMES = {"en": "English", "hi": "हिंदी", "kn": "ಕನ್ನಡ"}

# The model emits these English class names; each language maps them to a word
# a farmer actually reads.
FERTILITY_LABELS = {
    "en": {"Low": "Low", "Medium": "Medium", "High": "High"},
    "hi": {"Low": "कम", "Medium": "मध्यम", "High": "अधिक"},
    "kn": {"Low": "ಕಡಿಮೆ", "Medium": "ಮಧ್ಯಮ", "High": "ಹೆಚ್ಚು"},
}

# Fixed vocabulary so the same soil property is always called the same thing.
FEATURE_VOCAB = {
    "en": {
        "ph": "acidity (pH)",
        "moisture": "soil moisture",
        "nitrogen": "nitrogen level",
        "cec": "nutrient-holding capacity (CEC)",
        "latitude": "location",
        "longitude": "location",
    },
    "hi": {
        "ph": "अम्लता (pH)",
        "moisture": "मिट्टी की नमी",
        "nitrogen": "नाइट्रोजन स्तर",
        "cec": "पोषक तत्व धारण क्षमता (CEC)",
        "latitude": "स्थान",
        "longitude": "स्थान",
    },
    "kn": {
        "ph": "ಆಮ್ಲೀಯತೆ (pH)",
        "moisture": "ಮಣ್ಣಿನ ತೇವಾಂಶ",
        "nitrogen": "ಸಾರಜನಕ ಮಟ್ಟ",
        "cec": "ಪೋಷಕಾಂಶ ಹಿಡಿದಿಡುವ ಸಾಮರ್ಥ್ಯ (CEC)",
        "latitude": "ಸ್ಥಳ",
        "longitude": "ಸ್ಥಳ",
    },
}

# Small connective words used when building lists like "low nitrogen and high pH".
WORDS = {
    "en": {"low": "low", "high": "high", "and": " and "},
    "hi": {"low": "कम", "high": "अधिक", "and": " और "},
    "kn": {"low": "ಕಡಿಮೆ", "high": "ಹೆಚ್ಚು", "and": " ಮತ್ತು "},
}

TEMPLATES = {
    "en": {
        "explain": "Your soil was rated {label} mainly because of {drivers}.",
        "minor_one": " {names} was not a major factor this time.",
        "minor_many": " {names} were not major factors this time.",
        "no_signal": "Your soil was rated {label}, but we don't have enough signal to explain why.",
        "agree": "Both models agree: your soil fertility is {label}.",
        "disagree": "Our two models disagree: one says {a}, the other says {b}. "
                    "Treat this as a borderline result — a manual soil test is a good idea before acting on it.",
        "fert_wait": "Heavy rain (~{mm}mm) is expected in the next 24 hours. "
                     "Applying fertilizer now risks washing nutrients away — consider waiting until after the rain.",
        "fert_go": "No heavy rain expected soon — this is a reasonable time to apply fertilizer.",
        "fert_unknown": "Rain forecast unavailable — check conditions before fertilizing.",
        "irr_go": "Soil moisture is low ({moisture}%) and no rain is expected in the next 48 hours. Irrigate today.",
        "irr_hold_rain": "Rain is expected soon — you can hold off on irrigating.",
        "irr_hold_ok": "Moisture levels look adequate for now — no irrigation needed today.",
        "irr_unknown": "Rain forecast unavailable — check soil moisture directly before irrigating.",
    },
    "hi": {
        "explain": "आपकी मिट्टी की उर्वरता {label} आंकी गई है — मुख्य रूप से {drivers} के कारण।",
        "minor_one": " इस बार {names} कोई बड़ा कारण नहीं था।",
        "minor_many": " इस बार {names} बड़े कारण नहीं थे।",
        "no_signal": "आपकी मिट्टी की उर्वरता {label} आंकी गई है, लेकिन कारण बताने के लिए पर्याप्त जानकारी नहीं है।",
        "agree": "दोनों मॉडल सहमत हैं: आपकी मिट्टी की उर्वरता {label} है।",
        "disagree": "दोनों मॉडल असहमत हैं: एक कहता है {a}, दूसरा कहता है {b}। "
                    "इसे सीमावर्ती परिणाम मानें — कोई कदम उठाने से पहले मिट्टी की जांच कराना बेहतर है।",
        "fert_wait": "अगले 24 घंटों में भारी बारिश (~{mm}mm) की संभावना है। "
                     "अभी खाद डालने से पोषक तत्व बह सकते हैं — बारिश के बाद तक इंतज़ार करें।",
        "fert_go": "जल्द भारी बारिश की संभावना नहीं है — खाद डालने के लिए यह उपयुक्त समय है।",
        "fert_unknown": "बारिश का पूर्वानुमान उपलब्ध नहीं है — खाद डालने से पहले मौसम की जांच करें।",
        "irr_go": "मिट्टी की नमी कम है ({moisture}%) और अगले 48 घंटों में बारिश की संभावना नहीं है। आज सिंचाई करें।",
        "irr_hold_rain": "जल्द बारिश की संभावना है — सिंचाई टाल सकते हैं।",
        "irr_hold_ok": "नमी का स्तर फिलहाल ठीक है — आज सिंचाई की आवश्यकता नहीं।",
        "irr_unknown": "बारिश का पूर्वानुमान उपलब्ध नहीं है — सिंचाई से पहले मिट्टी की नमी जांचें।",
    },
    "kn": {
        "explain": "ನಿಮ್ಮ ಮಣ್ಣಿನ ಫಲವತ್ತತೆ {label} ಎಂದು ಅಂದಾಜಿಸಲಾಗಿದೆ — ಮುಖ್ಯವಾಗಿ {drivers} ಕಾರಣದಿಂದ.",
        "minor_one": " ಈ ಬಾರಿ {names} ಪ್ರಮುಖ ಕಾರಣವಾಗಿರಲಿಲ್ಲ.",
        "minor_many": " ಈ ಬಾರಿ {names} ಪ್ರಮುಖ ಕಾರಣಗಳಾಗಿರಲಿಲ್ಲ.",
        "no_signal": "ನಿಮ್ಮ ಮಣ್ಣಿನ ಫಲವತ್ತತೆ {label} ಎಂದು ಅಂದಾಜಿಸಲಾಗಿದೆ, ಆದರೆ ಕಾರಣ ವಿವರಿಸಲು ಸಾಕಷ್ಟು ಮಾಹಿತಿ ಇಲ್ಲ.",
        "agree": "ಎರಡೂ ಮಾದರಿಗಳು ಒಪ್ಪುತ್ತವೆ: ನಿಮ್ಮ ಮಣ್ಣಿನ ಫಲವತ್ತತೆ {label}.",
        "disagree": "ಎರಡು ಮಾದರಿಗಳು ಭಿನ್ನಾಭಿಪ್ರಾಯ ಹೊಂದಿವೆ: ಒಂದು {a} ಎನ್ನುತ್ತದೆ, ಇನ್ನೊಂದು {b} ಎನ್ನುತ್ತದೆ. "
                    "ಇದನ್ನು ಗಡಿರೇಖೆಯ ಫಲಿತಾಂಶವೆಂದು ಪರಿಗಣಿಸಿ — ಕ್ರಮ ಕೈಗೊಳ್ಳುವ ಮೊದಲು ಮಣ್ಣಿನ ಪರೀಕ್ಷೆ ಮಾಡಿಸುವುದು ಉತ್ತಮ.",
        "fert_wait": "ಮುಂದಿನ 24 ಗಂಟೆಗಳಲ್ಲಿ ಭಾರೀ ಮಳೆ (~{mm}mm) ನಿರೀಕ್ಷಿಸಲಾಗಿದೆ. "
                     "ಈಗ ಗೊಬ್ಬರ ಹಾಕಿದರೆ ಪೋಷಕಾಂಶಗಳು ಕೊಚ್ಚಿ ಹೋಗಬಹುದು — ಮಳೆಯ ನಂತರ ಹಾಕುವುದು ಉತ್ತಮ.",
        "fert_go": "ಶೀಘ್ರದಲ್ಲಿ ಭಾರೀ ಮಳೆ ನಿರೀಕ್ಷಿಸಿಲ್ಲ — ಗೊಬ್ಬರ ಹಾಕಲು ಇದು ಸೂಕ್ತ ಸಮಯ.",
        "fert_unknown": "ಮಳೆಯ ಮುನ್ಸೂಚನೆ ಲಭ್ಯವಿಲ್ಲ — ಗೊಬ್ಬರ ಹಾಕುವ ಮೊದಲು ಹವಾಮಾನ ಪರಿಶೀಲಿಸಿ.",
        "irr_go": "ಮಣ್ಣಿನ ತೇವಾಂಶ ಕಡಿಮೆ ಇದೆ ({moisture}%) ಮತ್ತು ಮುಂದಿನ 48 ಗಂಟೆಗಳಲ್ಲಿ ಮಳೆ ನಿರೀಕ್ಷಿಸಿಲ್ಲ. ಇಂದು ನೀರುಣಿಸಿ.",
        "irr_hold_rain": "ಶೀಘ್ರದಲ್ಲಿ ಮಳೆ ನಿರೀಕ್ಷಿಸಲಾಗಿದೆ — ನೀರುಣಿಸುವುದನ್ನು ಮುಂದೂಡಬಹುದು.",
        "irr_hold_ok": "ಸದ್ಯಕ್ಕೆ ತೇವಾಂಶ ಮಟ್ಟ ಸರಿಯಾಗಿದೆ — ಇಂದು ನೀರುಣಿಸುವ ಅಗತ್ಯವಿಲ್ಲ.",
        "irr_unknown": "ಮಳೆಯ ಮುನ್ಸೂಚನೆ ಲಭ್ಯವಿಲ್ಲ — ನೀರುಣಿಸುವ ಮೊದಲು ಮಣ್ಣಿನ ತೇವಾಂಶ ಪರಿಶೀಲಿಸಿ.",
    },
}


def normalize_lang(lang: str | None) -> str:
    """Accept 'hi', 'HI', 'hi-IN' etc; fall back to English for anything unknown."""
    if not lang:
        return DEFAULT_LANG
    code = str(lang).strip().lower().replace("_", "-").split("-")[0]
    return code if code in SUPPORTED_LANGS else DEFAULT_LANG


def _t(lang: str, key: str) -> str:
    """Template lookup with an English fallback, so a missing key never blanks the UI."""
    return TEMPLATES.get(lang, {}).get(key) or TEMPLATES[DEFAULT_LANG][key]


def _word(lang: str, key: str) -> str:
    return WORDS.get(lang, {}).get(key) or WORDS[DEFAULT_LANG][key]


def _readable(feature: str, lang: str) -> str:
    vocab = FEATURE_VOCAB.get(lang, {})
    return vocab.get(feature.lower()) or FEATURE_VOCAB[DEFAULT_LANG].get(
        feature.lower(), feature.replace("_", " ")
    )


def translate_fertility(label: str, lang: str) -> str:
    """Map the model's English class name ('Low'/'Medium'/'High') into `lang`."""
    table = FERTILITY_LABELS.get(lang, {})
    return table.get(label) or FERTILITY_LABELS[DEFAULT_LANG].get(label, label)


def explain_prediction(fertility_label: str, shap_items: list[dict], top_n: int = 2, lang: str = DEFAULT_LANG) -> str:
    """
    fertility_label: "Low"/"Medium"/"High" (result["fertility"] from app.py)
    shap_items: the list app.py's explain() already builds.
    """
    lang = normalize_lang(lang)
    label = translate_fertility(fertility_label, lang)

    if not shap_items:
        return _t(lang, "no_signal").format(label=label)

    ranked = sorted(shap_items, key=lambda x: -abs(x.get("value", 0)))
    top = [x for x in ranked if x.get("value", 0) != 0][:top_n]
    if not top:
        return _t(lang, "no_signal").format(label=label)

    joiner = _word(lang, "and")
    drivers = joiner.join(
        f"{_word(lang, 'low' if x['value'] < 0 else 'high')} {_readable(x['feature'], lang)}"
        for x in top
    )
    sentence = _t(lang, "explain").format(label=label, drivers=drivers)

    named = {x["feature"] for x in top}
    minor = [x for x in ranked if x["feature"] not in named]
    if minor:
        names = [_readable(x["feature"], lang) for x in minor[:2]]
        joined = joiner.join(names)
        if lang == "en":
            # NB: don't use str.capitalize() — it lowercases the rest and would
            # turn "(CEC)" into "(cec)". Indic scripts have no case at all.
            joined = joined[0].upper() + joined[1:]
        key = "minor_one" if len(names) == 1 else "minor_many"
        sentence += _t(lang, key).format(names=joined)

    return sentence


def agreement_message(model_agreement: bool, lgb_prediction: str, cat_prediction: str, lang: str = DEFAULT_LANG) -> str:
    """Plain-language wrapper around the model_agreement bool app.py already computes."""
    lang = normalize_lang(lang)
    if model_agreement:
        return _t(lang, "agree").format(label=translate_fertility(lgb_prediction, lang))
    return _t(lang, "disagree").format(
        a=translate_fertility(lgb_prediction, lang),
        b=translate_fertility(cat_prediction, lang),
    )


# Thresholds — tune these for your region/crops.
RAIN_WASHOUT_THRESHOLD_MM = 10.0
DRY_SPELL_THRESHOLD_MM = 2.0


def get_timing_advice(
    action: str,
    precipitation_next_24h_mm: float | None,
    precipitation_next_48h_mm: float | None,
    soil_moisture_pct: float | None = None,
    lang: str = DEFAULT_LANG,
) -> dict:
    """
    action: "fertilize" | "irrigate"
    Returns {"recommendation": "go"|"wait"|"hold_off"|"unknown", "message": str}
    A missing forecast yields a clearly-labelled "unknown" rather than a guess.
    """
    lang = normalize_lang(lang)
    action = action.lower()

    if action == "fertilize":
        if precipitation_next_24h_mm is None:
            return {"recommendation": "unknown", "message": _t(lang, "fert_unknown")}
        if precipitation_next_24h_mm >= RAIN_WASHOUT_THRESHOLD_MM:
            return {
                "recommendation": "wait",
                "message": _t(lang, "fert_wait").format(mm=f"{precipitation_next_24h_mm:.0f}"),
            }
        return {"recommendation": "go", "message": _t(lang, "fert_go")}

    if action == "irrigate":
        if precipitation_next_48h_mm is None:
            return {"recommendation": "unknown", "message": _t(lang, "irr_unknown")}
        dry_spell = precipitation_next_48h_mm < DRY_SPELL_THRESHOLD_MM
        if soil_moisture_pct is not None and soil_moisture_pct < 20 and dry_spell:
            return {
                "recommendation": "go",
                "message": _t(lang, "irr_go").format(moisture=f"{soil_moisture_pct:.0f}"),
            }
        if not dry_spell:
            return {"recommendation": "hold_off", "message": _t(lang, "irr_hold_rain")}
        return {"recommendation": "hold_off", "message": _t(lang, "irr_hold_ok")}

    raise ValueError(f"Unknown action: {action!r}")