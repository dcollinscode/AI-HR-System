"""Skill-based matching between a job and a candidate profile.

Used to decide which talent-pool candidates get a job invite. Pure functions
(no DB / framework imports) so they are cheap to test.

A job's skills come from the skill-like sections of ``Job.requirements``
(``skills``, ``technical_skills``, ``mandatory``, ``preferred`` ...). When a job
has none, skills named in the title/description are used instead. A candidate
skill matches a job item when one token set contains the other, so "React.js"
matches "React", and "Python" matches "3+ years of Python experience".
"""
import re
from dataclasses import dataclass, field

SKILL_KEYS = (
    "skills",
    "technical_skills",
    "mandatory",
    "preferred",
    "must_have",
    "nice_to_have",
    "requirements",
)

# Invite when the candidate covers this share of the job's skill items...
MIN_COVERAGE = 0.34
# ...or clearly overlaps on this many distinct skills regardless of coverage.
MIN_MATCHED = 3

_TOKEN_RE = re.compile(r"[a-z0-9+#]+")
_NOISE = {
    "a", "an", "the", "of", "and", "or", "for", "in", "on", "with", "to", "at",
    "years", "year", "yrs", "experience", "knowledge", "strong", "good", "basic",
    "advanced", "proficiency", "proficient", "skills", "skill", "plus", "using",
    "working", "understanding", "ability", "excellent", "minimum", "min",
}


def _canonical_tokens(text: str) -> frozenset[str]:
    """Lower-cased tokens with noise dropped and ".js"/"js" suffix variants
    folded ("reactjs", "react.js" -> "react")."""
    tokens: list[str] = []
    for raw in _TOKEN_RE.findall(text.lower().replace(".", " ")):
        if raw in _NOISE:
            continue
        if len(raw) > 3 and raw.endswith("js") and not raw.endswith("+js"):
            raw = raw[:-2]
        tokens.append(raw)
    if len(tokens) > 1:
        tokens = [t for t in tokens if t != "js"] or tokens
    return frozenset(t for t in tokens if t)


def _as_list(value) -> list[str]:
    if isinstance(value, str):
        parts = re.split(r"[\n,;]+", value)
    elif isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                item = item.get("name") or item.get("skill") or item.get("requirement")
            if item:
                parts.append(str(item))
    else:
        return []
    return [p.strip() for p in parts if p and p.strip()]


def job_skill_items(requirements) -> list[str]:
    """Skill-like requirement strings from a job's ``requirements`` blob."""
    if not isinstance(requirements, dict):
        return _as_list(requirements) if isinstance(requirements, (str, list)) else []
    seen: set[str] = set()
    items: list[str] = []
    for key in SKILL_KEYS:
        for item in _as_list(requirements.get(key)):
            marker = item.lower()
            if marker not in seen:
                seen.add(marker)
                items.append(item)
    return items


def candidate_skills(profile: dict | None) -> list[str]:
    return _as_list((profile or {}).get("skills"))


def _matches(candidate_tokens: frozenset[str], item_tokens: frozenset[str]) -> bool:
    if not candidate_tokens or not item_tokens:
        return False
    return candidate_tokens <= item_tokens or item_tokens <= candidate_tokens


@dataclass
class SkillMatch:
    matched: list[str] = field(default_factory=list)  # candidate skill names
    total_items: int = 0  # job skill items considered
    matched_items: int = 0

    @property
    def coverage(self) -> float:
        return self.matched_items / self.total_items if self.total_items else 0.0

    @property
    def score(self) -> float:
        """0..1 ranking value: coverage, nudged up by the number of overlaps."""
        return min(1.0, self.coverage + 0.02 * len(self.matched))

    @property
    def qualifies(self) -> bool:
        if not self.matched:
            return False
        return len(self.matched) >= MIN_MATCHED or self.coverage >= MIN_COVERAGE


def match_skills(
    *,
    job_title: str,
    job_description: str | None,
    job_requirements,
    profile: dict | None,
) -> SkillMatch:
    cand_skills = candidate_skills(profile)
    cand_tokens = {s: _canonical_tokens(s) for s in cand_skills}
    cand_tokens = {s: t for s, t in cand_tokens.items() if t}
    if not cand_tokens:
        return SkillMatch()

    items = job_skill_items(job_requirements)
    if items:
        matched_skills: list[str] = []
        matched_items = 0
        for item in items:
            item_tokens = _canonical_tokens(item)
            hits = [s for s, t in cand_tokens.items() if _matches(t, item_tokens)]
            if hits:
                matched_items += 1
                for skill in hits:
                    if skill not in matched_skills:
                        matched_skills.append(skill)
        return SkillMatch(
            matched=matched_skills, total_items=len(items), matched_items=matched_items
        )

    # No explicit skill list: look for the candidate's skills in the job text.
    blob_tokens = _canonical_tokens(f"{job_title} {job_description or ''}")
    hits = [s for s, t in cand_tokens.items() if t <= blob_tokens]
    return SkillMatch(matched=hits, total_items=len(cand_tokens), matched_items=len(hits))
