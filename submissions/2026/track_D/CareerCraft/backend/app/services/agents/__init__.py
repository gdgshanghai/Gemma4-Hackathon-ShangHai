"""Agent orchestration layer.

Subagents are small, single-responsibility units that wrap one LLM
interaction (or its mock). Orchestrators (added in a later PR) sequence
subagents and apply per-stage fallback policy. See
``docs/specification/05-mission-agent-architecture.md``.
"""
