# SPDX-License-Identifier: MIT
"""Evidence-bound calculation primitives for the OSMS maintainer draft.

No built-in organization-specific risk appetite, source authority register or
normalization anchors. Callers supply and version those inputs explicitly.
"""
import hashlib
import json
import math
from datetime import datetime, timezone
from statistics import median, NormalDist

CONFIDENCE_WEIGHTS = {'completeness':.25,'freshness':.25,'source_authority':.20,
                      'consistency':.15,'reconciliation_quality':.15}


def finite(value, name, lo=None, hi=None):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError(name+': finite numeric value required')
    if lo is not None and value<lo or hi is not None and value>hi:
        raise ValueError(name+': outside the declared domain')
    return float(value)


def identity(value, name):
    if not isinstance(value,str) or not value.strip():raise ValueError(name+': nonempty identifier required')
    return value


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def valid_period(start, end):
    def parse(value):
        identity(value,'period timestamp')
        dt=datetime.fromisoformat(value.replace('Z','+00:00'))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    if parse(start)>=parse(end):raise ValueError('Increasing UTC reporting period required')


def confidence(dimensions, profile_version, scope_id, period_start, period_end, *, reported_card_id, reported_card_version):
    """Profile dq-checks/1: documented check pass fractions, all five mandatory.

    Each dimension supplies passed/eligible check counts, evidence_ref and its
    check_definition_version. The caller owns the population register. Zero or
    missing basis never becomes 100. Mandatory failures cannot be compensated by
    high values in the other dimensions. This is data quality, not a probability
    that the KPI is correct or a statistical confidence interval.
    """
    for key,v in [('profile_version',profile_version),('scope_id',scope_id),('period_start',period_start),('period_end',period_end)]:identity(v,key)
    valid_period(period_start,period_end)
    identity(reported_card_id,'reported_card_id');identity(reported_card_version,'reported_card_version')
    if set(dimensions)!=set(CONFIDENCE_WEIGHTS):raise ValueError('Exactly five confidence dimensions required')
    scores={};failures=[]
    for name in CONFIDENCE_WEIGHTS:
        d=dimensions[name]
        for k in ['evidence_ref','check_definition_version']:identity(d.get(k),name+'.'+k)
        n=finite(d.get('eligible'),name+'.eligible',0);x=finite(d.get('passed'),name+'.passed',0,n)
        if not x.is_integer() or not n.is_integer():raise ValueError('Check counts must be integers')
        f=d.get('mandatory_failures')
        if not isinstance(f,list) or any(not isinstance(v,str) or not v.strip() for v in f):
            raise ValueError('Explicit mandatory_failures list required, including [] when none')
        failures.extend(name+':'+v for v in f)
        scores[name]=100*x/n if n else None
    incomplete=any(v is None for v in scores.values())
    score=None if incomplete else math.fsum(CONFIDENCE_WEIGHTS[k]*scores[k] for k in scores)
    valid=not incomplete and not failures
    return {'profile_id':'dq-checks/1','profile_version':profile_version,'scope_id':scope_id,
            'reported_card_id':reported_card_id,'reported_card_version':reported_card_version,
            'period_start':period_start,'period_end':period_end,'dimensions':scores,'score':score,
            'mandatory_failures':failures,'status':'valid' if valid else ('insufficient_basis' if incomplete else 'invalid_data'),
            'operational_green_eligible':valid and score>=70,'management_green_eligible':valid and score>=85,
            'input_hash':fingerprint(dimensions)}


def normalize(raw_value, profile):
    """Piecewise-linear posture [0,100]. Preserve raw value and profile hash.

    higher: red < target; lower: target < red. band: red_low < target_low
    <= target_high < red_high. The entire good band maps to 100. Anchors are
    explicitly versioned risk-appetite inputs, never estimated from the sample.
    """
    for k in ['profile_id','profile_version','card_id','card_version','output_id','unit','evidence_ref']:
        identity(profile.get(k),k)
    raw=finite(raw_value,'raw_value');direction=profile.get('direction')
    if direction in ('higher','lower'):
        red,target=finite(profile.get('red'),'red'),finite(profile.get('target'),'target')
        if direction=='higher' and not red<target or direction=='lower' and not target<red:
            raise ValueError('Normalization anchors conflict with direction or have zero width')
        value=100*(raw-red)/(target-red)
    elif direction=='band':
        rl,tl,th,rh=[finite(profile.get(k),k) for k in ['red_low','target_low','target_high','red_high']]
        if not rl<tl<=th<rh:raise ValueError('Invalid band anchors')
        value=100 if tl<=raw<=th else 100*(raw-rl)/(tl-rl) if raw<tl else 100*(rh-raw)/(rh-th)
    else:raise ValueError('Unknown normalization direction')
    return {'raw_value':raw,'posture_score':min(100,max(0,value)),
            'profile_hash':fingerprint(profile),'card_id':profile['card_id'],'output_id':profile['output_id']}


