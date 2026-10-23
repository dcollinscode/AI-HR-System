from app.services.skill_matching import match_skills


def _match(skills, requirements=None, title="Backend Engineer", description=None):
    return match_skills(
        job_title=title,
        job_description=description,
        job_requirements=requirements,
        profile={"skills": skills},
    )


def test_explicit_skills_partial_coverage_qualifies():
    result = _match(
        ["Python", "Django"],
        {"technical_skills": ["Python", "Django", "PostgreSQL", "Docker"]},
    )
    assert result.matched == ["Python", "Django"]
    assert result.coverage == 0.5
    assert result.qualifies


def test_js_suffix_and_sentences_match():
    result = _match(
        ["React.js", "Node"],
        {"mandatory": ["3+ years of React experience", "NodeJS APIs", "AWS"]},
    )
    assert set(result.matched) == {"React.js", "Node"}
    assert result.qualifies


def test_no_overlap_does_not_qualify():
    result = _match(["Photoshop", "Illustrator"], {"skills": ["Python", "SQL"]})
    assert not result.matched
    assert not result.qualifies


def test_low_coverage_needs_three_matches():
    reqs = {"skills": [f"skill{i}" for i in range(20)] + ["Python"]}
    assert not _match(["Python"], reqs).qualifies
    big = {"skills": ["Python", "Go", "Rust"] + [f"x{i}" for i in range(30)]}
    assert _match(["Python", "Go", "Rust"], big).qualifies


def test_falls_back_to_job_text_when_no_skill_list():
    result = _match(
        ["Python", "Figma"],
        None,
        title="Data Engineer",
        description="Build pipelines in Python and SQL.",
    )
    assert result.matched == ["Python"]
    assert result.qualifies


def test_candidate_without_skills():
    assert not match_skills(
        job_title="x", job_description=None, job_requirements=None, profile=None
    ).qualifies


def test_string_skills_accepted():
    assert _match("python, django", {"skills": ["Python"]}).qualifies
