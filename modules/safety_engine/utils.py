"""
utils.py
--------
Shared helper functions used by every checker.

Two jobs:
  1. Load the JSON datasets from data/medical/ (once, not on every request).
  2. Clean up messy medicine names into clean generic names.

Why job 2 matters: Keshav's OCR will hand you strings like "Dolo 650",
"TAB. AUGMENTIN 625 DUO" or "ibuprofen 400mg". Your dataset only knows
"Paracetamol", "Amoxicillin" and "Ibuprofen". Something has to translate.
That something is this file.
"""

import json          # lets Python read .json files into dictionaries
import re            # "regular expressions" - used for pattern-based text cleaning
from pathlib import Path   # a modern, safe way to build file paths


# ---------------------------------------------------------------------------
# STEP 1: Work out where data/medical/ lives
# ---------------------------------------------------------------------------

# __file__ is this file's own path: BharatRx/modules/safety_engine/utils.py
# .resolve() turns it into a full absolute path.
# .parents[0] = safety_engine/   .parents[1] = modules/   .parents[2] = BharatRx/
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Now build the path to the dataset folder: BharatRx/data/medical
DATA_DIR = PROJECT_ROOT / "data" / "medical"


def load_dataset(filename):
    """Open one JSON file from data/medical/ and return it as a Python dict."""
    path = DATA_DIR / filename                      # e.g. .../data/medical/drug_interactions.json
    with open(path, "r", encoding="utf-8") as f:    # open the file for reading
        return json.load(f)                         # convert JSON text -> Python dictionary


# ---------------------------------------------------------------------------
# STEP 2: Load every dataset ONCE when this module is first imported
# ---------------------------------------------------------------------------
# This is important for speed. If you loaded the files inside each function,
# you would re-read the disk on every single API request. Loading here means
# it happens once when the server starts.

DRUG_INTERACTIONS = load_dataset("drug_interactions.json")
DISEASE_RULES = load_dataset("disease_rules.json")
ALLERGY_DATA = load_dataset("allergy_rules.json")
BRAND_GENERIC = load_dataset("brand_generic.json")
CONTEXT_RULES = load_dataset("patient_context_rules.json")
DRUG_CLASSES = load_dataset("drug_classes.json")
CLASS_INTERACTIONS = load_dataset("class_interactions.json")

# Build a reverse index once: drug name -> list of classes it belongs to.
# Without this, finding "which classes is Ibuprofen in?" would mean scanning
# all 39 class lists on every single lookup.
_DRUG_TO_CLASSES = {}
for _cls, _members in DRUG_CLASSES.items():
    if _cls.startswith("_"):
        continue
    for _m in _members:
        _DRUG_TO_CLASSES.setdefault(_m.lower(), []).append(_cls)


def classes_of(drug):
    """Return every class this generic drug belongs to (may be more than one)."""
    return _DRUG_TO_CLASSES.get(str(drug).strip().lower(), [])


def is_known_drug(drug):
    """True if we have ANY knowledge of this drug at all."""
    name = str(drug).strip().lower()
    if name in _DRUG_TO_CLASSES:
        return True
    for d in (DRUG_INTERACTIONS, DISEASE_RULES):
        for k, v in d.items():
            if k.startswith("_"):
                continue
            if k.lower() == name:
                return True
            if isinstance(v, dict) and any(ik.lower() == name for ik in v):
                return True
    for members in ALLERGY_GROUPS.values():
        if any(m.lower() == name for m in members):
            return True
    return False

# Pull the two sections out of the allergy file for easier access later
ALLERGY_GROUPS = ALLERGY_DATA["allergy_groups"]
CROSS_REACTIVITY = ALLERGY_DATA["cross_reactivity"]


# ---------------------------------------------------------------------------
# STEP 3: Clean a raw medicine string
# ---------------------------------------------------------------------------

