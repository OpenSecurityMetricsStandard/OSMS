# SPDX-License-Identifier: MIT
"""Execute generated expressions on the actual installed DuckDB engine."""
import json
from decimal import Decimal
import duckdb
from . import model,render

def duckdb_compute(plan,rows,params,dialect='gsql'):
    with duckdb.connect() as con:
        schema=render.typed_schema(plan,dialect)
        con.execute('CREATE TABLE osms_input ('+','.join(k+' '+v for k,v in schema.items())+')')
        if rows:
            values=[]
            for row in rows:
                values.append([model.instant(row.get(k)) if plan['inputs'][k]['type']=='timestamp' else row.get(k) for k in schema])
            con.executemany('INSERT INTO osms_input VALUES ('+','.join('?' for _ in schema)+')',values)
        query=render.sql(plan,dialect)
        for name in params:query=query.replace(':'+name,'$'+name)
        cursor=con.execute(query,params)
        result=dict(zip((d[0] for d in cursor.description),cursor.fetchone()))
        result={k:float(v) if isinstance(v,Decimal) else v for k,v in result.items()}
        if isinstance(result.get('services'),str):result['services']=json.loads(result['services'])
        return {'evaluation_status':result.pop('evaluation_status'),'selected_records':result.pop('selected_records'),
                'invalid_records':result.pop('invalid_records'),'outputs':result}
