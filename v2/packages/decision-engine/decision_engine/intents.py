"""The rule set — per-intent trigger patterns, in Arabic and English, written in the same
normalized form `rules.normalize` produces. Each pattern carries a weight; the classifier
sums matched weights per intent and the highest total wins. Specific multi-word phrases
score higher than generic single words, so "extract obligations" beats a bare "what are".

This is the whole "AI" of the MVP: deterministic, inspectable regex rules. No model.
"""

from __future__ import annotations

import re

from decision_engine.models import Intent

# Each entry: (raw pattern, weight). English patterns use \b; Arabic patterns don't
# (Arabic has no ASCII word boundaries). Patterns are matched against normalized text.
_RAW: dict[Intent, list[tuple[str, float]]] = {
    Intent.COMPARISON: [
        (r"\bcompare\b", 2.5),
        (r"\bcomparison\b", 2.5),
        (r"\b(?:vs\.?|versus)\b", 2.2),
        (r"\bdifferences? between\b", 2.5),
        (r"قارن", 2.5),
        (r"مقارنه", 2.5),
        (r"الفرق بين|الفروق بين", 2.5),
    ],
    Intent.SUMMARIZATION: [
        (r"\bsummar(?:y|ies|ize|ise|ization|isation)\b", 2.5),
        (r"\btl;?dr\b", 2.0),
        (r"\bgive me a (?:brief|short) overview\b", 1.8),
        (r"لخص|تلخيص|ملخص|اختصر", 2.5),
    ],
    Intent.EXPLANATION: [
        (r"\bexplain\b", 2.5),
        (r"\bdescribe\b", 2.0),
        (r"\bhow does\b", 1.6),
        (r"\bwhat does .{1,40} mean\b", 2.2),
        (r"\bwhy\b", 1.0),
        (r"اشرح|وضح|اوضح|فسر", 2.5),
        (r"ما معني", 2.0),
        (r"كيف", 1.2),
        (r"لماذا", 1.2),
    ],
    Intent.LOOKUP: [
        (r"\bwhat (?:is|are)\b", 1.6),
        (r"\bwhat's\b", 1.4),
        (r"\bwhere does it say\b", 2.2),
        (r"\bdefine\b|\bdefinition of\b", 1.8),
        (r"\blist\b", 1.0),
        (r"ما هي|ما هو|ماهي|ماهو", 1.6),
        (r"اين", 1.5),
        (r"عرف|تعريف", 1.8),
        (r"اذكر", 1.2),
    ],
    Intent.OBLIGATION_EXTRACTION: [
        (r"\bobligations?\b", 2.5),
        (r"\bextract[a-z ]{0,15}obligation", 3.0),
        (r"\brequirements? under\b", 1.6),
        (r"الالتزامات|التزامات", 2.6),
        (r"استخرج[^\n]{0,20}(?:التزام|الالتزامات)", 3.0),
    ],
    Intent.RISK_ANALYSIS: [
        (r"\brisk (?:analysis|assessment)\b", 3.0),
        (r"\banalyz(?:e|se)[a-z ]{0,15}risk", 2.6),
        (r"\bassess[a-z ]{0,15}risk", 2.6),
        (r"\brisks?\b", 1.2),
        (r"تحليل المخاطر|تقييم المخاطر", 3.0),
        (r"حلل المخاطر", 2.8),
        (r"المخاطر|مخاطر", 1.6),
    ],
    Intent.GAP_ASSESSMENT: [
        (r"\bgap (?:analysis|assessment)\b", 3.0),
        (r"\bgaps?\b", 1.8),
        (r"\bwhat'?s missing\b|\bwhat is missing\b", 2.5),
        (r"\b(?:not|isn'?t|aren'?t|doesn'?t|don'?t)\s+cover(?:ed|s|ing)?\b", 2.7),
        (r"\buncovered\b", 2.4),
        (r"الفجوه|الفجوات|تحليل الفجوه", 3.0),
        (r"ما (?:الذي )?ينقص", 2.5),
        (r"لا تغطي|غير مغطاه|غير مغطي", 2.6),
    ],
    Intent.COMPLIANCE_REVIEW: [
        (r"\bcompliance review\b", 3.0),
        (r"\b(?:are|am) (?:we|i)[a-z ]{0,10}compliant\b", 3.0),
        (r"\bcompliant with\b|\bcomply with\b", 2.6),
        (r"\bcompliance\b", 1.6),
        (r"الامتثال", 2.0),
        (r"هل نحن (?:ممتثلون|متوافقون)|هل نمتثل", 3.0),
        (r"متوافق مع|التوافق مع", 2.0),
        (r"مراجعه الامتثال", 3.0),
    ],
    Intent.POLICY_REVIEW: [
        (r"\bpolicy review\b|\breview[a-z ]{0,30}polic", 3.0),
        (r"\bis this policy\b", 3.0),
        (r"\b(?:assess|evaluate|critique|check)[a-z ]{0,30}polic", 2.5),
        (r"هل هذه السياسه", 3.0),
        (r"(?:راجع|مراجعه|قيم|تقييم)[^\n]{0,30}سياسه", 3.0),
    ],
    Intent.CONTROL_MAPPING: [
        (r"\bcontrol mapping\b", 3.0),
        (r"\bmap[a-z ]{0,15}controls?\b", 2.6),
        (r"\bwhich[a-z0-9 ]{0,25}controls?\b", 2.5),
        (r"\bcontrols? (?:for|that address|address(?:es)?|covering|related to|map to)\b", 2.2),
        (r"ربط الضوابط|خريطه الضوابط", 2.8),
        (r"اي ضابط|اي الضوابط|اي من الضوابط", 2.5),
    ],
    Intent.CROSS_FRAMEWORK_MAPPING: [
        (r"\bcross[- ]framework\b", 3.0),
        (r"\bmapping between\b", 2.5),
        (r"الربط بين[^\n]{0,25}(?:الاطر|المعايير|الانظمه)", 3.0),
    ],
    Intent.DOCUMENT_ANALYSIS: [
        (r"\banalyz(?:e|se)[a-z ]{0,10}(?:this|the attached|the uploaded)?[a-z ]{0,5}document\b", 3.0),
        (r"\breview (?:this|the attached|the uploaded) document\b", 2.6),
        (r"\banalyz(?:e|se) (?:this|the) (?:file|doc)\b", 2.6),
        (r"حلل[^\n]{0,15}(?:المستند|الوثيقه|الملف)", 3.0),
        (r"تحليل[^\n]{0,15}(?:المستند|الوثيقه)", 2.8),
    ],
    Intent.CONVERSATION: [
        (r"\b(?:hi|hello|hey|thanks|thank you|good (?:morning|evening))\b", 2.0),
        (r"\bwho are you\b|\bwhat can you do\b|\bwhat are you\b|\bhelp me\b|^help$", 2.0),
        (r"مرحبا|السلام عليكم|اهلا|شكرا|من انت|ماذا تستطيع|كيف حالك|مساعده", 2.0),
    ],
}

INTENT_PATTERNS: dict[Intent, list[tuple[re.Pattern[str], float]]] = {
    intent: [(re.compile(p), w) for p, w in patterns] for intent, patterns in _RAW.items()
}

# A "mapping" cue that, combined with two or more named frameworks, promotes a request to
# cross_framework_mapping (handled in the classifier).
MAPPING_CUE = re.compile(r"\bmap(?:ping|ped)?\b|ربط|خريطه|الربط")
