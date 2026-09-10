# SPDX-License-Identifier: MIT
"""Independent arithmetic and validity oracles for canonical quotient profiles.

The expected values below are literal hand calculations. No snippet or formula
parser is used to derive them. These cases validate the calculation stage only.
"""
import copy


def cases(c):
    row={k:c[k] for k in ['card_id','card_version','contract_hash','numerator_name','denominator_name']}
    row.update(scope_id='prod',period_start='2026-06-01T00:00:00Z',period_end='2026-07-01T00:00:00Z',
               numerator=3.,denominator=4.,numerator_evidence_ref='fixture:numerator',denominator_evidence_ref='fixture:denominator',source_system='fixture',source_snapshot_hash='a'*64)
    percent=c['scale']==100;proportion=c['kind']=='proportion';signed=c['numerator_min']<0
    result=[]
    def add(name,rows,value,status):result.append({'case_id':name,'rows':rows,'expect':{'value':value,'evaluation_status':status}})
    add('three_of_four',[row],75. if percent else .75,'ok')
    add('true_zero',[{**row,'numerator':0.}],0.,'ok')
    add('zero_denominator',[{**row,'numerator':0.,'denominator':0.}],None,'not_applicable')
    add('empty',[],None,'missing_input')
    add('duplicate',[row,dict(row)],None,'invalid_input')
    add('above_one',[{**row,'numerator':8.}],None if proportion else (200. if percent else 2.),'invalid_input' if proportion else 'ok')
    add('negative_numerator',[{**row,'numerator':-2.}],(-50. if percent else -.5) if signed else None,'ok' if signed else 'invalid_input')
    add('negative_denominator',[{**row,'denominator':-4.}],None,'invalid_input')
    add('missing_value',[{**row,'numerator':None}],None,'invalid_input')
    add('old_version',[{**row,'card_version':'stale'}],None,'invalid_input')
    add('old_contract',[{**row,'contract_hash':'b'*64}],None,'invalid_input')
    add('wrong_operand',[{**row,'numerator_name':'wrong_population'}],None,'invalid_input')
    add('missing_evidence',[{**row,'denominator_evidence_ref':' '}],None,'invalid_input')
    add('other_scope',[{**row,'scope_id':'other'}],None,'missing_input')
    add('other_period',[{**row,'period_end':'2026-08-01T00:00:00Z'}],None,'missing_input')
    add('card_id_case',[{**row,'card_id':row['card_id'].lower()}],None,'missing_input')
    add('scope_id_case',[{**row,'scope_id':'PROD'}],None,'missing_input')
    add('operand_case',[{**row,'numerator_name':row['numerator_name'].upper()}],None,'invalid_input')
    return copy.deepcopy(result)