# Words that appear on Indian medicine strips but are not part of the name.
# We strip these out so "AUGMENTIN 625 DUO" becomes "Augmentin".
NOISE_WORDS = {
    "tab", "tabs", "tablet", "tablets", "cap", "caps", "capsule", "capsules",
    "syr", "syrup", "inj", "injection", "susp", "suspension", "drops",
    "mg", "ml", "gm", "g", "mcg", "iu",
    "duo", "dt", "ds", "sr", "xr", "er", "md", "od", "bd", "tds", "hs", "sos",
    "forte", "plus", "advance", "cv", "kid", "junior",
}


def clean_name(raw):
    """
    Turn a messy medicine string into a tidy name.

    "Dolo 650"            -> "Dolo"
    "TAB. IBUPROFEN 400MG" -> "Ibuprofen"
    "augmentin 625 duo"    -> "Augmentin"
    """
    if not raw:                      # guard against None or empty string
        return ""

    text = str(raw).lower()          # work in lowercase so comparisons are easy

    # Replace anything that is not a letter, digit, + or space with a space.
    # This kills full stops, hyphens, brackets, slashes etc.
    text = re.sub(r"[^a-z0-9+\s-]", " ", text)

    # Glue a number to the unit next to it so "400 mg" is treated as one token
    text = re.sub(r"(\d)\s*(mg|ml|gm|mcg|g)\b", r"\1\2", text)

    words = []
    for word in text.split():                  # split on spaces into individual words
        if word in NOISE_WORDS:                # skip "tab", "mg", "duo" etc.
            continue
        if re.fullmatch(r"\d+[a-z]*", word):   # skip pure numbers like "650" or "400mg"
            continue
        words.append(word)

    # Re-join and Title Case it, so "ibuprofen" -> "Ibuprofen"
    return " ".join(words).title().strip()


# ---------------------------------------------------------------------------
# STEP 4: Convert a cleaned name into its GENERIC name(s)
# ---------------------------------------------------------------------------

# Build a lookup where the KEY is the cleaned brand name.
# The dataset has "Dolo 650" as a key; clean_name() turns that into "Dolo",
# so we pre-clean all the keys here and everything matches later.
_BRAND_LOOKUP = {}
for brand, generic in BRAND_GENERIC.items():
    if brand.startswith("_"):            # skip the "_comment" line in the JSON
        continue
    _BRAND_LOOKUP[clean_name(brand)] = generic


def to_generics(raw):
    """
    Take one raw medicine string and return a LIST of generic names.

    A list, not a single string, because Indian combination medicines
    contain more than one drug:

        "Dolo 650"   -> ["Paracetamol"]
        "Combiflam"  -> ["Ibuprofen", "Paracetamol"]
        "Augmentin"  -> ["Amoxicillin", "Clavulanic Acid"]
        "Ibuprofen"  -> ["Ibuprofen"]   (already generic, passed through)
    """
    name = clean_name(raw)
    if not name:
        return []

    # If the doctor wrote "Amoxicillin + Clavulanic Acid", split on the plus sign
    if "+" in name:
        parts = [p.strip() for p in name.split("+") if p.strip()]
        results = []
        for part in parts:
            results.extend(to_generics(part))   # handle each half separately
        return unique(results)

    # Is this a known Indian brand?
    mapped = _BRAND_LOOKUP.get(name)
    if mapped is None:
        return [name]                 # not a brand we know - assume it is already generic
    if isinstance(mapped, list):      # combination product
        return list(mapped)
    return [mapped]                   # single-ingredient brand


def unique(items):
    """Remove duplicates from a list while keeping the original order."""
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def match(a, b):
    """
    Compare two names ignoring case and spacing.
    "kidney disease" and "Kidney Disease" should count as the same thing.
    """
    return str(a).strip().lower() == str(b).strip().lower()


def find_key(dictionary, wanted):
    """
    Look up a key in a dictionary, ignoring case.

    Needed because Namita's chatbot might send "kidney disease" (lowercase)
    while your dataset says "Kidney Disease". A plain dictionary lookup
    would miss it; this does not.
    """
    for key in dictionary:
        if match(key, wanted):
            return key
    return None
