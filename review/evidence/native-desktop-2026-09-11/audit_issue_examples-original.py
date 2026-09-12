#!/usr/bin/env python3
"""Native issue examples supplement; independent hand-specified numeric oracles."""
import argparse,copy,hashlib,json,sys,tempfile,subprocess
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'recipes/ci'),str(ROOT/'recipes')]
from desktop_runner import execute,fixture_hash
from semantic_runner import equal

def fixtures(bundle):
    result=[]
    for cid,vectors in {
      'SOC-002':[('four_values_15h',[2,10,20,30],15,30,15.5),('duplicate_values',[2,2,10,30],6,30,11),('singleton',[7],7,7,7),('two_values',[2,10],6,10,6)],
      'CFG-002':[('four_values_9d',[1,9,20,30],9,30,15),('duplicate_values',[2,2,10,30],2,30,11),('singleton',[7],7,7,7),('two_values',[2,10],2,10,6)]}.items():
        p=bundle['profiles'][cid]['prepared_observations_v1']
        base=p['fixtures'][0]
        for name,values,p50,p90,mean in vectors:
            c=copy.deepcopy(base);c['name']='audit_issue/'+name
            rows=[]
            for i,value in enumerate(values):
                row=copy.deepcopy(base['rows'][0]);row.update(record_id='audit:'+str(i),evidence_ref='synthetic:audit:'+str(i))
                if cid=='SOC-002':
                    end=datetime(2026,6,20,tzinfo=timezone.utc)
                    row.update(occurred_at=(end-timedelta(hours=value)).isoformat(),detected_at=end.isoformat(),confirmed_at='2026-06-21T00:00:00Z')
                else:
                    end=datetime(2026,7,1,tzinfo=timezone.utc)
                    row.update(first_drift_detected_at=(end-timedelta(days=value)).isoformat(),period_end=end.isoformat())
                rows.append(row)
            c['rows']=rows;c['expected']=dict(p50=p50,p90=p90,valid_cases=len(values),invalid_cases=0)
            if cid=='SOC-002':c['expected'].update(mean_h=mean,severity_weighted_mean_h=mean)
            result.append((cid,p,c))
    for cid in ['STD-068','STD-069','STD-075']:
        p=bundle['profiles'][cid]['prepared_observations_v1'];base=p['fixtures'][0]
        fields=[k for k,s in p['plan']['inputs'].items() if s['type']=='number']
        for field in fields:
            c=copy.deepcopy(base);c['name']='audit_issue/missing_'+field;c['rows'][0][field]=None;c['expected']={k:None for k in base['expected']};c['status']='invalid_input'
            result.append((cid,p,c))
        for label,value in [('nan_text','NaN'),('positive_infinity_text','Infinity'),('negative_infinity_text','-Infinity'),('above_score_range',101)]:
            c=copy.deepcopy(base);c['name']='audit_issue/'+label;c['rows'][0][fields[0]]=value;c['expected']={k:None for k in base['expected']};c['status']='invalid_input'
            result.append((cid,p,c))
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--bundle',default='recipes/out');ap.add_argument('--out',required=True);a=ap.parse_args()
    if sys.platform!='win32':ap.error('Native Windows Excel required')
    source=ROOT/a.bundle/'execution-profiles.json';bundle=json.loads(source.read_text(encoding='utf-8'))
    for path,sha in bundle['source_files_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=sha:raise ValueError('Stale source: '+path)
    report=dict(engine='excel',execution_kind='native_desktop',stage='audit_issue_supplements',started_at=datetime.now(timezone.utc).isoformat(),profile_bundle_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),source_files_sha256=bundle['source_files_sha256'],runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),cases=[],aborted=False)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    args=SimpleNamespace(server=None,tom_assembly=None,adomd_assembly=None)
    try:
        with tempfile.TemporaryDirectory(prefix='osms-issue-examples-') as d:
            for cid,p,c in fixtures(bundle):
                row=dict(card_id=cid,case_id=c['name'],fixture=c,fixture_sha256=fixture_hash(c),expected=c['expected'],status='fail')
                try:
                    actual,version=execute(p,c,'excel',Path(d),args,True);report['engine_version']=version
                    errors=[k for k,v in c['expected'].items() if k not in actual or not equal(actual[k],v,p['plan']['output_contracts'].get(k))]
                    row.update(actual=actual,failed_outputs=errors,status='fail' if errors else 'pass')
                except Exception as exc:
                    row['error']=str(exc)+(str(exc.stderr)[:2000] if isinstance(exc,subprocess.CalledProcessError) else '')
                    report['aborted']=True
                report['cases'].append(row)
                out.write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
                print(cid,c['name'],row['status'],row.get('failed_outputs',row.get('error')),flush=True)
                if report['aborted']:break
    finally:
        report.update(completed_at=datetime.now(timezone.utc).isoformat(),passed=sum(r['status']=='pass' for r in report['cases']))
        report['failed']=len(report['cases'])-report['passed']
        out.write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    print(report['passed'],'passed;',report['failed'],'failed',flush=True)
    return int(report['aborted'] or report['failed'] or len(report['cases'])!=len(fixtures(bundle)))
if __name__=='__main__':raise SystemExit(main())
