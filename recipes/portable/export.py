# SPDX-License-Identifier: MIT
"""Export calculation stage separately from source-adapter and engine evidence."""
import hashlib
import json
from pathlib import Path
from .ratios import generate, DIALECTS


def build(cards, recipes, root, out):
    import soc003
    import esql_exact
    ratios=generate(cards)
    profiles={cid:{'canonical_quotient_v1':profile} for cid,profile in ratios.items()}
    from semantic.export import generate as semantic_generate,PROFILE as SEMANTIC_PROFILE
    semantic=semantic_generate(cards)
    for cid,p in semantic.items():profiles.setdefault(cid,{})[SEMANTIC_PROFILE]=p
    card=next(c for c in cards if c['id']=='SOC-003')
    profiles.setdefault('SOC-003',{})['incident_snapshot_v1']={
        'contract':{'card_id':'SOC-003','card_version':card['card_version'],'profile_version':soc003.VERSION,
            'stage':'typed_incident_snapshot','input_table':'incidents','primary_key':['scope_id','incident_id'],
            'cohort':card['reproducibility'],'source_adapter_status':'required',
            'date_columns':{'alert_at':'UTC timestamp nullable','ack_at':'UTC timestamp nullable','detected_at':'UTC timestamp nullable','contained_at':'UTC timestamp nullable','resolved_at':'UTC timestamp nullable'},
            'outputs':{n+'_'+key:{'unit':unit,'nullable':nullable,'absolute_tolerance':tol,'relative_tolerance':1e-12 if unit=='hours' else 0} for n in soc003.PAIRS for key,unit,nullable,tol in [('p50_h','hours',True,1e-8),('p90_h','hours',True,1e-8),('mean_h_supplementary','hours',True,1e-8),('valid_cases','count',False,0),('invalid_cases','count',False,0)]},
            'verification':{d:'not_run' for d in DIALECTS},'green_eligibility':'requires_confidence_and_risk_appetite_profiles'},
        'dialects':soc003.snippets(card['minimum_data_fields']),
        'excel_spec':soc003.excel_spec(card['minimum_data_fields']),
        'esql_protocol':{'execution_mode':'esql_export_python_exact_reducer','queries':esql_exact.queries(),
                        'reducer':'recipes/esql_exact.py','input_requirement':'Same immutable snapshot for count and row queries; reject warnings, partial results and count mismatch. Export row limit 10000; larger inputs require a complete separately materialized export.',
                        'native_percentile_claim':False}}
    incident_contract=profiles['SOC-003']['incident_snapshot_v1']['contract']
    for name in ('closed_cases','identity_errors','open_cases_at_period_end'):
        incident_contract['outputs'][name]={'unit':'count','nullable':name=='open_cases_at_period_end','absolute_tolerance':0,'relative_tolerance':0}
    incident_contract['diagnostic_statuses']={n+'_status':{'values':['ok','invalid_data','not_applicable','capacity_exceeded'],
        'native_string_outputs':['py','gsql','pg','kql','spl'],
        'xlsx_dax_rule':'Derive invalid_data from identity_errors or family invalid_cases > 0; otherwise not_applicable when family valid_cases = 0; otherwise ok. Invalid parameters must prevent execution.'} for n in soc003.PAIRS}
    for cid,ps in profiles.items():
        recipes[cid]['execution_profiles']={k:{'stage':p['contract']['stage'],
                'artifact':'execution-profiles.json','source_adapter_status':p['contract']['source_adapter_status'],
                'verification_status':'not_run'} for k,p in ps.items()}
    hashes={}
    for group in ['recipes/portable/*.py','recipes/semantic/*.py','recipes/gen_recipes.py','recipes/curated/*.json','recipes/fixtures/*.json','recipes/soc003.py','recipes/esql_exact.py','recipes/dax_profiles.py','recipes/ci/*.py','recipes/ci/*.ps1','recipes/export_implementation.py','recipes/xlsx_dialect.py','reference/assurance.py','reference/execution_store.py','catalog/osms-catalog.yaml','catalog/principles.yaml','reference/RUBRICS.md','reference/ASSURANCE_PROFILES.md','recipes/EXECUTION_PROFILES.md']:
        for p in sorted(Path(root).glob(group)):
            hashes[str(p.relative_to(root))]=hashlib.sha256(p.read_bytes()).hexdigest()
    payload={'schema_version':'1.0.0-draft','source_files_sha256':hashes,
             'stage_notice':'Calculation profiles are not raw-source adapters, approval decisions, or evidence of native engine execution.',
             'profiles':profiles}
    Path(out,'execution-profiles.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n')
    matrix=[]
    for c in cards:
        cid=c['id'];ps=profiles.get(cid,{})
        for d in DIALECTS:
            implementations=[]
            for profile_id,p in ps.items():
                mode='native_expression' if d in p['dialects'] else 'esql_export_python_exact_reducer' if d=='esql' and 'esql_protocol' in p else None
                if mode:implementations.append({'profile_id':profile_id,'stage':p['contract']['stage'],'mode':mode,'verification':'not_run'})
            legacy=recipes[cid]
            matrix.append({'card_id':cid,'card_version':c['card_version'],'dialect':d,
                           'implementations':implementations,'legacy_status':legacy['status'] if d in legacy.get('dialects',{}) else 'absent',
                           'raw_source_adapter':'not_verified','full_card_native_conformance':'not_established',
                           'outputs':{k:list(p['contract'].get('outputs',{})) for k,p in ps.items()}})
    coverage={'catalog_cards':len(cards),'dialects':list(DIALECTS),'matrix_rows':len(matrix),
              'canonical_quotient_cards':len(ratios),'additional_incident_snapshot_cards':1,'prepared_observation_cards':len(semantic),
              'cards_without_additional_profiles':len(cards)-len(profiles),
              'generation_is_verification':False,'matrix':matrix}
    jobs=[]
    for cid,p in ratios.items():
        schema=', '.join(f+':'+('real' if f in ('numerator','denominator') else 'datetime' if f.startswith('period_') else 'string') for f in p['contract']['columns'])
        jobs.append({'id':cid,'q':'let metric_inputs=datatable('+schema+')[ ];\n'+p['dialects']['kql']})
    for cid,p in semantic.items():
        schema=','.join(k+':'+{'number':'real','timestamp':'datetime','string':'string','boolean':'bool'}[s['type']] for k,s in p['plan']['inputs'].items())
        jobs.append({'id':cid,'q':'let osms_input=datatable('+schema+')[ ];\n'+p['dialects']['kql']})
    Path(out,'profile-kql-jobs.json').write_text(json.dumps(jobs)+'\n')
    Path(out,'execution-coverage.json').write_text(json.dumps(coverage,indent=2)+'\n')
    return payload
