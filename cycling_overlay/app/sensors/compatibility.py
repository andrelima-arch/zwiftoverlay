"""BLE compatibility rules adapted from QDomyos-Zwift.

QDomyos-Zwift is GPLv3. This module ports only the generic device matching
rules needed by this Python overlay.
"""

from __future__ import annotations

from dataclasses import dataclass


FTMS_SERVICE_UUID = "00001826-0000-1000-8000-00805f9b34fb"
POWER_SERVICE_UUID = "00001818-0000-1000-8000-00805f9b34fb"
CSC_SERVICE_UUID = "00001816-0000-1000-8000-00805f9b34fb"
RSC_SERVICE_UUID = "00001814-0000-1000-8000-00805f9b34fb"
HR_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"


@dataclass(frozen=True)
class CompatibilityMatch:
    service_type: str
    profile: str
    hint: str


@dataclass(frozen=True)
class CompatibilityRule:
    profile: str
    hint: str
    prefixes: tuple[str, ...]
    preferred_service: str = "ftms"


QZ_COMPATIBILITY_RULES: tuple[CompatibilityRule, ...] = (
    CompatibilityRule(
        profile="qz_virtual",
        hint="QZ Virtual BLE",
        prefixes=("QZ", "QZ FITNESS DEVICE"),
    ),
    CompatibilityRule(
        profile="think_x",
        hint="FTMS / ThinkRider QZ match",
        prefixes=("THINK X", "THINK-", "THINK_", "THINKRIDER", "THINK VS", "X2MAX"),
    ),
    CompatibilityRule(
        profile="tacxneo2_like",
        hint="FTMS / Tacx Neo QZ match",
        prefixes=("TACX NEO", "NEO BIKE", "TACX SMART BIKE", "TACX"),
    ),
    CompatibilityRule(
        profile="wahoo_kickr",
        hint="FTMS / Wahoo KICKR QZ match",
        prefixes=("KICKR", "WAHOO KICKR", "WAHOO", "SNAP"),
    ),
    CompatibilityRule(
        profile="elite",
        hint="FTMS / Elite QZ match",
        prefixes=("ELITE", "DIRETO", "SUITO", "TUO", "JUSTO", "AVANTI", "STERZO"),
    ),
    CompatibilityRule(
        profile="saris",
        hint="FTMS / Saris QZ match",
        prefixes=("HAMMER", "MAGNUS", "SARIS", "H3", "H4"),
    ),
    CompatibilityRule(
        profile="jetblack",
        hint="FTMS / JetBlack/Zwift Hub QZ match",
        prefixes=("ZWIFT HUB", "JETBLACK", "VOLT", "ZWIFT"),
    ),
    CompatibilityRule(
        profile="magene",
        hint="FTMS / Magene QZ match",
        prefixes=("MAGENE", "MG-", "GEARBIKE"),
    ),
    CompatibilityRule(
        profile="van_rysel",
        hint="FTMS / Van Rysel QZ match",
        prefixes=("VANRYSEL-HT", "VAN RYSEL", "D100", "D500", "VANRYSEL"),
    ),
    CompatibilityRule(
        profile="zdrive",
        hint="FTMS / ZDrive QZ match",
        prefixes=("ZDRIVE", "Z-DRIVE"),
    ),
    CompatibilityRule(
        profile="stages_bike",
        hint="FTMS / Stages Bike QZ match",
        prefixes=("STAGES BIKE", "STAGES", "STAGESB"),
    ),
    CompatibilityRule(
        profile="wattbike",
        hint="FTMS / Wattbike QZ match",
        prefixes=("WATTBIKE", "WATT BIKE", "ATOM"),
    ),
    CompatibilityRule(
        profile="noza",
        hint="FTMS / Xplova/NOZA QZ match",
        prefixes=("NOZA", "XLOVA", "XPLOVA"),
    ),
    CompatibilityRule(
        profile="domyos",
        hint="FTMS / Domyos QZ match",
        prefixes=("DOMYOS-BIKE", "DOMYOS-EL", "DOMYOS-TC", "DOMYOS"),
    ),
    CompatibilityRule(
        profile="sole",
        hint="FTMS / Sole QZ match",
        prefixes=("SOLE E25", "SOLE E35", "SOLE E95", "SOLE"),
    ),
    CompatibilityRule(
        profile="nautilus",
        hint="FTMS / Nautilus QZ match",
        prefixes=("NAUTILUS B", "NAUTILUS E", "NAUTILUS"),
    ),
    CompatibilityRule(
        profile="schwinn",
        hint="FTMS / Schwinn QZ match",
        prefixes=("IC BIKE", "SCHWINN", "C7-", "C6-", "170", "130"),
    ),
    CompatibilityRule(
        profile="yesoul",
        hint="FTMS / Yesoul QZ match",
        prefixes=("YESOUL", "YESOULBIKE"),
    ),
    CompatibilityRule(
        profile="proform",
        hint="FTMS / ProForm QZ match",
        prefixes=("PROFORM", "PRO-FORM", "PF"),
    ),
    CompatibilityRule(
        profile="bowflex",
        hint="FTMS / Bowflex QZ match",
        prefixes=("BOWFLEX", "BFX", "C6", "C7", "VELOCORE"),
    ),
    CompatibilityRule(
        profile="cycplus",
        hint="FTMS / Cycplus QZ match",
        prefixes=("CYCPLUS", "BC2", "T2", "C6"),
    ),
    CompatibilityRule(
        profile="du30",
        hint="FTMS / DU30 QZ match",
        prefixes=("DU30", "SPORT01", "TOPUTURE"),
    ),
    CompatibilityRule(
        profile="fitmetria",
        hint="FTMS / Fitmetria QZ match",
        prefixes=("FITFAN", "HEADWIND", "FITMETRIA"),
    ),
)


