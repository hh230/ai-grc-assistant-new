"""Tests for the AI Judge.

No network and no API key: the LLM is a seam, so what is tested is the parsing, the aggregation and
the failure handling — which is where a judge layer actually goes wrong. Whether a given model
scores a given plan 88 or 74 is not a property any test can pin, which is precisely why this layer
does not gate a release.
"""

from __future__ import annotations

import json
from typing import Any

from devteam_harness.judge import (
    CONCERN_THRESHOLD,
    DIMENSIONS,
    JudgePanel,
    build_prompt,
    judge_plan,
    parse_judgement,
)


class _Turn:
    def __init__(self, question_id: str, answer: Any, skipped: bool = False) -> None:
        self.question_id = question_id
        self.answer = answer
        self.skipped = skipped


class _Client:
    def __init__(self, response: str) -> None:
        self.response = response
        self.seen: dict[str, str] = {}

    def complete(self, *, system: str, user: str) -> str:
        self.seen = {"system": system, "user": user}
        return self.response


def _good_response(total: int = 88) -> str:
    return json.dumps(
        {
            "dimensions": {
                name: {"score": 18, "reason": f"{name} is sound"} for name, _ in DIMENSIONS
            },
            "total": total,
            "verdict": "Solid, specific advice.",
            "worst_problem": "",
        }
    )


# --- the prompt must contain what makes judging possible ---------------------------------------


def test_the_judge_sees_the_organization_s_own_answers() -> None:
    """Judging a plan without them only asks "is this reasonable in general" — which is exactly
    the generic-advice failure this layer exists to catch."""
    prompt = build_prompt(
        transcript=[_Turn("q:policy_state", "absent"), _Turn("q:employee_count", 45)],
        plan_items=[{"id": "seed:draft_policies", "priority": "high"}],
        reasoning="policies are missing",
    )
    assert "policy_state: 'absent'" in prompt
    assert "employee_count: 45" in prompt
    assert "draft_policies" in prompt
    assert "policies are missing" in prompt


def test_an_empty_plan_is_shown_as_empty_not_omitted() -> None:
    """An empty plan is the most damaging output there is; the judge must see that it is empty
    rather than see nothing and assume the section was left out."""
    prompt = build_prompt(transcript=[_Turn("q:policy_state", "absent")], plan_items=[], reasoning="")
    assert "the plan is EMPTY" in prompt


def test_skipped_answers_are_not_presented_as_answers() -> None:
    prompt = build_prompt(
        transcript=[_Turn("q:has_board", None, skipped=True)], plan_items=[], reasoning=""
    )
    assert "has_board" not in prompt


def test_the_judge_is_told_to_be_critical() -> None:
    """A judge that praises everything measures nothing."""
    client = _Client(_good_response())
    judge_plan(client, seed=1, transcript=[], plan_items=[])
    assert "Be critical" in client.seen["system"]
    assert "generic compliance boilerplate" in client.seen["system"]


# --- LLM output is untrusted input --------------------------------------------------------------


def test_a_valid_response_is_parsed() -> None:
    judgement = parse_judgement(3, _good_response(88))
    assert judgement.parsed
    assert judgement.total == 88
    assert len(judgement.dimensions) == len(DIMENSIONS)


def test_a_fenced_response_is_still_parsed() -> None:
    """Models routinely wrap JSON in a code fence despite being told not to. Failing on that would
    make the judge look broken when the model was merely being polite."""
    judgement = parse_judgement(3, f"```json\n{_good_response(75)}\n```")
    assert judgement.parsed
    assert judgement.total == 75


def test_an_unparseable_response_is_recorded_not_raised() -> None:
    """One bad response must not end a run over hundreds of plans."""
    judgement = parse_judgement(3, "I think the plan is quite good, actually.")
    assert not judgement.parsed
    assert judgement.raw


def test_a_score_outside_its_range_is_clamped_not_trusted() -> None:
    """A model error is not a reason to crash, and not a reason to believe 900/100 either."""
    payload = json.loads(_good_response())
    payload["total"] = 900
    payload["dimensions"]["relevance"]["score"] = -5
    judgement = parse_judgement(3, json.dumps(payload))
    assert judgement.total == 100
    assert next(d for d in judgement.dimensions if d.name == "relevance").score == 0


def test_a_non_object_response_is_refused() -> None:
    assert not parse_judgement(3, "[1, 2, 3]").parsed


# --- the trend is the point ---------------------------------------------------------------------


def test_the_panel_averages_only_what_it_could_score() -> None:
    panel = JudgePanel()
    panel.add(parse_judgement(1, _good_response(90)))
    panel.add(parse_judgement(2, _good_response(70)))
    panel.add(parse_judgement(3, "garbage"))
    assert panel.average == 80.0, "an unparseable response must not be counted as zero"
    assert len(panel.scored) == 2


def test_unparseable_responses_are_reported_never_silently_dropped() -> None:
    """The rule the whole harness follows: what did not run is reported."""
    panel = JudgePanel()
    panel.add(parse_judgement(1, _good_response(90)))
    panel.add(parse_judgement(2, "garbage"))
    assert "could not be parsed" in panel.render()


def test_concerning_plans_are_surfaced_worst_first() -> None:
    panel = JudgePanel()
    for seed, total in ((1, 95), (2, 40), (3, 65)):
        panel.add(parse_judgement(seed, _good_response(total)))
    concerning = panel.concerning
    assert [j.total for j in concerning] == [40, 65]
    assert all(j.total < CONCERN_THRESHOLD for j in concerning)


def test_dimension_averages_show_WHERE_quality_is_weak() -> None:
    """A blended total hides which dimension is dragging, which is the only actionable part."""
    weak = json.loads(_good_response(60))
    weak["dimensions"]["prioritisation"]["score"] = 4
    panel = JudgePanel()
    panel.add(parse_judgement(1, json.dumps(weak)))
    averages = panel.dimension_averages()
    assert averages["prioritisation"] == 4.0
    assert averages["relevance"] == 18.0


def test_an_empty_panel_does_not_claim_a_score() -> None:
    assert "no parseable judgements" in JudgePanel().render()
