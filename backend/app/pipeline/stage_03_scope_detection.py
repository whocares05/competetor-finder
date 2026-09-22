"""Pipeline Stage 03: Scope and Region Detection"""
import re
from typing import Optional

# Comprehensive set of recognized countries and common aliases
KNOWN_COUNTRIES = {
    "afghanistan", "albania", "algeria", "andorra", "angola", "argentina", "armenia",
    "australia", "austria", "azerbaijan", "bahamas", "bahrain", "bangladesh", "barbados",
    "belarus", "belgium", "belize", "benin", "bhutan", "bolivia", "bosnia", "botswana",
    "brazil", "brunei", "bulgaria", "burkina faso", "burundi", "cambodia", "cameroon",
    "canada", "chile", "china", "colombia", "costa rica", "croatia", "cuba", "cyprus",
    "czech republic", "czechia", "denmark", "dominican republic", "ecuador", "egypt",
    "estonia", "ethiopia", "fiji", "finland", "france", "georgia", "germany", "ghana",
    "greece", "guatemala", "haiti", "honduras", "hong kong", "hungary", "iceland", "india",
    "indonesia", "iran", "iraq", "ireland", "israel", "italy", "jamaica", "japan",
    "jordan", "kazakhstan", "kenya", "kuwait", "latvia", "lebanon", "lithuania",
    "luxembourg", "malaysia", "maldives", "malta", "mexico", "monaco", "mongolia",
    "morocco", "myanmar", "nepal", "netherlands", "new zealand", "nicaragua", "nigeria",
    "norway", "oman", "pakistan", "palestine", "panama", "paraguay", "peru", "philippines",
    "poland", "portugal", "qatar", "romania", "russia", "saudi arabia", "senegal",
    "serbia", "singapore", "slovakia", "slovenia", "south africa", "south korea", "spain",
    "sri lanka", "sudan", "sweden", "switzerland", "taiwan", "tanzania", "thailand",
    "tunisia", "turkey", "turkiye", "uganda", "ukraine", "united arab emirates", "uae",
    "united kingdom", "uk", "great britain", "england", "scotland", "wales",
    "united states", "united states of america", "usa", "us", "uruguay", "uzbekistan",
    "venezuela", "vietnam", "yemen", "zambia", "zimbabwe"
}


def is_country_level_location(location: Optional[str]) -> bool:
    """Check if the provided location string specifies a country rather than a city/neighborhood."""
    if not location:
        return False
    loc = location.strip().lower()
    # If it contains a comma (e.g. "Lahore, Pakistan" or "Austin, TX"), it designates a specific city/locality
    if "," in loc:
        parts = [p.strip() for p in loc.split(",")]
        if len(parts) == 2 and parts[0] in KNOWN_COUNTRIES:
            return True
        return False
    clean = re.sub(r"[^a-zA-Z\s]", "", loc).strip()
    return clean in KNOWN_COUNTRIES


async def run_stage_03_scope_detection(
    inferred_scope: str,
    scope_override: Optional[str] = "auto",
    location: Optional[str] = None,
) -> str:
    """Resolve effective geographic scope between auto-inferred and user override."""
    # 1. User manual override takes absolute precedence
    if scope_override and scope_override != "auto":
        return scope_override.lower().strip()

    inferred = (inferred_scope or "global").lower().strip()

    # 2. If no location was supplied, trust the inferred scope
    if not location:
        return inferred

    is_country = is_country_level_location(location)

    # 3. If inferred scope is "national":
    # Stays "national" unless user gave an explicit city-level locality (e.g. "Lahore, Pakistan")
    if inferred == "national":
        if is_country or not ("," in location):
            return "national"
        return "local"

    # 4. If inferred scope is "local":
    # If the user specified a whole country (e.g. "Pakistan") with no city, elevate to national
    if inferred == "local":
        if is_country:
            return "national"
        return "local"

    # 5. If inferred scope is "global" (or unknown) but location was provided:
    if is_country:
        return "national"
    else:
        return "local"