def weighted_components(rows, expected, context, *, average=False):
    """Rebuild contributions from input values and fixed profile weights.

    expected maps component IDs to {weight, card_version, normalization_hash}.
    No reweighting around missing children. Each row binds scope/period/profile,
    evidence and its exact upstream version/normalization profile. Any stored
    contribution is checked against independent multiplication.
    """
    for k in ['scope_id','period_start','period_end','profile_version']:identity(context.get(k),k)
    valid_period(context['period_start'],context['period_end'])
    if not expected or len(rows)!=len(expected):raise ValueError('Missing or duplicate components')
    seen=set();contributions=[];weights=[]
    for row in rows:
        key=row.get('component_id')
        if key not in expected or key in seen:raise ValueError('Unknown or duplicate component')
        seen.add(key);spec=expected[key]
        for k,v in context.items():
            if row.get(k)!=v:raise ValueError('Component context mismatch: '+k)
        for k in ['card_version','normalization_hash']:
            identity(spec.get(k),k)
            if row.get(k)!=spec[k]:raise ValueError('Component version/profile mismatch: '+k)
        identity(row.get('evidence_ref'),'evidence_ref')
        w=finite(spec.get('weight'),'profile weight',0);v=finite(row.get('value'),'posture input',0,100)
        if row.get('weight')!=w:raise ValueError('Input weight differs from frozen profile')
        contribution=w*v
        if 'stored_contribution' in row and not math.isclose(finite(row['stored_contribution'],'stored contribution'),contribution,rel_tol=1e-12,abs_tol=1e-9):
            raise ValueError('Stored contribution differs from recomputation')
        weights.append(w);contributions.append(contribution)
    total=math.fsum(weights)
    if total<=0:raise ValueError('No positive weight')
    if not average and not math.isclose(total,1,rel_tol=0,abs_tol=1e-12):raise ValueError('Composite weights must sum to one')
    return {'value':math.fsum(contributions)/(total if average else 1),
            'contributions':dict(zip([r['component_id'] for r in rows],contributions)),
            'profile_hash':fingerprint({'expected':expected,'context':context}),'input_hash':fingerprint(rows)}


def wilson_interval(successes, trials, *, confidence_level=.95, sampling_design, selection_note):
    """Wilson interval for unweighted independent Bernoulli samples only.

    Unknown selection mechanism, convenience samples, repeated clustered cases,
    weighted estimates and complete censuses must not be relabelled binomial.
    Selection bias is recorded separately; an interval does not repair it.
    """
    identity(selection_note,'selection_note')
    x=finite(successes,'successes',0);n=finite(trials,'trials',0)
    if not x.is_integer() or not n.is_integer() or x>n:raise ValueError('Invalid binomial counts')
    level=finite(confidence_level,'confidence_level')
    if not 0<level<1:raise ValueError('Confidence level must lie in (0,1)')
    if sampling_design!='independent_probability_sample' or not n:
        return {'status':'not_applicable','lower':None,'upper':None,'sample_size':int(n),'selection_note':selection_note}
    z=NormalDist().inv_cdf((1+level)/2);p=x/n;den=1+z*z/n
    middle=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return {'status':'calculated','method':'Wilson score','confidence_level':level,
            'lower':max(0,middle-half),'upper':min(1,middle+half),'sample_size':int(n),'selection_note':selection_note}


def portfolio_risk(draws, scenario_ids, profile, risk_appetite):
    """Aggregate supplied joint annual draws, preserving their dependency model.

    Each draw has the same scenario keys and one annual loss per scenario. This
    reducer does not invent distributions or assume independence. Generation
    method, horizon, currency, dependence, control-credit policy and input
    snapshot must be declared in the profile. Missing scenarios invalidate a draw;
    neither missing draws nor negative losses are silently excluded.
    """
    for k in ['profile_id','profile_version','horizon','currency','dependence_model','generator_version','input_snapshot_hash','control_credit_policy','evidence_ref']:
        identity(profile.get(k),k)
    finite(risk_appetite,'risk_appetite',0)
    expected=set(scenario_ids)
    if not expected or len(expected)!=len(scenario_ids):raise ValueError('Unique scenario IDs required')
    if not draws:raise ValueError('No joint draws supplied')
    totals=[];seen=set()
    for d in draws:
        key=identity(d.get('draw_id'),'draw_id')
        if key in seen:raise ValueError('Duplicate draw ID')
        seen.add(key)
        if set(d['losses'])!=expected:raise ValueError('Incomplete joint draw')
        totals.append(math.fsum(finite(v,'annual loss',0) for v in d['losses'].values()))
    totals.sort();n=len(totals)
    return {'mean':math.fsum(totals)/n,'p50':median(totals),'p90':totals[math.ceil(.9*n)-1],
            'probability_exceeding_appetite':sum(v>risk_appetite for v in totals)/n,'joint_draws':n,
            'profile_hash':fingerprint(profile),'input_hash':fingerprint(draws),
            'status':'model_estimate','unit':profile['currency']+'/'+profile['horizon']}


