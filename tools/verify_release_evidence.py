#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Require successful workflow evidence for the exact release source commit."""
import argparse,datetime,json,os,subprocess,time,urllib.request
import hashlib
from pathlib import Path

REQUIRED={'.github/workflows/validate.yml','.github/workflows/recipes-ci.yml'}

def evaluate(runs,commit):
    selected={}
    for run in runs:
        path=(run.get('path') or '').split('@')[0]
        if path not in REQUIRED or run.get('head_sha')!=commit:continue
        # A pull-request run normally checks GitHub's synthetic merge commit,
        # not head_sha. Release proof must be a push/dispatch of the exact source.
        if run.get('event') not in ('push','workflow_dispatch'):continue
        if path not in selected or (run['id'],run.get('run_attempt',1))>(selected[path]['id'],selected[path].get('run_attempt',1)):selected[path]=run
    errors=[];pending=[]
    for path in sorted(REQUIRED):
        run=selected.get(path)
        if run is None:pending.append(path+': no run for the release commit')
        elif run.get('status')!='completed':pending.append(path+': '+str(run.get('status')))
        elif run.get('conclusion')!='success':errors.append(path+': '+str(run.get('conclusion')))
    return {'commit':commit,'ok':not errors and not pending,'errors':errors,'pending':pending,
            'workflows':[{k:r.get(k) for k in ('id','run_attempt','path','head_sha','event','status','conclusion','html_url')} for _,r in sorted(selected.items())]}

def fetch_runs(repo,commit):
    headers={'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'}
    token=os.environ.get('GH_TOKEN')
    if token:headers['Authorization']='Bearer '+token
    runs=[];page=1
    while True:
        url=f'https://api.github.com/repos/{repo}/actions/runs?head_sha={commit}&per_page=100&page={page}'
        with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=30) as response:body=json.loads(response.read())
        rows=body['workflow_runs'];runs+=rows
        if len(rows)<100:return runs
        page+=1

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--repo',default=os.environ.get('GITHUB_REPOSITORY','OpenSecurityMetricsStandard/OSMS'))
    ap.add_argument('--commit');ap.add_argument('--wait-seconds',type=int,default=3600);ap.add_argument('--out',type=Path,default=Path('release/gate-evidence.json'))
    ap.add_argument('--download-artifacts',action='store_true');a=ap.parse_args()
    head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();commit=a.commit or head
    if commit!=head:ap.error('The checked-out source must be the release commit')
    end=time.monotonic()+a.wait_seconds
    while True:
        result=evaluate(fetch_runs(a.repo,commit),commit)
        if result['ok'] or result['errors'] or time.monotonic()>=end:break
        print('Waiting for required release-commit checks:', '; '.join(result['pending']),flush=True);time.sleep(15)
    result.update(repository=a.repo,checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  approval_claim=False,notice='Workflow evidence is a technical release gate, not a Board decision or proof of optional unrun engines.')
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+'\n')
    if not result['ok']:raise SystemExit('Release blocked: '+'; '.join(result['errors']+result['pending']))
    if a.download_artifacts:
        folder=a.out.parent/'engine-evidence'
        if folder.exists():raise SystemExit('Release blocked: engine-evidence already exists; use a fresh output directory')
        folder.mkdir()
        for run in result['workflows']:
            subprocess.run(['gh','run','download',str(run['id']),'--repo',a.repo,'--dir',str(folder/str(run['id']))],check=True,timeout=300)
        reports=list(folder.rglob('profile-report-*.json'))
        required_engines={'python','duckdb','formulas','postgresql','libreoffice','esql'}
        expected_bundle=hashlib.sha256(Path('recipes/out/execution-profiles.json').read_bytes()).hexdigest()
        seen=set()
        for file in reports:
            report=json.loads(file.read_text())
            if report.get('profile_bundle_sha256')!=expected_bundle:raise SystemExit('Release blocked: execution report does not match the generated release bundle')
            if not report.get('cases') or any(c.get('status')!='pass' for c in report['cases']):raise SystemExit('Release blocked: invalid or failing execution report '+str(file))
            seen.add((report.get('engine'),report.get('stage')))
        required={(engine,stage) for engine in required_engines for stage in ('calculation_inputs','prepared_observations')}
        if required-seen:raise SystemExit('Release blocked: missing engine evidence '+str(sorted(required-seen)))
    print('Required workflows passed for',commit)

if __name__=='__main__':main()
