"""Deterministic broad-spectrum stress test for V7.3.4 category intelligence."""
from __future__ import annotations
import random
from architecture_model import infer_architecture_profile
from commercial_knowledge import BUSINESS_PHRASE_EXPANSIONS, JOURNEY_PHRASE_EXPANSIONS
from test_v734_category_deep_dive import BUSINESS_CASES


def run(seed: int = 7344, business_trials: int = 100, journey_trials: int = 100, collision_trials: int = 1000):
    rng = random.Random(seed)
    business_total = business_ok = 0
    by_type = {}
    all_types = [x[0] for x in BUSINESS_CASES]
    for business_type, _, title, h1, base_text, actions in BUSINESS_CASES:
        phrases = [p for p,w in BUSINESS_PHRASE_EXPANSIONS.get(business_type,()) if float(w)>=3.0]
        good = 0
        for _ in range(business_trials):
            k=min(len(phrases), max(4, int(len(phrases)*rng.uniform(.35,.72))))
            chosen=rng.sample(phrases,k)
            # Add a small amount of realistic audience/adjacent-business noise.
            noise_type=rng.choice([x for x in all_types if x!=business_type])
            noise=[p for p,w in BUSINESS_PHRASE_EXPANSIONS.get(noise_type,()) if 2.0 <= float(w) <= 4.0]
            if noise and rng.random()<.70:
                chosen += rng.sample(noise, min(len(noise), rng.randint(1,2)))
            rng.shuffle(chosen)
            text=" ".join(chosen)+" "+" ".join(base_text.split()[:14])
            p=infer_architecture_profile({"title":title,"h1_tags":[h1],"page_text":text,"journey_text_sample":text,"mobile_cta_types":actions},"auto")
            business_total+=1
            if p["business_type"]==business_type:
                business_ok+=1; good+=1
        by_type[business_type]=good

    action_for={"lead_quote":"quote","appointment_consultation":"book","reservation_event":"reserve","direct_purchase":"buy","demo_sales":"demo","membership_subscription":"join","donation_support":"donate","application_enrollment":"apply"}
    journey_total=journey_ok=0
    by_journey={}
    for journey,items in JOURNEY_PHRASE_EXPANSIONS.items():
        strong=[p for p,w in items if float(w)>=5.0]
        good=0
        for _ in range(journey_trials):
            k=min(len(strong),max(2,int(len(strong)*rng.uniform(.35,.78))))
            chosen=rng.sample(strong,k); rng.shuffle(chosen)
            p=infer_architecture_profile({"title":"Organization","h1_tags":["Get started"],"page_text":" ".join(chosen),"journey_text_sample":" ".join(chosen),"mobile_cta_types":[action_for[journey]]},"auto")
            journey_total+=1
            if p["journey_model"]==journey:
                journey_ok+=1; good+=1
        by_journey[journey]=good

    # Cross-industry contamination: strong provider identity + a few audience words from another type.
    collision_ok=0
    for _ in range(collision_trials):
        business_type, _, title, h1, base_text, actions = rng.choice(BUSINESS_CASES)
        noise_type=rng.choice([x for x in all_types if x!=business_type])
        own=[p for p,w in BUSINESS_PHRASE_EXPANSIONS.get(business_type,()) if float(w)>=5.0]
        other=[p for p,w in BUSINESS_PHRASE_EXPANSIONS.get(noise_type,()) if 2.0 <= float(w)<=4.0]
        own_sample=rng.sample(own,min(len(own),max(3,min(6,len(own))))) if own else []
        other_sample=rng.sample(other,min(len(other),rng.randint(1,3))) if other else []
        text=" ".join(own_sample+other_sample)+" "+base_text
        p=infer_architecture_profile({"title":title,"h1_tags":[h1],"page_text":text,"journey_text_sample":text,"mobile_cta_types":actions},"auto")
        if p["business_type"]==business_type:
            collision_ok+=1

    return {
        "business": {"passed":business_ok,"total":business_total,"by_type":by_type},
        "journey": {"passed":journey_ok,"total":journey_total,"by_journey":by_journey},
        "collision": {"passed":collision_ok,"total":collision_trials},
    }

if __name__ == "__main__":
    result=run()
    print(result)
    b=result["business"]; j=result["journey"]; c=result["collision"]
    # Stress thresholds deliberately allow some noisy synthetic ambiguity; no forced classification is desired.
    assert b["passed"]/b["total"] >= .92, b
    assert j["passed"]/j["total"] >= .95, j
    assert c["passed"]/c["total"] >= .90, c
