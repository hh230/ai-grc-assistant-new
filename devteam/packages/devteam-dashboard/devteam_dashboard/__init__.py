"""Autonomous Platform Dev Team — Operations Dashboard (Operations Mode).

A local, presentation-only web view an operator keeps open during the day. It OBSERVES the running
ContinuousMonitor (from live GitHub, the monitor's log file, and the LaunchAgent plist) and drives
APPROVE/REJECT through the existing ``ApprovalGateway`` — never re-implementing any decision. All
contact with the runtime is funnelled through one seam (``RuntimeGateway``), which composes exactly
the public services ``operate.py`` composes. No business logic lives here; no runtime behavior,
deployment, or Core is changed; there is no database.
"""

__version__ = "0.1.0"
