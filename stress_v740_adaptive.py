"""Deterministic stress for V7.4 adaptive learning/eligibility safety boundaries."""
import os, random, tempfile
from pathlib import Path

from commercial_eligibility import evaluate_commercial_eligibility
from learning_intelligence import LearningMemory

rng=random.Random(740)
with tempfile.TemporaryDirectory() as td:
    os.environ['TRILLOKA_LEARNING_DB_PATH']=str(Path(td)/'learn.db')
    os.environ['TRILLOKA_LEARNING_AUTO_ACTIVATE_MIN_DOMAINS']='12'
    mem=LearningMemory()
    base={
        'title':'Vertical analytics software platform',
        'h1_tags':['Analytics platform for operations teams'],
        'meta_description':'API integrations SSO dashboard free trial request demo',
        'architecture_profile':{'business_type':'saas','journey_model':'demo_sales','context_tags':['enterprise_considered_purchase']},
        'schema_types':['SoftwareApplication'],'mobile_cta_types':['demo'],
    }
    # 12 independent confirmations may activate only bounded recognition hints.
    for i in range(12):
        mem.record_classification_confirmation(domain=f'saas-{i}.example',selected_business_type='saas',scan=base)
    bounded=0
    for i in range(5000):
        scan=dict(base)
        if rng.random()<.5:
            scan['title']=rng.choice(['Vertical analytics software','Operations intelligence platform','Workflow analytics platform'])
        overlay=mem.inference_overlay(scan)
        if all(0 <= float(v) <= mem.max_inference_boost for v in overlay.get('scores',{}).values()):
            bounded+=1
    # Eligibility false-positive / mixed-path stress.
    eligibility=0
    for i in range(5000):
        if i%2==0:
            scan={'title':'Public Heritage Archive','page_text':'government public information historical archive research library contact us','form_present':True}
            r=evaluate_commercial_eligibility(scan,{'business_type':'nonprofit','journey_model':'lead_quote'},'auto')
            eligibility += int(not r['allow_scan'])
        else:
            scan={'title':'City Museum Tickets','page_text':'museum exhibition tickets admission buy tickets membership gift shop reserve'}
            r=evaluate_commercial_eligibility(scan,{'business_type':'nonprofit','journey_model':'direct_purchase'},'auto')
            eligibility += int(r['allow_scan'])
    print({'learning_inference_trials':5000,'bounded':bounded,'eligibility_trials':5000,'eligibility_correct':eligibility,'max_inference_boost':mem.max_inference_boost})
    if bounded!=5000 or eligibility!=5000:
        raise SystemExit(1)
