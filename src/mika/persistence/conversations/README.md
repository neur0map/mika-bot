# Conversation persistence

This package stores privacy-safe conversation turn traces plus evidence-backed relationship claims,
immutable profile and policy versions, archive cursors, and content-free recall attribution. The
relationship-memory repository owns primitive DTOs and lifecycle/evidence reads without depending
on conversation-layer types. Runtime callers use short-session managed adapters so concurrent recall
and background observation never share an ORM session. The archive adapter validates both shared and
training archive schemas in read-only mode and reports invalid ordering rows without copying retained
media resources.
