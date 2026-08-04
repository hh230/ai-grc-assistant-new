"""Investigation instruments — run by a human against a question, never by the gate.

The distinction this package exists to make STRUCTURAL rather than tribal:

  devteam_harness/*          the GATE. Runs on every PR, blocks a release, must never flake.
  devteam_harness/investigation/*   INSTRUMENTS. Run by hand when something is wrong, to find
                                    out what and to propose a measured fix.

Both are real work and both earn their keep, but they have different contracts. The gate must be
fast, deterministic and blocking. An instrument may be slow, may need an LLM or a live app, and
must never gate anything — its output is evidence for a human decision.

Keeping them in one flat namespace hid that: an audit of what the gate actually loads found that
these five modules were reachable only from their own tests, which reads as "unused code" to
anyone auditing the package and as "tested system behaviour" to anyone reading the suite. Neither
was true. They are instruments, and now they are shelved as instruments.

They are what produced the findings behind the knowledge-model fix:
  counterfactual  the binary maturity ladder, and `has_gov_clients` never moving the plan
  minimal_fix     33 threshold edits searched, all rejected
  intent          why all 33 were rejected — they destroyed the rule's meaning
  synthesis       the new rules that were adopted instead
  diff            how any of the above is reviewed at population scale
"""

from devteam_harness.investigation import counterfactual, diff, intent, minimal_fix, synthesis

__all__ = ["counterfactual", "diff", "intent", "minimal_fix", "synthesis"]
