"""Application pack generation with evidence guardrails."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from jobscout_shared.models import ApplicationPack, Job, JobMatch

MIN_COVER_WORDS = 150
MAX_COVER_WORDS = 250
NEEDS_INPUT = "NEEDS_USER_INPUT"


@dataclass(slots=True)
class SkillEntry:
    domain_index: int
    skill_index: int
    skill_name: str
    keywords: list[str]
    evidence: list[str]


@dataclass(slots=True)
class PackGenerationResult:
    pack_id: int
    job_id: int
    status: str


@dataclass(slots=True)
class GuardrailContract:
    min_cover_words: int
    max_cover_words: int
    require_claim_evidence_refs: bool
    require_non_empty_evidence_path: bool
    required_inputs: tuple[str, ...]
    right_to_work_field_path: str


DEFAULT_GUARDRAIL_CONTRACT = GuardrailContract(
    min_cover_words=MIN_COVER_WORDS,
    max_cover_words=MAX_COVER_WORDS,
    require_claim_evidence_refs=True,
    require_non_empty_evidence_path=True,
    required_inputs=("job", "skills_profile", "truth_bank"),
    right_to_work_field_path="identity.right_to_work_uk",
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _normalize_text(value: str) -> str:
    return " ".join((value or "").lower().split())


def _word_count(value: str) -> int:
    return len([token for token in value.replace("\n", " ").split(" ") if token.strip()])


def _safe_path(source: str, path: str, quote: str) -> dict[str, str]:
    return {
        "source": source,
        "path": path,
        "quote": quote.strip()[:200],
    }


def _load_guardrail_from_yaml(yml_path: Path) -> GuardrailContract:
    data = yaml.safe_load(yml_path.read_text(encoding="utf-8")) or {}
    required_inputs = [str(item) for item in data.get("required_inputs", [])]
    if len(required_inputs) < 3:
        raise ValueError(f"required_inputs incomplete in {yml_path.name}")
    right_to_work = str(data.get("right_to_work_field_path", "")).strip()
    if not right_to_work:
        raise ValueError(f"right_to_work_field_path missing in {yml_path.name}")
    return GuardrailContract(
        min_cover_words=int(data["min_cover_words"]),
        max_cover_words=int(data["max_cover_words"]),
        require_claim_evidence_refs=bool(data.get("require_claim_evidence_refs", True)),
        require_non_empty_evidence_path=bool(data.get("require_non_empty_evidence_path", True)),
        required_inputs=tuple(required_inputs),
        right_to_work_field_path=right_to_work,
    )


def _load_guardrail_from_markdown(path: Path) -> GuardrailContract:
    text = path.read_text(encoding="utf-8")

    cover_range_match = re.search(
        r"between\s+(\d+)\s+and\s+(\d+)\s+words",
        text,
        flags=re.IGNORECASE,
    ) or re.search(
        r"(\d+)\s*-\s*(\d+)\s*words",
        text,
        flags=re.IGNORECASE,
    )
    if cover_range_match is None:
        raise ValueError(f"unable to parse cover-letter range from {path.name}")

    required_inputs_section_match = re.search(
        r"## Required Inputs(?P<section>.*?)(?:\n## |\Z)",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    required_section = required_inputs_section_match.group("section") if required_inputs_section_match else ""
    required_inputs: list[str] = []
    for item in ("job", "skills_profile", "truth_bank"):
        if re.search(rf"`{item}`", required_section):
            required_inputs.append(item)
    if len(required_inputs) < 3:
        raise ValueError(f"required inputs are incomplete in {path.name}")

    right_to_work_match = re.search(
        r"truth_bank\.(identity\.right_to_work_uk)",
        text,
        flags=re.IGNORECASE,
    )
    if right_to_work_match is None:
        raise ValueError(f"unable to parse right-to-work guardrail path from {path.name}")

    require_claim_evidence_refs = "Every claim must include at least one evidence reference." in text
    if not require_claim_evidence_refs:
        raise ValueError(f"missing claim evidence rule in {path.name}")

    require_non_empty_evidence_path = "Reject any evidence ref with empty `path`" in text
    if not require_non_empty_evidence_path:
        raise ValueError(f"missing non-empty evidence path rule in {path.name}")

    return GuardrailContract(
        min_cover_words=int(cover_range_match.group(1)),
        max_cover_words=int(cover_range_match.group(2)),
        require_claim_evidence_refs=require_claim_evidence_refs,
        require_non_empty_evidence_path=require_non_empty_evidence_path,
        required_inputs=tuple(required_inputs),
        right_to_work_field_path=right_to_work_match.group(1),
    )


def load_prompt_guardrail_contract(path: Path) -> GuardrailContract:
    # Prefer a structured YAML sidecar (same stem, .yml) over markdown regex parsing.
    yml_path = path.with_suffix(".yml")
    if yml_path.exists():
        return _load_guardrail_from_yaml(yml_path)
    return _load_guardrail_from_markdown(path)


def _skills_index(skills_profile: dict[str, Any]) -> list[SkillEntry]:
    entries: list[SkillEntry] = []
    for domain_idx, domain in enumerate(skills_profile.get("core_domains", [])):
        for skill_idx, skill in enumerate(domain.get("skills", [])):
            entries.append(
                SkillEntry(
                    domain_index=domain_idx,
                    skill_index=skill_idx,
                    skill_name=str(skill.get("skill", "")).strip(),
                    keywords=[str(item).strip().lower() for item in skill.get("keywords", [])],
                    evidence=[str(item).strip() for item in skill.get("evidence", []) if str(item).strip()],
                )
            )
    return entries


def _skill_evidence_refs(entry: SkillEntry, limit: int = 1) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for ev_idx, quote in enumerate(entry.evidence[:limit]):
        refs.append(
            _safe_path(
                source="skills_profile",
                path=f"core_domains[{entry.domain_index}].skills[{entry.skill_index}].evidence[{ev_idx}]",
                quote=quote,
            )
        )
    if refs:
        return refs

    return [
        _safe_path(
            source="skills_profile",
            path=f"core_domains[{entry.domain_index}].skills[{entry.skill_index}].skill",
            quote=entry.skill_name or "Skill evidence missing",
        )
    ]


def _select_relevant_skills(job: Job, entries: list[SkillEntry], limit: int = 4) -> list[SkillEntry]:
    text = _normalize_text(" ".join([job.title, job.description_text or "", job.requirements_text or ""]))
    ranked: list[tuple[int, SkillEntry]] = []
    for entry in entries:
        if not entry.skill_name:
            continue
        score = sum(1 for keyword in set(entry.keywords) if keyword and keyword in text)
        ranked.append((score, entry))

    ranked.sort(key=lambda item: (item[0], item[1].skill_name), reverse=True)
    relevant = [item[1] for item in ranked if item[0] > 0][:limit]
    if relevant:
        return relevant

    fallback = [item[1] for item in ranked][:limit]
    return fallback


def _truth_bank_ref(truth_bank: dict[str, Any], path: str) -> tuple[str, list[dict[str, str]]]:
    value: Any = truth_bank
    for part in path.split("."):
        if not isinstance(value, dict):
            value = ""
            break
        value = value.get(part, "")

    if isinstance(value, list):
        for idx, item in enumerate(value):
            text = str(item).strip()
            if text:
                return text, [_safe_path(source="truth_bank", path=f"{path}[{idx}]", quote=text)]
        return "", [_safe_path(source="truth_bank", path=f"{path}[0]", quote="Value missing in truth_bank.yml")]

    text = str(value).strip() if value is not None else ""
    if not text:
        return "", [_safe_path(source="truth_bank", path=path, quote="Value missing in truth_bank.yml")]
    return text, [_safe_path(source="truth_bank", path=path, quote=text)]


def _job_requirements_summary(job: Job) -> str:
    raw = job.requirements_text or job.description_text or ""
    words = raw.replace("\n", " ").split()
    snippet = " ".join(words[:18]).strip()
    if not snippet:
        return "reliable Microsoft 365 and infrastructure delivery"
    return snippet.rstrip(".,;:") + "."


def _build_cv_variant(
    job: Job,
    skills: list[SkillEntry],
    missing_requirements: list[str],
) -> str:
    bullets = [
        f"- {entry.skill_name}: practical delivery across operations, change, and incident response."
        for entry in skills
    ]
    missing_line = (
        f"- Development areas for this role: {', '.join(missing_requirements[:3])}."
        if missing_requirements
        else "- Development areas for this role: none flagged by the current matcher."
    )
    return "\n".join(
        [
            f"# CV Variant - {job.title} ({job.company})",
            "",
            "## Role Alignment",
            f"- Target role: {job.title}",
            "- Focus: Microsoft 365, infrastructure reliability, and service ownership.",
            "",
            "## Evidence-backed Experience",
            *bullets,
            "",
            "## This Application Focus",
            missing_line,
        ]
    )


def _build_cover_letter(job: Job, candidate_name: str, skills: list[SkillEntry]) -> str:
    named_skills = ", ".join(entry.skill_name for entry in skills[:4])
    if not named_skills:
        named_skills = "Microsoft 365 operations and infrastructure support"

    requirement_summary = _job_requirements_summary(job)
    return "\n".join(
        [
            "Dear Hiring Team,",
            "",
            (
                f"I am applying for the {job.title} role at {job.company}. My recent technical delivery "
                f"work centres on {named_skills}, with a practical focus on stable service operations and "
                "clear communication with users and stakeholders. I have supported production environments "
                "where incident ownership, service improvement, and careful change management were expected "
                "every day."
            ),
            "",
            (
                "Across Microsoft 365 and infrastructure workloads, I have contributed to administration, "
                "migration, and recovery activities that balance delivery pace with operational risk. I am "
                "comfortable working across priorities, documenting decisions, and collaborating with peers "
                "to keep support outcomes consistent."
            ),
            "",
            (
                f"Your role description highlights {requirement_summary} That aligns with how I work: "
                "evidence-led, accountable, and focused on outcomes users can feel. I would value the "
                f"opportunity to contribute this approach to {job.company}."
            ),
            "",
            "Kind regards,",
            candidate_name or "Candidate",
        ]
    )


def _make_claims(skills: list[SkillEntry], role_target_ref: list[dict[str, str]]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for idx, entry in enumerate(skills, start=1):
        claims.append(
            {
                "id": f"claim_{idx:03d}",
                "text": f"Hands-on delivery in {entry.skill_name} across production service work.",
                "evidence_refs": _skill_evidence_refs(entry, limit=2),
                "supported": True,
            }
        )

    claims.append(
        {
            "id": f"claim_{len(claims) + 1:03d}",
            "text": "Current role targeting includes Microsoft 365 and infrastructure engineering positions.",
            "evidence_refs": role_target_ref,
            "supported": True,
        }
    )
    return claims


def _make_screening_answers(
    skills: list[SkillEntry],
    role_target: str,
    role_target_ref: list[dict[str, str]],
    truth_bank: dict[str, Any],
    right_to_work_field_path: str,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    needs_user_input: list[dict[str, str]] = []

    top_skills = ", ".join(entry.skill_name for entry in skills[:3]) or "Microsoft 365 support"
    skill_refs = _skill_evidence_refs(skills[0], limit=2) if skills else role_target_ref

    screening_answers: list[dict[str, Any]] = [
        {
            "question": "Why are you interested in this role?",
            "answer": (
                "The role aligns with my target direction in "
                f"{role_target or 'Microsoft 365 and infrastructure engineering'}, and with recent "
                f"hands-on delivery across {top_skills}."
            ),
            "evidence_refs": role_target_ref + skill_refs[:1],
        },
        {
            "question": "Which parts of this role match your recent experience?",
            "answer": (
                "The strongest overlap is in "
                f"{top_skills}, plus operational ownership for incidents and service improvements."
            ),
            "evidence_refs": skill_refs,
        },
    ]

    right_to_work, right_to_work_ref = _truth_bank_ref(truth_bank, right_to_work_field_path)
    if not right_to_work:
        needs_user_input.append(
            {
                "field": right_to_work_field_path,
                "reason": "Missing right-to-work details in truth_bank.yml",
            }
        )
    screening_answers.append(
        {
            "question": "Do you have the right to work in the UK?",
            "answer": right_to_work or NEEDS_INPUT,
            "evidence_refs": right_to_work_ref,
        }
    )

    notice_period, notice_ref = _truth_bank_ref(truth_bank, "availability.notice_period")
    if not notice_period:
        needs_user_input.append(
            {
                "field": "availability.notice_period",
                "reason": "Missing notice period in truth_bank.yml",
            }
        )
    screening_answers.append(
        {
            "question": "What is your notice period?",
            "answer": notice_period or NEEDS_INPUT,
            "evidence_refs": notice_ref,
        }
    )

    return screening_answers, needs_user_input


def _dedupe_needs(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, str]] = []
    for item in items:
        field = str(item.get("field", "")).strip()
        reason = str(item.get("reason", "")).strip()
        key = (field, reason)
        if not field or not reason or key in seen:
            continue
        seen.add(key)
        result.append({"field": field, "reason": reason})
    return result


def validate_guardrail_output(
    payload: dict[str, Any],
    contract: GuardrailContract = DEFAULT_GUARDRAIL_CONTRACT,
) -> dict[str, Any]:
    needs = list(payload.get("needs_user_input", []))

    claims = payload.get("claims", [])
    for idx, claim in enumerate(claims):
        refs = claim.get("evidence_refs") or []
        if contract.require_claim_evidence_refs and not refs:
            claim["supported"] = False
            needs.append(
                {
                    "field": f"claims[{idx}].evidence_refs",
                    "reason": "Claim is missing evidence references",
                }
            )
            continue
        if contract.require_non_empty_evidence_path:
            for ref_idx, ref in enumerate(refs):
                if not str(ref.get("path", "")).strip():
                    claim["supported"] = False
                    needs.append(
                        {
                            "field": f"claims[{idx}].evidence_refs[{ref_idx}].path",
                            "reason": "Evidence path cannot be empty",
                        }
                    )

    screening_answers = payload.get("screening_answers", [])
    for idx, answer in enumerate(screening_answers):
        refs = answer.get("evidence_refs") or []
        if not refs:
            if answer.get("answer") != NEEDS_INPUT:
                answer["answer"] = NEEDS_INPUT
            needs.append(
                {
                    "field": f"screening_answers[{idx}]",
                    "reason": "Screening answer is missing evidence references",
                }
            )
            continue
        if contract.require_non_empty_evidence_path:
            for ref_idx, ref in enumerate(refs):
                if not str(ref.get("path", "")).strip():
                    answer["answer"] = NEEDS_INPUT
                    needs.append(
                        {
                            "field": f"screening_answers[{idx}].evidence_refs[{ref_idx}].path",
                            "reason": "Evidence path cannot be empty",
                        }
                    )

    cover_letter_word_count = _word_count(str(payload.get("cover_letter_md", "")))
    if (
        cover_letter_word_count < contract.min_cover_words
        or cover_letter_word_count > contract.max_cover_words
    ):
        payload["cover_letter_md"] = NEEDS_INPUT
        needs.append(
            {
                "field": "cover_letter_md",
                "reason": (
                    f"Cover letter must be {contract.min_cover_words}-{contract.max_cover_words} words; "
                    f"found {cover_letter_word_count}"
                ),
            }
        )

    payload["needs_user_input"] = _dedupe_needs(needs)
    payload["status"] = NEEDS_INPUT if payload["needs_user_input"] else "OK"
    return payload


def generate_application_pack(
    job: Job,
    skills_profile: dict[str, Any],
    truth_bank: dict[str, Any],
    missing_requirements: list[str] | None = None,
    guardrail_contract: GuardrailContract = DEFAULT_GUARDRAIL_CONTRACT,
) -> dict[str, Any]:
    missing_requirements = missing_requirements or []
    needs_user_input: list[dict[str, str]] = []

    if "job" in guardrail_contract.required_inputs and not job:
        needs_user_input.append({"field": "job", "reason": "Missing required `job` input"})
    if "skills_profile" in guardrail_contract.required_inputs and not skills_profile:
        needs_user_input.append(
            {"field": "skills_profile", "reason": "Missing required `skills_profile` input"}
        )
    if "truth_bank" in guardrail_contract.required_inputs and not truth_bank:
        needs_user_input.append({"field": "truth_bank", "reason": "Missing required `truth_bank` input"})

    candidate = skills_profile.get("candidate", {})
    candidate_name = str(candidate.get("name", "")).strip()

    role_target, role_target_ref = _truth_bank_ref(truth_bank, "role_preferences.target_titles")
    if not role_target:
        fallback_role = job.title
        target_roles = skills_profile.get("target_roles", [])
        if isinstance(target_roles, list) and target_roles:
            first_role = str(target_roles[0]).strip()
            if first_role:
                fallback_role = first_role
        role_target = fallback_role
        role_target_ref = [
            _safe_path(
                source="skills_profile",
                path="target_roles[0]",
                quote=fallback_role,
            )
        ]

    skills = _select_relevant_skills(job, _skills_index(skills_profile))
    cv_variant_md = _build_cv_variant(job, skills=skills, missing_requirements=missing_requirements)
    cover_letter_md = _build_cover_letter(job, candidate_name=candidate_name, skills=skills)
    screening_answers, answer_needs = _make_screening_answers(
        skills=skills,
        role_target=role_target,
        role_target_ref=role_target_ref,
        truth_bank=truth_bank,
        right_to_work_field_path=guardrail_contract.right_to_work_field_path,
    )
    claims = _make_claims(skills=skills, role_target_ref=role_target_ref)

    payload = {
        "status": "OK",
        "cv_variant_md": cv_variant_md,
        "cover_letter_md": cover_letter_md,
        "screening_answers": screening_answers,
        "claims": claims,
        "needs_user_input": answer_needs + needs_user_input,
    }
    return validate_guardrail_output(payload, contract=guardrail_contract)


def run_pack_generation(
    session_factory: sessionmaker[Session],
    job_id: int,
    skills_profile_path: Path,
    truth_bank_path: Path,
    prompt_guardrail_path: Path | None = None,
) -> PackGenerationResult:
    guardrail_contract = load_prompt_guardrail_contract(
        prompt_guardrail_path or Path("prompt_guardrail.md")
    )
    with session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise LookupError(f"job not found: {job_id}")

        preload_needs: list[dict[str, str]] = []
        try:
            skills_profile = _load_json(skills_profile_path)
        except Exception:
            skills_profile = {}
            preload_needs.append(
                {
                    "field": "skills_profile",
                    "reason": f"Unable to load {skills_profile_path}",
                }
            )

        try:
            truth_bank = _load_yaml(truth_bank_path)
        except Exception:
            truth_bank = {}
            preload_needs.append(
                {
                    "field": "truth_bank",
                    "reason": f"Unable to load {truth_bank_path}",
                }
            )

        match = session.get(JobMatch, job_id)
        missing_requirements = (match.missing_json or []) if match else []
        payload = generate_application_pack(
            job=job,
            skills_profile=skills_profile,
            truth_bank=truth_bank,
            missing_requirements=missing_requirements[:3],
            guardrail_contract=guardrail_contract,
        )
        payload["needs_user_input"] = list(payload.get("needs_user_input", [])) + preload_needs
        payload = validate_guardrail_output(payload, contract=guardrail_contract)

        pack = ApplicationPack(
            job_id=job_id,
            cv_variant_md=payload["cv_variant_md"],
            cover_letter_md=payload["cover_letter_md"],
            screening_answers_json={"screening_answers": payload["screening_answers"]},
            evidence_map_json={
                "status": payload["status"],
                "claims": payload["claims"],
                "needs_user_input": payload["needs_user_input"],
                "missing_requirements": missing_requirements[:3],
            },
        )
        session.add(pack)
        session.commit()
        session.refresh(pack)

        return PackGenerationResult(pack_id=pack.id, job_id=job_id, status=str(payload["status"]))


def get_latest_application_pack(db: Session, job_id: int) -> ApplicationPack | None:
    stmt = (
        select(ApplicationPack)
        .where(ApplicationPack.job_id == job_id)
        .order_by(ApplicationPack.created_at.desc(), ApplicationPack.id.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()
