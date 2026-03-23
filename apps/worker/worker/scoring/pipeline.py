"""Job scoring pipeline and explainability persistence."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from jobscout_shared.models import Job, JobMatch

SYNONYM_MAP = {
    "o365": "microsoft 365",
    "office 365": "microsoft 365",
    "microsoft intra": "entra id",
    "intra": "entra",
}

ROLE_FAMILY_PATTERNS = {
    "software_engineering_only": [
        "software engineer",
        "full stack",
        "frontend",
        "backend",
        "developer",
    ],
    "sales_only": [
        "account executive",
        "commission-only",
        "business development",
        "sales representative",
    ],
}

CLEARANCE_TERMS = ["security clearance", " sc ", " dv ", " bpss", "bp ss"]
PREFERRED_LOCATION_TERMS = ["scotland", "aberdeen", "inverness", "dundee", "perth", "highlands"]


@dataclass(slots=True)
class ScoreArtifacts:
    skills_profile: dict[str, Any]
    truth_bank: dict[str, Any]
    scoring_weights: dict[str, Any]


@dataclass(slots=True)
class RubricContract:
    section_maxima: dict[str, float]
    component_points: dict[tuple[str, str], float]
    location_range: tuple[float, float]
    decision_thresholds: dict[str, tuple[float, float]]
    expected_hard_filters: dict[str, bool]


@dataclass(slots=True)
class ScoreResult:
    total_score: float
    decision: str
    breakdown: dict[str, Any]
    reasons: list[str]
    missing_keywords: list[str]


@dataclass(slots=True)
class ScoringSummary:
    jobs_scored: int
    apply_count: int
    review_count: int
    skip_count: int


def _extract_int(pattern: str, text: str, label: str) -> int:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"unable to parse `{label}` from RUBRIC.md")
    return int(match.group(1))


def _load_rubric_contract(rubric_path: Path) -> RubricContract:
    text = rubric_path.read_text(encoding="utf-8")

    section_patterns = {
        "microsoft_365_core": r"Microsoft 365 core\s+\(0-(\d+)\)",
        "backup_dr": r"Backup / DR\s+\(0-(\d+)\)",
        "ops_service_ownership": r"Ops / Service ownership\s+\(0-(\d+)\)",
        "migrations_project_delivery": r"Migrations / project delivery\s+\(0-(\d+)\)",
        "telco_teams_voice": r"Telco / Teams Voice\s+\(0-(\d+)\)",
    }
    section_maxima = {
        section: float(_extract_int(pattern, text, f"section max `{section}`"))
        for section, pattern in section_patterns.items()
    }

    component_patterns = {
        ("microsoft_365_core", "exchange_online_mailflow_hybrid"): (
            r"Exchange Online / mail flow / hybrid:\s+\+0\.\.(\d+)"
        ),
        ("microsoft_365_core", "sharepoint_online_migration"): (
            r"SharePoint Online / migration:\s+\+0\.\.(\d+)"
        ),
        ("microsoft_365_core", "teams_administration"): r"Teams administration:\s+\+0\.\.(\d+)",
        ("backup_dr", "azure_backup"): r"Azure Backup:\s+\+0\.\.(\d+)",
        ("backup_dr", "veeam"): r"Veeam:\s+\+0\.\.(\d+)",
        ("backup_dr", "storage_restore_testing"): r"NAS/Tape/Cold storage \+ restore testing:\s+\+0\.\.(\d+)",
        ("ops_service_ownership", "l3_incident_ownership"): r"L3 support / incident ownership:\s+\+0\.\.(\d+)",
        ("migrations_project_delivery", "onprem_to_cloud_migrations"): (
            r"On-prem to cloud migrations \(Exchange/SharePoint/telco\):\s+\+0\.\.(\d+)"
        ),
        ("migrations_project_delivery", "vendor_management_delivery"): (
            r"Vendor management \+ delivery:\s+\+0\.\.(\d+)"
        ),
        ("telco_teams_voice", "avaya_sbc_sip_teams_phone"): r"Avaya / SBC / SIP / Teams Phone:\s+\+0\.\.(\d+)",
    }
    component_points = {
        key: float(_extract_int(pattern, text, f"component `{key[0]}.{key[1]}`"))
        for key, pattern in component_patterns.items()
    }

    location_min = _extract_int(r"Location \+ work-mode fit\s+\(([-–]?\d+)\s+to\s+\+\d+\)", text, "location min")
    location_max = _extract_int(r"Location \+ work-mode fit\s+\([-–]?\d+\s+to\s+\+(\d+)\)", text, "location max")

    apply_min = _extract_int(r"(\d+)-\d+:\s+`apply`", text, "apply min")
    apply_max = _extract_int(r"\d+-(\d+):\s+`apply`", text, "apply max")
    review_min = _extract_int(r"(\d+)-\d+:\s+`review`", text, "review min")
    review_max = _extract_int(r"\d+-(\d+):\s+`review`", text, "review max")
    skip_below = _extract_int(r"below\s+(\d+):\s+`skip`", text, "skip below threshold")

    expected_hard_filters = {
        "reject_daily_onsite_outside_scotland_if_not_remote": (
            "Daily onsite presence is required outside Scotland and role is not remote" in text
        ),
        "reject_clearance_mismatch_unless_willing_to_obtain": (
            "Requires clearance the candidate does not have and is not willing to obtain" in text
        ),
        "excluded_role_families": ("Role family mismatch" in text),
    }

    return RubricContract(
        section_maxima=section_maxima,
        component_points=component_points,
        location_range=(float(location_min), float(location_max)),
        decision_thresholds={
            "apply": (float(apply_min), float(apply_max)),
            "review": (float(review_min), float(review_max)),
            "skip": (0.0, float(skip_below - 1)),
        },
        expected_hard_filters=expected_hard_filters,
    )


def _validate_scoring_weights_against_rubric(
    scoring_weights: dict[str, Any],
    rubric: RubricContract,
    rubric_path: Path,
) -> None:
    errors: list[str] = []
    weights = scoring_weights.get("weights", {})

    for section_name, expected_max in rubric.section_maxima.items():
        actual_max = float(weights.get(section_name, {}).get("max", -1))
        if actual_max != expected_max:
            errors.append(
                f"`weights.{section_name}.max` expected {expected_max:.0f} from {rubric_path.name}, got {actual_max}"
            )

    for (section_name, component_name), expected_points in rubric.component_points.items():
        actual_points = float(weights.get(section_name, {}).get(component_name, -1))
        if actual_points != expected_points:
            errors.append(
                (
                    f"`weights.{section_name}.{component_name}` expected {expected_points:.0f} "
                    f"from {rubric_path.name}, got {actual_points}"
                )
            )

    location_cfg = weights.get("location_work_mode_fit", {})
    range_cfg = location_cfg.get("range", {})
    if float(range_cfg.get("min", 0)) != rubric.location_range[0]:
        errors.append(
            (
                f"`weights.location_work_mode_fit.range.min` expected {rubric.location_range[0]:.0f} "
                f"from {rubric_path.name}, got {range_cfg.get('min')}"
            )
        )
    if float(range_cfg.get("max", 0)) != rubric.location_range[1]:
        errors.append(
            (
                f"`weights.location_work_mode_fit.range.max` expected {rubric.location_range[1]:.0f} "
                f"from {rubric_path.name}, got {range_cfg.get('max')}"
            )
        )

    decision_cfg = scoring_weights.get("decision_thresholds", {})
    for decision, (expected_min, expected_max) in rubric.decision_thresholds.items():
        actual_block = decision_cfg.get(decision, {})
        actual_min = float(actual_block.get("min", 0))
        actual_max = float(actual_block.get("max", 0))
        if decision == "skip":
            if actual_max != expected_max:
                errors.append(
                    (
                        f"`decision_thresholds.skip.max` expected {expected_max:.0f} from "
                        f"{rubric_path.name}, got {actual_max}"
                    )
                )
            continue
        if actual_min != expected_min or actual_max != expected_max:
            errors.append(
                (
                    f"`decision_thresholds.{decision}` expected {expected_min:.0f}-{expected_max:.0f} "
                    f"from {rubric_path.name}, got {actual_min:.0f}-{actual_max:.0f}"
                )
            )

    hard_filters = scoring_weights.get("hard_filters", {})
    if rubric.expected_hard_filters["reject_daily_onsite_outside_scotland_if_not_remote"]:
        if not bool(hard_filters.get("reject_daily_onsite_outside_scotland_if_not_remote", False)):
            errors.append("missing hard filter: reject_daily_onsite_outside_scotland_if_not_remote")

    if rubric.expected_hard_filters["reject_clearance_mismatch_unless_willing_to_obtain"]:
        if not bool(hard_filters.get("reject_clearance_mismatch_unless_willing_to_obtain", False)):
            errors.append("missing hard filter: reject_clearance_mismatch_unless_willing_to_obtain")

    if rubric.expected_hard_filters["excluded_role_families"]:
        families = hard_filters.get("excluded_role_families", [])
        if not isinstance(families, list) or len(families) == 0:
            errors.append("missing hard filter: excluded_role_families")

    if errors:
        joined = "; ".join(errors)
        raise ValueError(f"scoring_weights.yml violates {rubric_path.name}: {joined}")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _normalize_text(value: str) -> str:
    text = f" {(value or '').lower()} "
    for source, target in SYNONYM_MAP.items():
        text = text.replace(f" {source} ", f" {target} ")
    return " ".join(text.split())


def _contains_keyword(text: str, keyword: str) -> bool:
    token = keyword.lower().strip()
    if not token:
        return False
    return token in text


def _extract_profile_keywords(skills_profile: dict[str, Any]) -> set[str]:
    keywords: set[str] = set()
    for domain in skills_profile.get("core_domains", []):
        for skill in domain.get("skills", []):
            for keyword in skill.get("keywords", []):
                norm = keyword.strip().lower()
                if norm:
                    keywords.add(norm)
    for keyword in skills_profile.get("matching_preferences", {}).get("include_keywords", []):
        norm = keyword.strip().lower()
        if norm:
            keywords.add(norm)
    return keywords


def _location_is_preferred(location_text: str) -> bool:
    location = _normalize_text(location_text)
    return any(term in location for term in PREFERRED_LOCATION_TERMS)


def _work_mode_from_job(job: Job, text: str) -> str:
    mode = (job.work_mode or "").lower().strip()
    if mode:
        return mode
    if "hybrid" in text:
        return "hybrid"
    if "remote" in text:
        return "remote"
    if "onsite" in text or "on-site" in text:
        return "onsite"
    return "unknown"


def _score_weighted_component(text: str, keywords: list[str], max_points: float) -> tuple[float, list[str]]:
    normalized_keywords = [kw.strip().lower() for kw in keywords if kw and kw.strip()]
    unique_keywords = sorted(set(normalized_keywords))
    if not unique_keywords or max_points <= 0:
        return 0.0, []

    matched = [kw for kw in unique_keywords if _contains_keyword(text, kw)]
    ratio = len(matched) / len(unique_keywords)
    return round(max_points * ratio, 2), matched


def _component_keywords(profile_keywords: set[str]) -> dict[str, list[str]]:
    def pick(*terms: str) -> list[str]:
        selected = [kw for kw in profile_keywords if any(term in kw for term in terms)]
        return sorted(set(selected))

    return {
        "exchange_online_mailflow_hybrid": pick("exchange", "mail flow", "smtp", "hybrid"),
        "sharepoint_online_migration": pick("sharepoint", "migration"),
        "teams_administration": pick("teams", "telephony", "teams phone"),
        "azure_backup": pick("azure backup", "recovery services"),
        "veeam": pick("veeam"),
        "storage_restore_testing": pick("nas", "tape", "cold storage", "restore"),
        "l3_incident_ownership": pick("l3", "incident", "service owner", "problem management"),
        "onprem_to_cloud_migrations": pick("migration", "cloud"),
        "vendor_management_delivery": pick("vendor", "procurement", "delivery"),
        "avaya_sbc_sip_teams_phone": pick("avaya", "sbc", "sip", "teams phone"),
    }


def _hard_filter_reasons(job: Job, text: str, truth_bank: dict[str, Any], weights: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    hard_filters = weights.get("hard_filters", {})

    if hard_filters.get("reject_daily_onsite_outside_scotland_if_not_remote", False):
        mode = _work_mode_from_job(job, text)
        is_remote = "remote" in mode or "remote" in text
        is_onsite = "onsite" in mode or "onsite" in text or "on-site" in text
        if is_onsite and not is_remote and not _location_is_preferred(job.location_text or ""):
            reasons.append("location/work_mode hard filter triggered")

    excluded_families = hard_filters.get("excluded_role_families", [])
    for family in excluded_families:
        patterns = ROLE_FAMILY_PATTERNS.get(family, [])
        if any(pattern in text for pattern in patterns):
            reasons.append(f"role family hard filter triggered: {family}")
            break

    if hard_filters.get("reject_clearance_mismatch_unless_willing_to_obtain", False):
        requires_clearance = any(term in text for term in CLEARANCE_TERMS)
        security = truth_bank.get("security_and_compliance", {})
        candidate_clearance = str(security.get("security_clearance", "")).strip().lower()
        willing = str(security.get("willing_to_undergo_checks", "")).strip().lower()
        willing_yes = willing in {"yes", "true", "y", "willing", "willing to obtain"}
        if requires_clearance and not candidate_clearance and not willing_yes:
            reasons.append("clearance hard filter triggered")

    return reasons


def _location_fit_score(job: Job, text: str, weights: dict[str, Any]) -> float:
    location_weight = weights.get("weights", {}).get("location_work_mode_fit", {})
    mode = _work_mode_from_job(job, text)

    if "hybrid" in mode:
        return float(location_weight.get("hybrid_within_radius", 0))
    if "remote" in mode:
        return float(location_weight.get("remote_uk", 0))
    if "onsite" in mode:
        if _location_is_preferred(job.location_text or ""):
            return float(location_weight.get("onsite_within_radius", 0))
        return float(location_weight.get("onsite_far_outside_preferred", 0))
    return 0.0


def _region_boost(job: Job, text: str, weights: dict[str, Any]) -> float:
    boosts = weights.get("region_boosts", {})
    location = _normalize_text(job.location_text or "")
    boost_total = 0.0

    if "aberdeen" in location:
        for keyword in boosts.get("aberdeen_keywords", []):
            if _contains_keyword(text, keyword):
                boost_total += 1.0

    if "inverness" in location or "highlands" in location:
        for keyword in boosts.get("inverness_highlands_keywords", []):
            if _contains_keyword(text, keyword):
                boost_total += 1.0

    for keyword in boosts.get("public_sector_keywords", []):
        if _contains_keyword(text, keyword):
            boost_total += 0.5

    return round(min(boost_total, 5.0), 2)


def _embedding_similarity_hook(text: str, profile_keywords: set[str], enabled: bool) -> float | None:
    if not enabled:
        return None
    text_tokens = {token for token in text.split() if len(token) > 2}
    profile_tokens = {token for token in profile_keywords if len(token) > 2}
    if not text_tokens or not profile_tokens:
        return 0.0
    overlap = len(text_tokens & profile_tokens)
    union = len(text_tokens | profile_tokens)
    return round(overlap / union, 4)


def _decide_score(total_score: float, hard_filter_reasons: list[str], thresholds: dict[str, Any]) -> str:
    if hard_filter_reasons:
        return "skip"

    apply_cfg = thresholds.get("apply", {})
    review_cfg = thresholds.get("review", {})
    skip_cfg = thresholds.get("skip", {})

    if apply_cfg.get("min", 80) <= total_score <= apply_cfg.get("max", 100):
        return "apply"
    if review_cfg.get("min", 60) <= total_score <= review_cfg.get("max", 79):
        return "review"
    if total_score <= skip_cfg.get("max", 59):
        return "skip"
    return "review"


def _build_reasons(
    component_scores: dict[str, float],
    hard_filter_reasons: list[str],
    top_reasons_count: int,
) -> list[str]:
    reasons: list[str] = [f"Hard filter: {reason}" for reason in hard_filter_reasons]
    sorted_components = sorted(component_scores.items(), key=lambda item: item[1], reverse=True)
    for name, value in sorted_components:
        if value <= 0:
            continue
        label = name.replace("_", " ")
        reasons.append(f"Strong match: {label} (+{value:.2f})")
        if len(reasons) >= top_reasons_count:
            break

    return reasons[:top_reasons_count]


def _build_missing_keywords(
    text: str,
    profile_keywords: set[str],
    missing_count: int,
) -> list[str]:
    missing = [keyword for keyword in sorted(profile_keywords) if not _contains_keyword(text, keyword)]
    return missing[:missing_count]


def score_job(
    job: Job,
    artifacts: ScoreArtifacts,
    use_embeddings: bool = False,
) -> ScoreResult:
    weights = artifacts.scoring_weights
    text = _normalize_text(" ".join([job.title, job.company, job.description_text or ""]))
    profile_keywords = _extract_profile_keywords(artifacts.skills_profile)

    component_keyword_map = _component_keywords(profile_keywords)
    weight_map = weights.get("weights", {})

    component_scores: dict[str, float] = {}
    matched_keywords: set[str] = set()

    for group_name, group_weights in weight_map.items():
        if group_name in {"location_work_mode_fit"}:
            continue
        if not isinstance(group_weights, dict):
            continue

        for component_name, value in group_weights.items():
            if component_name == "max":
                continue
            max_points = float(value)
            keywords = component_keyword_map.get(component_name, [])
            score, matched = _score_weighted_component(text, keywords, max_points)
            component_scores[component_name] = score
            matched_keywords.update(matched)

    location_score = _location_fit_score(job, text, weights)
    component_scores["location_work_mode_fit"] = location_score

    region_boost = _region_boost(job, text, weights)
    hard_filter_reasons = _hard_filter_reasons(job, text, artifacts.truth_bank, weights)

    keyword_ratio = 0.0
    if profile_keywords:
        keyword_ratio = round(len(matched_keywords) / len(profile_keywords), 4)

    embedding_similarity = _embedding_similarity_hook(text, profile_keywords, enabled=use_embeddings)

    total_score = round(sum(component_scores.values()) + region_boost, 2)
    total_score = max(0.0, min(total_score, 100.0))
    decision = _decide_score(total_score, hard_filter_reasons, weights.get("decision_thresholds", {}))

    top_reasons_count = int(weights.get("explainability", {}).get("top_reasons_count", 5))
    missing_count = int(weights.get("explainability", {}).get("missing_keywords_count", 3))

    reasons = _build_reasons(component_scores, hard_filter_reasons, top_reasons_count)
    missing_keywords = _build_missing_keywords(text, profile_keywords, missing_count)

    breakdown = {
        "hard_filters": {
            "triggered": bool(hard_filter_reasons),
            "reasons": hard_filter_reasons,
        },
        "components": component_scores,
        "region_boost": region_boost,
        "keyword_match_ratio": keyword_ratio,
        "embedding_similarity": embedding_similarity,
        "embedding_enabled": bool(use_embeddings),
    }

    return ScoreResult(
        total_score=total_score,
        decision=decision,
        breakdown=breakdown,
        reasons=reasons,
        missing_keywords=missing_keywords,
    )


def _load_artifacts(
    skills_profile_path: Path,
    truth_bank_path: Path,
    scoring_weights_path: Path,
    rubric_path: Path,
) -> ScoreArtifacts:
    scoring_weights = _load_yaml(scoring_weights_path)
    rubric = _load_rubric_contract(rubric_path)
    _validate_scoring_weights_against_rubric(scoring_weights, rubric, rubric_path)
    return ScoreArtifacts(
        skills_profile=_load_json(skills_profile_path),
        truth_bank=_load_yaml(truth_bank_path),
        scoring_weights=scoring_weights,
    )


def run_scoring(
    session_factory: sessionmaker[Session],
    skills_profile_path: Path,
    truth_bank_path: Path,
    scoring_weights_path: Path,
    rubric_path: Path | None = None,
    use_embeddings: bool = False,
) -> ScoringSummary:
    artifacts = _load_artifacts(
        skills_profile_path,
        truth_bank_path,
        scoring_weights_path,
        rubric_path or Path("RUBRIC.md"),
    )
    apply_count = 0
    review_count = 0
    skip_count = 0

    with session_factory() as session:
        jobs = session.execute(select(Job).order_by(Job.id.asc())).scalars().all()

        for job in jobs:
            result = score_job(job, artifacts, use_embeddings=use_embeddings)
            match = session.get(JobMatch, job.id)
            if match is None:
                match = JobMatch(job_id=job.id)
                session.add(match)

            match.total_score = result.total_score
            match.score_breakdown_json = result.breakdown
            match.reasons_json = result.reasons
            match.missing_json = result.missing_keywords
            match.decision = result.decision

            if result.decision == "apply":
                apply_count += 1
            elif result.decision == "review":
                review_count += 1
            else:
                skip_count += 1

        session.commit()

    return ScoringSummary(
        jobs_scored=apply_count + review_count + skip_count,
        apply_count=apply_count,
        review_count=review_count,
        skip_count=skip_count,
    )
