"""Validate and merge preferences; adapt the existing requirement contract.

Extended with constants for the internal private database modules:
knowledge categories, session stages, and skill registry categories.
"""

from copy import deepcopy
from decimal import Decimal, InvalidOperation


VERSION = "1.0"
SKILLS = (
    "travel-planner-plugin", "travel-requirement-analysis",
    "multi-platform-travel-planner", "travel-accommodation-advisor", "x-xiake",
    "travel-plan-review", "travel-handbook-builder", "travel-replanner",
    "travel-time-pocket",
)

KNOWLEDGE_CATEGORIES = (
    "city_info", "intercity_transport", "budget_reference",
    "accommodation_type", "local_food", "photo_spot",
    "season_tip", "transit_tip",
)

SESSION_STAGES = (
    "confirmed", "candidate", "verified", "intermediate",
    "review_result", "handbook_output",
)

REGISTRY_CATEGORIES = (
    "orchestrator", "analysis", "planning", "accommodation",
    "photo", "review", "handbook", "replanner", "pocket",
)

QUESTIONNAIRE_DIMENSIONS = (
    "destination", "departure_location", "dates_and_duration",
    "party_size", "budget", "travel_style", "transport_preference",
    "accommodation_preference", "photo_needs", "review_preference",
    "handbook_needs", "contingency_awareness",
)

QUESTION_TYPES = ("choice", "fill", "confirm")
LIST_FIELDS = {"interests", "transport_modes", "accommodation", "photo_styles"}
TEXT_FIELDS = {"pace", "photo_social_preference"}
INT_FIELDS = {"walking_tolerance_minutes"}
FIELDS = LIST_FIELDS | TEXT_FIELDS | INT_FIELDS
ENUMS = {
    "pace": {"relaxed", "balanced", "intensive", "unspecified"},
    "photo_social_preference": {"strangers_ok", "companions_only", "no_interaction", "unspecified"},
    "transport_modes": {"walk", "transit", "drive", "bike", "mixed", "unspecified"},
}


def object_value(value, name):
    if not isinstance(value, dict):
        raise ValueError(name + " must be an object")
    return value


def nonempty(value, name):
    if not isinstance(value, str) or not value.strip() or len(value) > 1000:
        raise ValueError(name + " must be a nonempty string of at most 1000 characters")
    return value


def validate_preferences(value, persistent=False):
    object_value(value, "preferences")
    if value.keys() - FIELDS:
        raise ValueError("unsupported preference fields: " + ", ".join(sorted(value.keys() - FIELDS)))
    for key, item in value.items():
        if item is None:
            if persistent:
                raise ValueError("use delete to remove a saved preference")
            continue
        if key in LIST_FIELDS:
            if not isinstance(item, list) or len(item) > 30:
                raise ValueError(key + " must be an array of at most 30 strings")
            for entry in item:
                nonempty(entry, key)
                if key in ENUMS and entry not in ENUMS[key]:
                    raise ValueError("unsupported " + key)
        elif key in TEXT_FIELDS:
            nonempty(item, key)
            if item not in ENUMS[key]:
                raise ValueError("unsupported " + key)
        elif type(item) is not int or item < 0:
            raise ValueError(key + " must be a nonnegative integer")
        if persistent and (item == "unspecified" or item == ["unspecified"]):
            raise ValueError("unspecified is not a long-term preference")
    return deepcopy(value)


def merge_preferences(saved, trip, current, explicit_fields):
    """Absent/null/unspecified inherit; explicitly listed [] clears for this trip."""
    layers = [("memory", saved), ("trip", trip), ("current", current)]
    if not isinstance(explicit_fields, list) or any(k not in FIELDS for k in explicit_fields):
        raise ValueError("explicit_preference_fields must list supported preference fields")
    if any(k not in current for k in explicit_fields):
        raise ValueError("explicit preference fields must exist in current preferences")
    merged, origins = {}, {}
    for origin, values in layers:
        validate_preferences(values)
        for key, value in values.items():
            explicit_clear = origin == "current" and key in explicit_fields and value == []
            if value is None or value == "unspecified" or value == ["unspecified"]:
                continue
            if value == [] and not explicit_clear:
                continue
            merged[key] = deepcopy(value)
            origins[key] = origin
    return merged, origins


