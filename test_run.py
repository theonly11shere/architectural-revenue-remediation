from scorer import run_full_audit_pipeline

# Trigger a test audit against a live target domain
test_payload = {
    "domain": "example.com",
    "business_type": "local_services"
}

print("Running hybrid audit pipeline...")
result = run_full_audit_pipeline(test_payload)

print("\n--- AUDIT RESULTS ---")
print(f"Domain: {result['domain']}")
print(f"Overall Score: {result['surface_metrics']['overall_score']}")
print(f"AI Spectrum Index: {result['surface_metrics']['ai_spectrum_pct']}% ({result['surface_metrics']['classification']})")
print(f"Key Friction Insight: {result['key_friction_insight']['reason']}")
print(f"Report Vault ID: {result['report_vault_id']}")