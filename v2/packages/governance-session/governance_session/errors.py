"""The service's typed error taxonomy — routers map these to HTTP status codes (never a raw
exception leaks to a caller)."""

from __future__ import annotations


class GovernanceSessionError(Exception):
    """Base for everything this package raises."""


class SessionNotFound(GovernanceSessionError):
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"discovery session not found: {session_id}")


class SessionAlreadyConcluded(GovernanceSessionError):
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"discovery session already concluded: {session_id}")


class UnknownQuestion(GovernanceSessionError):
    def __init__(self, question_id: str) -> None:
        self.question_id = question_id
        super().__init__(f"unknown question: {question_id}")


class QuestionNotCurrentlyEligible(GovernanceSessionError):
    """Answering a question that isn't (or is no longer) in scope for this session — e.g. a stale
    client submitting a question that a prior answer already made irrelevant."""

    def __init__(self, question_id: str) -> None:
        self.question_id = question_id
        super().__init__(f"question is not currently eligible: {question_id}")


class InvalidAnswer(GovernanceSessionError):
    """The raw answer does not match the question's declared `value_type`/options (CLAUDE.md
    §22: validate at boundaries)."""

    def __init__(self, question_id: str, reason: str) -> None:
        self.question_id = question_id
        self.reason = reason
        super().__init__(f"invalid answer for {question_id}: {reason}")


class NoQuestionToGoBackTo(GovernanceSessionError):
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"no answered, in-scope question to go back to: {session_id}")
