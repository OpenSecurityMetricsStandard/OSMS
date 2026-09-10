# SPDX-License-Identifier: MIT
"""Runnable DAX query wrappers for explicitly declared disconnected selectors."""
import re


def query(measure_text, table, outputs):
    """Convert maintained measure definitions into one DEFINE/EVALUATE query.

    outputs maps exported output names to measure names. Query literals are an
    example selection, not model constants. A UTC typed input table and selector
    tables Scope / ReportingPeriod must exist in the model.
    """
    definitions=re.sub(r'(?m)^([^/\n][^\n]*?)\s*:=\s*$',lambda m:'MEASURE '+table+'['+m.group(1).strip()+'] =',measure_text)
    if ':=' in definitions:raise ValueError('Unconverted DAX measure declaration')
    fields=',\n    '.join('"'+output+'", ['+measure+']' for output,measure in outputs.items())
    return 'DEFINE\n'+definitions+'\nEVALUATE\nCALCULATETABLE(\n  ROW(\n    '+fields+'''\n  ),
  TREATAS({"prod"},Scope[scope_id]),
  TREATAS({DATE(2026,6,1)},ReportingPeriod[period_start]),
  TREATAS({DATE(2026,7,1)},ReportingPeriod[period_end])
)'''


def soc002():
    params='''VAR ps=SELECTEDVALUE(ReportingPeriod[period_start])
VAR pe=SELECTEDVALUE(ReportingPeriod[period_end])
VAR sc=SELECTEDVALUE(Scope[scope_id])
VAR cases=FILTER(ALL(Incidents),Incidents[scope_id]=sc && NOT ISBLANK(Incidents[detected_at]) && Incidents[detected_at]>=ps && Incidents[detected_at]<pe && NOT ISBLANK(Incidents[confirmed_at]) && Incidents[confirmed_at]<=pe && Incidents[confirmed_at]>=Incidents[detected_at] && NOT ISBLANK(Incidents[occurred_at]) && Incidents[detected_at]>=Incidents[occurred_at])
VAR durations=ADDCOLUMNS(cases,"@h",(Incidents[detected_at]-Incidents[occurred_at])*24.0,"@w",SWITCH(Incidents[severity],"P1",4.0,"P2",2.0,1.0))
VAR n=COUNTROWS(cases)+0
VAR badParameters=ISBLANK(ps) || ISBLANK(pe) || ps>=pe || ISBLANK(sc)'''
    expressions={'valid_cases':'n','p50_h':'MEDIANX(durations,[@h])',
                 'p90_h':'MAXX(TOPN(ROUNDUP(0.9*n,0),durations,[@h],ASC),[@h])',
                 'mean_h_supplementary':'AVERAGEX(durations,[@h])',
                 'severity_weighted_avg':'DIVIDE(SUMX(durations,[@w]*[@h]),SUMX(durations,[@w]))'}
    text='// SOC-002: UTC incident data; detected cohort, confirmed by period end. Exact P50/P90.\n'
    for key,expression in expressions.items():
        guard='badParameters' if key=='valid_cases' else 'badParameters || n=0'
        text+=f'\nSOC002 {key} :=\n{params}\nRETURN IF({guard},BLANK(),{expression})\n'
    return query(text,'Incidents',{k:'SOC002 '+k for k in expressions})
