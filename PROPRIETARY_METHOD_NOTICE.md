# Trilloka Proprietary Method Boundary

The customer-facing product should explain enough of the methodology to make results understandable and actionable without publishing the private decision system.

Public/customer-safe:
- detected business type and confidence
- detected customer journey and confidence
- relevant context tags
- evidence receipts
- checkpoint PASS / FAIL / UNKNOWN / N/A outcomes
- plain-language findings
- prioritization labels
- three-angle remediation
- high-level architecture layer scores
- final Revenue Readiness Index

Private/server-side only:
- exact business-type inference signals/candidate scores
- exact journey inference signals/candidate scores
- scoring multipliers and internal rule weights
- calibration anchors/function
- ranking equations and tie-break rules
- family overlap/cap implementation
- private recommendation-selection logic
- internal Architect/Vault review state

Keep the backend repository private. Do not move scorer.py, checkpoint_engine.py, architecture_model.py, internal calibration data or private solution logic into public frontend JavaScript.
