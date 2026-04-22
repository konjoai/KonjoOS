# DREX Unified Spec (Kyro Pointer)

This repository consumes DREX architectural contracts but does not own the full specification document.

## Canonical Source

- Workspace path: `/Users/wscholl/drex/DREX_UNIFIED_SPEC.md`
- Treat the canonical document above as source of truth for DREX component contracts.

## Kyro-Local Contract Summary

For DREX-related work in this repository, enforce at minimum:

1. Explicit dtype boundaries; no implicit casting across module interfaces.
2. NaN/Inf detection at component boundaries.
3. Echo-state / routing / memory safety guards as defined in the canonical spec.
4. No performance claims without benchmark evidence and reproducible run artifacts.
5. No phase-level claims without corresponding gate evidence.

If canonical spec and local docs conflict, canonical spec wins.
