# SPDX-License-Identifier: MIT
"""Publish explicit implementation stages and executable independent examples."""
from .registry import register
from . import render,excel,platforms,spl,esql,cases
import xlsx_dialect

PROFILE='prepared_observations_v1'

def generate(cards):
    plans=register(cards);examples=cases.examples(plans);result={}
    for cid,p in plans.items():
        spec=excel.spec(p)
        result[cid]={
            'contract':{**p,'outputs':p['output_contracts'],'verification':{d:'not_run' for d in ['py','gsql','pg','kql','spl','esql','xlsx','dax']}},
            'plan':p,'dialects':{'py':render.python_code(p),'gsql':render.sql(p,'gsql'),'pg':render.sql(p,'pg'),
                'kql':platforms.kql(p),'spl':spl.query(p),'xlsx':xlsx_dialect.render(cid,spec),'dax':platforms.dax(p)},
            'excel_spec':spec,'esql_protocol':esql.protocol(p),'fixtures':examples[cid]}
    return result