def money_minor(amount, currency):
    """Only currencies with an explicitly supported exponent; never silently round."""
    exponents = {"CNY": 2, "USD": 2, "EUR": 2, "GBP": 2, "HKD": 2, "JPY": 0}
    if currency not in exponents or type(amount) not in (int, float):
        raise ValueError("money requires a supported currency and numeric amount")
    try:
        value = Decimal(str(amount)) * (10 ** exponents[currency])
        if not value.is_finite() or value < 0 or value != value.to_integral_value():
            raise ValueError("amount must be nonnegative and fit currency precision")
        return int(value)
    except InvalidOperation as exc:
        raise ValueError("invalid money amount") from exc


def adapt_requirements(skill, requirements):
    """Return facts safe to map; leave domain-specific IDs/room counts unresolved."""
    object_value(requirements, "requirements")
    prefs = requirements.get("preferences") or {}
    budget = requirements.get("budget") or {}
    travelers = requirements.get("travelers") or {}
    dates = requirements.get("dates") or {}
    destination = requirements.get("destination") or {}
    for name, value in (("budget", budget), ("travelers", travelers),
                        ("dates", dates), ("destination", destination)):
        object_value(value, name)
    hints, warnings = {}, []
    if skill == "travel-accommodation-advisor":
        hints = {
            "destination": destination.get("city"),
            "check_in": dates.get("start_date"),
            # Trip end date does not prove a hotel checkout date.
            "check_out": None, "rooms": None,
            "adults": travelers.get("adults"), "children_ages": None,
            "preferences": deepcopy(prefs.get("accommodation", [])),
        }
        warnings.append("酒店退房日、房数、儿童年龄和住宿专项预算需单独确认；旅行总预算不是房费预算。")
    elif skill in {"travel-plan-review", "travel-replanner"}:
        hard = requirements.get("review_requirements") or {}
        object_value(hard, "review_requirements")
        hard_fields = {"budget", "mandatory_place_ids", "daily_walking_limit_m", "daily_windows",
                       "deadlines", "allowed_transport_modes", "route_policy", "additional_checks"}
        if hard.keys() - hard_fields:
            raise ValueError("unsupported review_requirements fields")
        hints = deepcopy(hard)
        if (budget.get("amount") is not None and budget.get("scope") == "total_trip"
                and budget.get("hard_limit") is True):
            hints["budget"] = {"currency": budget.get("currency"),
                               "amount_minor": money_minor(budget["amount"], budget.get("currency")),
                               "scope": "total_trip"}
        elif budget.get("amount") is not None:
            warnings.append("只有确认的全程硬预算自动映射；参考预算或每人/每天口径需明确后另算。")
        warnings.append("步行分钟不换算成每日米数；交通喜好不转成硬限制；必去名称须先解析地点ID。")
    elif skill == "x-xiake":
        hints = {"photo_styles": deepcopy(prefs.get("photo_styles", [])),
                 "photo_social_preference": prefs.get("photo_social_preference"),
                 "travelers_total": travelers.get("total")}
        warnings.append("旅行人数不等于当前拍摄人数，现场关系、位置和光线按本次情况确认。")
    elif skill == "travel-time-pocket":
        hints = {"preferences": deepcopy(prefs)}
        warnings.append("起点、返回点、截止时间和实时路线从本次状态取得；偏好只筛选可行候选。")
    elif skill == "travel-handbook-builder":
        warnings.append("只呈现已确认的最终行程；不在离线手册中导出用户身份、记忆来源或完整偏好档案。")
    else:
        hints = {"requirements": deepcopy(requirements)}
    return {"input_hints": hints, "warnings": warnings}
