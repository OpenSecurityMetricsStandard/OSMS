#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export one supported implementation with its contract and source identity.

Generate the bundle first. Incomplete legacy templates cannot be exported as a
completed implementation. This command writes local files; it does not publish.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import copy


def template_spec(spec, capacity):
    """Bound data and helper rows together; out-of-capacity input blocks results."""
    if not isinstance(capacity,int) or isinstance(capacity,bool) or not 1<=capacity<=99999:
        raise ValueError('Template capacity must be between 1 and 99999 rows')
    from xlsx_dialect import LETTER
    result=copy.deepcopy(spec)
    overflow=f'COUNTA(data!A${capacity+2}:{LETTER(len(spec["columns"]))}$1048576)'
    period='AND(ISNUMBER(result!$B$2),ISNUMBER(result!$B$3),result!$B$2<result!$B$3,LEN(TRIM(result!$B$1))>0)'
    result['outputs']={'template_input_valid':f'=IF(AND({overflow}=0,{period}),1,0)',
        **{key:'=IF(result!$B$'+str(spec.get('result_start',6))+'=1,'+formula[1:]+',NA())' for key,formula in spec['outputs'].items()}}
    if spec.get('tabular_outputs'):
        result['helpers']=[(key,'=IF(result!$B$'+str(spec.get('result_start',6))+'=1,'+formula[1:]+',NA())' if key in spec['tabular_outputs'] else formula) for key,formula in spec['helpers']]
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--bundle',type=Path,default=Path('recipes/out'))
    ap.add_argument('--card',required=True);ap.add_argument('--dialect',choices=['py','gsql','pg','kql','spl','esql','xlsx','dax'],required=True)
    ap.add_argument('--profile',help='Explicit profile ID if a card has multiple profiles')
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--workbook',action='store_true',help='Create an empty .xlsx template for the xlsx dialect')
    ap.add_argument('--template-rows',type=int,default=1000,help='Prepared input/helper rows in workbook mode, 1..99999 (default 1000)')
    a=ap.parse_args();path=a.bundle/'execution-profiles.json';bundle=json.loads(path.read_text(encoding='utf-8'))
    profiles=bundle['profiles'].get(a.card,{})
    if not profiles:ap.error('No additional completed calculation profile for this card; consult execution-coverage.json')
    profile_id=a.profile or (next(iter(profiles)) if len(profiles)==1 else None)
    if profile_id not in profiles:ap.error('Choose an available profile: '+', '.join(profiles))
    p=profiles[profile_id]
    if a.workbook and a.dialect!='xlsx':ap.error('--workbook requires --dialect xlsx')
    if a.workbook:
        import xlsx_dialect as xl
        root=Path(__file__).resolve().parents[1]
        for relative,expected in bundle['source_files_sha256'].items():
            source=root/relative
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest()!=expected:
                ap.error('Source/bundle mismatch for '+relative+'; regenerate the bundle before workbook export')
        if 'excel_spec' in p:spec=p['excel_spec']
        elif a.card=='SOC-003':
            import soc003
            card=next(c for c in json.loads((a.bundle/'catalog.json').read_text(encoding='utf-8')) if c['id']=='SOC-003')
            spec=soc003.excel_spec(card['minimum_data_fields'])
        else:ap.error('No workbook specification for this profile')
        if a.out.suffix.lower()!='.xlsx':ap.error('Workbook output must end in .xlsx')
        if not 1<=a.template_rows<=99999:ap.error('--template-rows must be between 1 and 99999')
        spec=template_spec(spec,a.template_rows)
        a.out.parent.mkdir(parents=True,exist_ok=True)
        xl.build_workbook(spec,{'rows':[{} for _ in range(a.template_rows)]},str(a.out))
    else:
        code=p['dialects'].get(a.dialect)
        if code is None and a.dialect=='esql' and 'esql_protocol' in p:
            code=json.dumps(p['esql_protocol'],indent=2)
        if code is None:ap.error('Requested dialect has no implementation in this profile')
        a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(code+'\n',encoding='utf-8',newline='\n')
    manifest={'card_id':a.card,'profile_id':profile_id,'dialect':a.dialect,'contract':p['contract'],
              'profile_bundle_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
              'implementation_sha256':hashlib.sha256(a.out.read_bytes()).hexdigest(),
              'exporter_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'verification_status':'not_attested_by_export','source_files_sha256':bundle['source_files_sha256']}
    if a.workbook:manifest['template']={'prepared_data_rows':a.template_rows,'data_row_range':[2,a.template_rows+1],
        'overflow_behavior':'Any nonempty input cell below the prepared row range makes template_input_valid=0 and blocks result cells.',
        'instructions':'Keep the data/result sheet names, input headers and helper formulas. Enter UTC numeric dates in result B2/B3, scope in B1. Paste values into input columns within the prepared rows. Generate a larger template before extending capacity. A 1 in template_input_valid checks capacity and parameters only; all card quality gates still apply.'}
    a.out.with_name(a.out.name+'.contract.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
    print(str(a.out)+' and its contract manifest written')

if __name__=='__main__':main()
