import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, require_hr_or_admin
from app.db.models.application import Application
from app.db.models.enums import JobStatus, TalentPoolStatus
from app.db.models.job import Job
from app.db.models.user import User
from app.schemas.talent_pool import (
    TalentPoolAdd,
    TalentPoolCandidateOut,
    TalentPoolJobMatch,
    TalentPoolMatchRequest,
    TalentPoolMatchResponse,
    TalentPoolOut,
    TalentPoolStatusUpdate,
)
from app.services import talent_pool_service
from app.services.skill_matching import match_skills

router = APIRouter(prefix="/talent-pool", tags=["Talent Pool"])


def _skills_of(candidate) -> list[str]:
    """Skill names from the candidate profile (strings, or dicts with a name)."""
    raw = (candidate.profile_data or {}).get("skills") if candidate else None
    if isinstance(raw, str):
        raw = raw.split(",")
    skills: list[str] = []
    seen: set[str] = set()
    for item in raw or []:
        if isinstance(item, dict):
            item = item.get("name") or item.get("skill")
        text = str(item).strip() if item else ""
        if text and text.lower() not in seen:
            seen.add(text.lower())
            skills.append(text)
    return skills


def _job_matches(candidate, open_jobs) -> list[TalentPoolJobMatch]:
    """Open jobs this candidate fits on skills, best fit first."""
    if candidate is None:
        return []
    matches: list[TalentPoolJobMatch] = []
    for job in open_jobs:
        result = match_skills(
            job_title=job.title,
            job_description=job.description,
            job_requirements=job.requirements,
            profile=candidate.profile_data,
        )
        if result.qualifies:
            matches.append(
                TalentPoolJobMatch(
                    job_id=job.id,
                    job_title=job.title,
                    matched_skills=result.matched,
                    score=round(result.score, 3),
                )
            )
    matches.sort(key=lambda m: m.score, reverse=True)
    return matches


def _candidate_out(
    entry, open_jobs=(), deleted_app_ids=frozenset()
) -> TalentPoolCandidateOut:
    base = TalentPoolOut.model_validate(entry).model_dump()
    # A deleted application must not be linked from the pool.
    if base.get("source_application_id") in deleted_app_ids:
        base["source_application_id"] = None
    candidate = entry.candidate
    matching = _job_matches(candidate, open_jobs)
    relevant: list[str] = []
    for match in matching:
        for skill in match.matched_skills:
            if skill not in relevant:
                relevant.append(skill)
    return TalentPoolCandidateOut(
        **base,
        candidate_name=candidate.full_name if candidate else None,
        candidate_email=candidate.email if candidate else None,
        skills=_skills_of(candidate),
        relevant_skills=relevant,
        matching_jobs=matching,
    )


@router.post("/match", response_model=TalentPoolMatchResponse)
def match(
    data: TalentPoolMatchRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_hr_or_admin),
):
    matches = talent_pool_service.match_candidates(db, data)
    return TalentPoolMatchResponse(matches=matches)


@router.post("/{candidate_id}", response_model=TalentPoolOut, status_code=status.HTTP_201_CREATED)
def add_to_pool(
    candidate_id: uuid.UUID,
    data: TalentPoolAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hr_or_admin),
):
    entry = talent_pool_service.add_to_pool(
        db, candidate_id, data.source_application_id, data.consent, current_user.id
    )
    return TalentPoolOut.model_validate(entry)


@router.get("", response_model=list[TalentPoolCandidateOut])
def list_pool(
    db: Session = Depends(get_db),
    _: User = Depends(require_hr_or_admin),
    status_filter: TalentPoolStatus | None = Query(default=None, alias="status"),
):
    entries = talent_pool_service.list_pool(db, status_filter)
    open_jobs = db.query(Job).filter(Job.status == JobStatus.OPEN).all()
    source_ids = {e.source_application_id for e in entries if e.source_application_id}
    deleted_app_ids = (
        {
            row[0]
            for row in db.query(Application.id)
            .filter(Application.id.in_(source_ids), Application.deleted_at.isnot(None))
            .all()
        }
        if source_ids
        else set()
    )
    return [_candidate_out(e, open_jobs, deleted_app_ids) for e in entries]


@router.post("/{pool_id}/contact", response_model=TalentPoolOut)
def contact(
    pool_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_hr_or_admin),
):
    entry = talent_pool_service.update_status(
        db, pool_id, TalentPoolStatus.CONTACTED
    )
    return TalentPoolOut.model_validate(entry)


@router.patch("/{pool_id}/status", response_model=TalentPoolOut)
def update_status(
    pool_id: uuid.UUID,
    data: TalentPoolStatusUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_hr_or_admin),
):
    entry = talent_pool_service.update_status(db, pool_id, data.status)
    return TalentPoolOut.model_validate(entry)