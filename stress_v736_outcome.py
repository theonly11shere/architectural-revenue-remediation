from __future__ import annotations
import random
from remediation_intelligence import CATEGORY_OUTCOME_PROFILES, JOURNEY_OUTCOME_PROFILES, RULE_REMEDIATION_BASE, build_outcome_remediation

BUSINESSES=[x for x in CATEGORY_OUTCOME_PROFILES if x!='general']
JOURNEYS=[x for x in JOURNEY_OUTCOME_PROFILES if x!='general']
RULES=list(RULE_REMEDIATION_BASE)
CONTEXTS=['sensitive_data','regulated_high_trust','commerce_payment','local_location_dependent','enterprise_considered_purchase','hospitality_event','recurring_commitment','donation_public_trust']

def run(seed=736, trials=30000):
    rng=random.Random(seed)
    ok=0
    unsafe=0
    missing=0
    for _ in range(trials):
        b=rng.choice(BUSINESSES); j=rng.choice(JOURNEYS); k=rng.choice(RULES)
        ctx=rng.sample(CONTEXTS, rng.randint(0,3))
        r=build_outcome_remediation(k,b,j,ctx)
        if not r:
            missing+=1; continue
        required=('technical','cro_ux','systems','why_recommend','success_check','outcome_measure','remediation_engine')
        if not all(str(r.get(x) or '').strip() for x in required):
            missing+=1; continue
        text=' '.join(str(r.get(x) or '') for x in ('technical','cro_ux','systems','why_recommend')).lower()
        # Guardrails: no automatic legal verdict and no promise of revenue uplift.
        if any(x in text for x in ('this is illegal','is noncompliant','guaranteed revenue','guaranteed uplift')):
            unsafe+=1; continue
        ok+=1
    return {'trials':trials,'passed':ok,'missing':missing,'unsafe':unsafe}

if __name__=='__main__':
    result=run()
    print(result)
    assert result['passed']==result['trials']
