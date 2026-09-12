import json,copy,sys
from pathlib import Path
sys.path[:0]=['recipes','recipes/ci']
import xlsx_dialect as xl
b=json.loads(Path('recipes/out/execution-profiles.json').read_text(encoding='utf-8'))
requests=[]
for cid in ['STD-068','STD-069','STD-075']:
    p=b['profiles'][cid]['prepared_observations_v1']
    columns=list(p['plan']['inputs'])
    field=next(k for k,v in p['plan']['inputs'].items() if v['type']=='number')
    path=Path('recipes/out/nonfinite-'+cid+'.xlsx').resolve()
    outputs=xl.build_workbook(copy.deepcopy(p['excel_spec']),copy.deepcopy(p['fixtures'][0]),str(path))
    requests.append(dict(card_id=cid,workbook=str(path),column=columns.index(field)+1,field=field,result_row=outputs['value']))
Path('recipes/out/nonfinite-requests.json').write_bytes((json.dumps(requests,indent=2)+'\n').encode())
print('Prepared three native IEEE input probes.')
