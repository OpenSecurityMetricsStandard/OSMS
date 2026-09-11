#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check actual charter adoption, assignments and substantive review coverage."""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re

GATES=('critical_findings','independent_review','native_platform_evidence','source_traceability','pilot_and_mappings','quorum_and_publication')
EXPERTISE={'measurement','security_operations_risk','data_engineering','assurance'}
DISPOSITIONS={'accepted','rejected','deferred','accepted-risk'}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reference(value):
    return isinstance(value,str) and bool(re.fullmatch(r'https://github\.com/OpenSecurityMetricsStandard/OSMS/(?:issues|pull)/\d+(?:#[A-Za-z0-9_-]+)?',value))


def nonempty(value):return isinstance(value,str) and bool(value.strip())


def past_date(value):
    try:return isinstance(value,str) and date.fromisoformat(value)<=date.today()
    except ValueError:return False


def evaluate(record,matrix,charter_hash,packet_hash):
    errors=[];pending=[];members={};assignments={};reviews={}
    bindings={'bundle_sha256':matrix['bundle_sha256'],'catalog_sha256':matrix['catalog_sha256'],
              'charter_sha256':charter_hash,'packet_manifest_sha256':packet_hash}
    for k,v in bindings.items():
        if record.get(k)!=v:errors.append('stale_or_missing_binding:'+k)
    if not re.fullmatch('[0-9a-f]{40}',record.get('source_commit') or ''):pending.append('source_commit')
    for m in record.get('members',[]):
        key=m.get('member_id')
        if not nonempty(key) or key in members:errors.append('invalid_or_duplicate_member');continue
        if not nonempty(m.get('name')) or not reference(m.get('declaration_ref')):errors.append('missing_actual_member_declaration:'+key)
        if m.get('conflicts_declared') is not True:errors.append('missing_conflict_declaration:'+key)
        if not set(m.get('expertise',[]))<=EXPERTISE:errors.append('unknown_expertise:'+key)
        members[key]=m
    adoption=record.get('adoption')
    if not adoption:pending.append('charter_adoption')
    else:
        participants=adoption.get('participants',[]);recused=set(adoption.get('recused_members',[]))
        if len(participants)!=len(set(participants)) or set(participants)-members.keys() or not recused<=set(participants):errors.append('invalid_session_participants')
        voters=set(participants)-recused
        if len(voters)<3:errors.append('quorum_below_three')
        skills=set().union(*(set(members[k].get('expertise',[])) for k in voters if k in members))
        if EXPERTISE-skills:errors.append('missing_session_expertise')
        if adoption.get('disposition')!='accepted' or not past_date(adoption.get('date')) or not reference(adoption.get('record_ref')):errors.append('invalid_adoption_decision')
        if adoption.get('mandatory_gates')!=list(GATES):errors.append('mandatory_gate_contract_not_adopted')
        if adoption.get('single_failed_gate_blocks') is not True:errors.append('gate_consequence_not_adopted')
        if not nonempty(adoption.get('rationale')) or not isinstance(adoption.get('dissent'),list):errors.append('missing_adoption_rationale_or_dissent')
        schedule=adoption.get('checkpoints',[])
        if not schedule:errors.append('missing_review_timetable')
        for checkpoint in schedule:
            try:date.fromisoformat(checkpoint.get('date',''))
            except (TypeError,ValueError):errors.append('invalid_checkpoint_date')
            if not nonempty(checkpoint.get('purpose')) or not nonempty(checkpoint.get('schedule_rationale')):errors.append('missing_checkpoint_rationale')
    cards={c['card_id']:c for c in matrix['cards']}
    for a in record.get('assignments',[]):
        cid=a.get('card_id');ids=a.get('reviewer_ids',[])
        if cid not in cards or cid in assignments:errors.append('unknown_or_duplicate_assignment');continue
        if len(ids)!=len(set(ids)) or set(ids)-members.keys():errors.append('invalid_assignment_members:'+cid)
        if not nonempty(a.get('scope')):errors.append('missing_assignment_scope:'+cid)
        assignments[cid]=set(ids)
    for r in record.get('reviews',[]):
        cid=r.get('card_id');member=r.get('member_id');key=(cid,member)
        if cid not in cards or member not in members or key in reviews:errors.append('invalid_or_duplicate_review');continue
        card=cards[cid]
        if member not in assignments.get(cid,set()):errors.append('unassigned_review:'+cid)
        if r.get('source_card_sha256')!=card['source_card_sha256']:errors.append('stale_card_review:'+cid)
        if r.get('independent_of_implementation') is not True or cid in members[member].get('recused_card_ids',[]):errors.append('review_independence_not_established:'+cid)
        if not all(nonempty(r.get(k)) for k in ('population_assessment','decision_assessment','calculation_assessment','rationale')):errors.append('missing_substantive_review:'+cid)
        if not past_date(r.get('date')) or not reference(r.get('record_ref')):errors.append('missing_review_record:'+cid)
        if r.get('disposition') not in DISPOSITIONS:errors.append('invalid_review_disposition:'+cid)
        cases=r.get('case_ids',[])
        if not cases or len(cases)!=len(set(cases)) or set(cases)-set(card['required_case_ids']):errors.append('missing_or_unknown_review_cases:'+cid)
        if r.get('disposition') in ('deferred','accepted-risk'):
            if not nonempty(r.get('followup_owner')) or not nonempty(r.get('followup_criterion')):errors.append('missing_followup:'+cid)
            try:date.fromisoformat(r.get('followup_due',''))
            except (TypeError,ValueError):errors.append('invalid_followup_due:'+cid)
        reviews[key]=r
    required={cid:c for cid,c in cards.items() if c['priority']=='P0' or c['independent_reviewers_required']==2}
    coverage=[]
    for cid,c in required.items():
        assigned=len(assignments.get(cid,set()));accepted=sum(r.get('disposition')=='accepted' for (k,_),r in reviews.items() if k==cid)
        need=c['independent_reviewers_required']
        if assigned<need:pending.append('assignment:'+cid)
        if accepted<need:pending.append('substantive_review:'+cid)
        coverage.append({'card_id':cid,'required_reviewers':need,'assigned':assigned,'accepted_reviews':accepted})
    gates=record.get('gates',{})
    if set(gates)-set(GATES):errors.append('unknown_mandatory_gate')
    for name in GATES:
        g=gates.get(name,{})
        if g.get('status')!='pass':pending.append('mandatory_gate:'+name)
        elif not reference(g.get('record_ref')) or not nonempty(g.get('rationale')):errors.append('missing_gate_evidence:'+name)
    return {'bindings':bindings,'structural_errors':errors,'pending':pending,'coverage':coverage,
        'ready_for_formal_promotion':not errors and not pending,'actual_board_approval_claim':False,
        'notice':'Record consistency only; authenticate the linked actual decisions separately. Deferred and accepted-risk reviews do not count as accepted semantic coverage. Every adopted mandatory gate must pass.'}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--packet',required=True);ap.add_argument('--record');ap.add_argument('--out',required=True)
    ap.add_argument('--prepare-record',action='store_true')
    ap.add_argument('--charter',default='review/BOARD_CHARTER_PROPOSAL.md');ap.add_argument('--require-complete',action='store_true');a=ap.parse_args()
    packet=Path(a.packet);matrix=json.loads((packet/'review-matrix.json').read_text());manifest=json.loads((packet/'manifest.json').read_text())
    for name,digest in manifest['files'].items():
        if sha(packet/name)!=digest:ap.error('Changed packet file: '+name)
    if matrix['catalog_sha256']!=sha(Path(__file__).resolve().parents[1]/'catalog/osms-catalog.yaml'):
        ap.error('Packet refers to a different source catalog')
    if a.prepare_record:
        result={'source_commit':None,'bundle_sha256':matrix['bundle_sha256'],'catalog_sha256':matrix['catalog_sha256'],
            'charter_sha256':sha(a.charter),'packet_manifest_sha256':sha(packet/'manifest.json'),
            'members':[],'adoption':None,'assignments':[],'reviews':[],
            'gates':{k:{'status':'pending','record_ref':None,'rationale':None} for k in GATES}}
        Path(a.out).write_text(json.dumps(result,indent=2)+'\n');print('Prepared an unapproved record; no actual member or decision inserted');return 0
    if not a.record:ap.error('Verification requires --record')
    result=evaluate(json.loads(Path(a.record).read_text()),matrix,sha(a.charter),sha(packet/'manifest.json'))
    Path(a.out).write_text(json.dumps(result,indent=2)+'\n');print(len(result['structural_errors']),'errors;',len(result['pending']),'pending requirements')
    return int(bool(result['structural_errors']) or a.require_complete and not result['ready_for_formal_promotion'])


if __name__=='__main__':raise SystemExit(main())