DSPS_WEIGHTS={'STD-006':.25,'STD-014':.08,'STD-015':.06,'STD-013':.04,'STD-029':.02,
              'SOC-002':.06,'SOC-003':.06,'SOC-004':.05,'SOC-009':.03,'STD-008':.15,
              'STD-007':.04,'STD-053':.035,'STD-054':.025,'STD-011':.10}


def dsps(children, penalties, normalization_profiles, context, penalty_versions):
    """STD-001 from raw child outputs and frozen normalization profiles.

    Every required child occurs once. Normalization is recomputed; an optional
    cached posture value is checked. Both capped penalty identities are mandatory,
    including explicit evidence-backed zeros. Period/scope/profile versions must
    match; no missing-child weight redistribution or silent penalty default.
    """
    if set(normalization_profiles)!=set(DSPS_WEIGHTS) or len(children)!=14:
        raise ValueError('Exactly fourteen DSPS child profiles and rows required')
    seen=set();rebuilt=[];expected={}
    for row in children:
        cid=row.get('component_id')
        if cid not in DSPS_WEIGHTS or cid in seen:raise ValueError('Unknown/duplicate DSPS child')
        seen.add(cid);p=normalization_profiles[cid]
        if p.get('card_id')!=cid or row.get('output_id')!=p.get('output_id'):raise ValueError('Wrong normalized child output')
        calc=normalize(row.get('raw_value'),p)
        if 'posture_score' in row and not math.isclose(finite(row['posture_score'],'cached posture',0,100),calc['posture_score'],rel_tol=1e-12,abs_tol=1e-9):
            raise ValueError('Cached posture differs from raw-value normalization')
        expected[cid]={'weight':DSPS_WEIGHTS[cid],'card_version':p['card_version'],'normalization_hash':calc['profile_hash']}
        rebuilt.append({**row,'value':calc['posture_score']})
    score=weighted_components(rebuilt,expected,context)
    if len(penalties)!=2 or {p.get('card_id') for p in penalties}!={'STD-001a','STD-001b'}:
        raise ValueError('Exactly one TSP and one EDP required')
    amounts=[]
    for p in penalties:
        for k,v in context.items():
            if p.get(k)!=v:raise ValueError('Penalty context mismatch: '+k)
        for k in ['card_version','evidence_ref']:identity(p.get(k),'penalty '+k)
        # Expected penalty versions are explicit in the frozen evaluation context.
        expected_version=penalty_versions.get(p['card_id'])
        if not expected_version or p['card_version']!=expected_version:raise ValueError('Penalty version mismatch')
        amounts.append(finite(p.get('value'),'penalty',0,25 if p['card_id']=='STD-001a' else 15))
    return {**score,'before_penalties':score['value'],'value':max(0,min(100,score['value']-math.fsum(amounts))),
            'penalties':{p['card_id']:p['value'] for p in penalties},'normalization_profile_hash':fingerprint(normalization_profiles)}


def rank_services(asset_rows, service_profiles, context):
    """STD-003: independent asset risk -> raw service priority -> displayed rank.

    Ranking population is exactly the explicit service profile set. Tie break is
    stable ascending service ID; equal raw values retain the same competition
    rank. Display scaling never changes ordering. A zero maximum yields zero
    display scores for known zero-risk inputs, not division by zero.
    """
    if not service_profiles:raise ValueError('Explicit ranking population required')
    for k in ['scope_id','period_end','card_version','profile_version']:identity(context.get(k),k)
    totals={k:[] for k in service_profiles};seen=set()
    for sid,p in service_profiles.items():
        identity(sid,'service_id');identity(p.get('evidence_ref'),'BIA/dependency evidence')
        if p.get('criticality_multiplier') not in (1,1.25,1.5,2) or p.get('dependency_multiplier') not in (1,1.25,1.5):
            raise ValueError('Ranking multiplier outside the declared STD-003 scale')
    for row in asset_rows:
        sid=row.get('service_id');aid=identity(row.get('asset_id'),'asset_id')
        if sid not in totals or (sid,aid) in seen:raise ValueError('Unknown service or duplicate service/asset risk')
        seen.add((sid,aid))
        for k,v in context.items():
            if row.get(k)!=v:raise ValueError('Ranking context mismatch: '+k)
        identity(row.get('evidence_ref'),'asset risk evidence')
        totals[sid].append(finite(row.get('asset_risk_value'),'asset risk',0,100))
    if any(not v for v in totals.values()):raise ValueError('No evidenced asset-risk basis for a ranking entity')
    raw={sid:math.fsum(values)*service_profiles[sid]['criticality_multiplier']*service_profiles[sid]['dependency_multiplier'] for sid,values in totals.items()}
    order=sorted(raw,key=lambda sid:(-raw[sid],sid));maximum=max(raw.values());result=[];prior=None;rank=0
    for i,sid in enumerate(order,1):
        if raw[sid]!=prior:rank=i
        prior=raw[sid]
        result.append({'service_id':sid,'rank':rank,'raw_priority':raw[sid],
                       'display_score':100*raw[sid]/maximum if maximum else 0})
    return {'ranking':result,'input_hash':fingerprint(asset_rows),'profile_hash':fingerprint({'services':service_profiles,'context':context})}