def normalise_uuid(value: str) -> str:
    value = str(value).lower().strip()
    if len(value) == 4:
        return f"0000{value}-0000-1000-8000-00805f9b34fb"
    return value


def has_uuid(services: list[str], uuid: str) -> bool:
    short = uuid[4:8]
    for service in services:
        normalised = normalise_uuid(service)
        if normalised == uuid or short in normalised:
            return True
    return False


def normalise_name(name: str) -> str:
    return " ".join((name or "").upper().replace("_", " ").split())


def matches_prefix(name: str, prefixes: tuple[str, ...]) -> bool:
    upper_name = (name or "").upper()
    normalised = normalise_name(name)
    for prefix in prefixes:
        upper_prefix = prefix.upper()
        normalised_prefix = normalise_name(prefix)
        if (
            upper_name.startswith(upper_prefix)
            or normalised.startswith(normalised_prefix)
            or upper_prefix in upper_name
            or normalised_prefix in normalised
        ):
            return True
    return False


def match_qz_profile(name: str) -> CompatibilityRule | None:
    if normalise_name(name) in {"QZ", "QZ FITNESS DEVICE"}:
        return QZ_COMPATIBILITY_RULES[0]
    for rule in QZ_COMPATIBILITY_RULES[1:]:
        if matches_prefix(name, rule.prefixes):
            return rule
    return None


def detect_compatibility(name: str, services: list[str]) -> CompatibilityMatch:
    rule = match_qz_profile(name)
    has_ftms = has_uuid(services, FTMS_SERVICE_UUID)
    has_power = has_uuid(services, POWER_SERVICE_UUID)
    has_csc = has_uuid(services, CSC_SERVICE_UUID)
    has_rsc = has_uuid(services, RSC_SERVICE_UUID)
    has_hr = has_uuid(services, HR_SERVICE_UUID)

    if has_ftms:
        return CompatibilityMatch("ftms", rule.profile if rule else "generic_ftms", rule.hint if rule else "")
    if rule:
        return CompatibilityMatch(rule.preferred_service, rule.profile, rule.hint)
    if has_power:
        return CompatibilityMatch("power", "cycling_power", "")
    if has_csc:
        return CompatibilityMatch("csc", "csc", "")
    if has_rsc:
        return CompatibilityMatch("rsc", "rsc", "")
    if has_hr:
        return CompatibilityMatch("hr", "heart_rate", "")
    return CompatibilityMatch("unknown", "", "")
