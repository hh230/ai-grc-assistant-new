"""WorkerControlSettings is a plain, frozen value object — nothing to unit test beyond
construction; the interesting behavior (tick() consulting an injected WorkerControlPort)
is covered in test_worker.py."""

from __future__ import annotations

from datetime import timedelta

from grc_knowledge_worker import WorkerControlSettings


def test_worker_control_settings_is_a_frozen_value_object() -> None:
    settings = WorkerControlSettings(
        enabled=True, interval=timedelta(hours=12), manual_trigger_requested=False
    )
    assert settings.enabled is True
    assert settings.interval == timedelta(hours=12)
    assert settings.manual_trigger_requested is False
