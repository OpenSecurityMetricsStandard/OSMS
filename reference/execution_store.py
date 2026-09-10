# SPDX-License-Identifier: MIT
"""Immutable calculation evidence for historical, multi-output OSMS reports.

The receipt hash must be retained separately from the report being checked.
Hash agreement detects changes against that receipt; it does not authenticate
the original source or the person who attested population completeness.
"""
import hashlib,json,platform,sqlite3,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'recipes'))
from semantic import model

FILES={'contract.json','observations.json','parameters.json','result.json','runtime.json'}

def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')
def sha(data):return hashlib.sha256(data).hexdigest()
def interpreter_hash():return sha(Path(model.__file__).read_bytes())

class EvidenceError(ValueError):pass

def initialize(con):
    con.executescript('''CREATE TABLE IF NOT EXISTS execution_report (
      report_id TEXT PRIMARY KEY, card_id TEXT NOT NULL, card_version TEXT NOT NULL,
      scope_id TEXT NOT NULL, period_start TEXT NOT NULL, period_end TEXT NOT NULL,
      manifest_sha256 TEXT NOT NULL, manifest_json TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS execution_file (
      report_id TEXT NOT NULL REFERENCES execution_report(report_id), name TEXT NOT NULL,
      content BLOB NOT NULL, PRIMARY KEY(report_id,name));''')

def capture(con,report_id,plan,observations,parameters):
    if not isinstance(report_id,str) or not report_id.strip():raise ValueError('Stable report ID required')
    actual_hash=sha(encoded({k:v for k,v in plan.items() if k!='contract_hash'}))
    if actual_hash!=plan.get('contract_hash'):raise EvidenceError('CONTRACT_HASH_MISMATCH')
    result=model.compute(plan,observations,parameters)
    files={'contract.json':encoded(plan),'observations.json':encoded(observations),
           'parameters.json':encoded(parameters),'result.json':encoded(result),
           'runtime.json':encoded({'profile_version':model.VERSION,'interpreter_sha256':interpreter_hash(),'python_version':platform.python_version()})}
    manifest={'schema_version':'execution-receipt/1','report_id':report_id,'card_id':plan['card_id'],'card_version':plan['card_version'],
              'scope_id':parameters['scope_id'],'period_start':parameters['period_start'],'period_end':parameters['period_end'],
              'files':{name:sha(data) for name,data in files.items()}}
    payload=encoded(manifest);receipt=sha(payload)
    initialize(con)
    # INSERT deliberately rejects an existing report ID, even if its version
    # has since been deactivated in the current card registry.
    with con:
        con.execute('INSERT INTO execution_report VALUES (?,?,?,?,?,?,?,?)',
            (report_id,plan['card_id'],plan['card_version'],parameters['scope_id'],parameters['period_start'],parameters['period_end'],receipt,payload.decode()))
        con.executemany('INSERT INTO execution_file VALUES (?,?,?)',[(report_id,name,data) for name,data in files.items()])
    return {'report_id':report_id,'manifest_sha256':receipt,'result':result}

def verify(manifest_bytes,files,expected_manifest_sha256):
    if not isinstance(expected_manifest_sha256,str) or len(expected_manifest_sha256)!=64 or sha(manifest_bytes)!=expected_manifest_sha256:raise EvidenceError('MANIFEST_HASH_MISMATCH')
    manifest=json.loads(manifest_bytes)
    if manifest.get('schema_version')!='execution-receipt/1' or set(manifest.get('files',{}))!=FILES:raise EvidenceError('MANIFEST_SCHEMA_MISMATCH')
    if set(files)!=FILES:raise EvidenceError('MISSING_EVIDENCE' if FILES-set(files) else 'UNLISTED_EVIDENCE')
    for name,expected in manifest['files'].items():
        if sha(files[name])!=expected:raise EvidenceError('EVIDENCE_HASH_MISMATCH:'+name)
    plan=json.loads(files['contract.json']);rows=json.loads(files['observations.json']);params=json.loads(files['parameters.json']);stored=json.loads(files['result.json']);runtime=json.loads(files['runtime.json'])
    if sha(encoded({k:v for k,v in plan.items() if k!='contract_hash'}))!=plan.get('contract_hash'):raise EvidenceError('CONTRACT_HASH_MISMATCH')
    for k in ['card_id','card_version']:
        if manifest[k]!=plan[k]:raise EvidenceError('CARD_IDENTITY_MISMATCH')
    for k in ['scope_id','period_start','period_end']:
        if manifest[k]!=params[k]:raise EvidenceError('REPORT_POPULATION_MISMATCH')
    if runtime['interpreter_sha256']!=interpreter_hash() or runtime['profile_version']!=model.VERSION:raise EvidenceError('INTERPRETER_VERSION_MISMATCH: restore the recorded source version before replay')
    recomputed=model.compute(plan,rows,params)
    if encoded(recomputed)!=encoded(stored):raise EvidenceError('CALCULATION_MISMATCH')
    return {'ok':True,'result':recomputed,'card_id':plan['card_id'],'card_version':plan['card_version'],
            'manifest_sha256':expected_manifest_sha256,'runtime_at_capture':runtime,
            'assurance':'replayed_calculation_and_unchanged_evidence; source authenticity and approval require separate evidence'}

def replay(con,report_id,expected_manifest_sha256):
    row=con.execute('SELECT manifest_json FROM execution_report WHERE report_id=?',(report_id,)).fetchone()
    if row is None:raise LookupError('Unknown report ID')
    files={name:bytes(content) for name,content in con.execute('SELECT name,content FROM execution_file WHERE report_id=?',(report_id,))}
    return verify(row[0].encode('utf-8'),files,expected_manifest_sha256)

def find_reports(con,card_id,card_version,scope_id,period_end):
    return con.execute('SELECT report_id,manifest_sha256 FROM execution_report WHERE card_id=? AND card_version=? AND scope_id=? AND period_end=? ORDER BY report_id',(card_id,card_version,scope_id,period_end)).fetchall()

def export_report(con,report_id,expected_manifest_sha256,folder):
    replay(con,report_id,expected_manifest_sha256)
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    if any(folder.iterdir()):raise ValueError('Export directory must be empty')
    for name,content in con.execute('SELECT name,content FROM execution_file WHERE report_id=?',(report_id,)):(folder/name).write_bytes(content)
    (folder/'manifest.json').write_text(con.execute('SELECT manifest_json FROM execution_report WHERE report_id=?',(report_id,)).fetchone()[0],encoding='utf-8')

def restore(folder,expected_manifest_sha256):
    folder=Path(folder)
    if {p.name for p in folder.iterdir()}!=FILES|{'manifest.json'}:raise EvidenceError('MISSING_OR_UNLISTED_EVIDENCE')
    return verify((folder/'manifest.json').read_bytes(),{name:(folder/name).read_bytes() for name in FILES},expected_manifest_sha256)
