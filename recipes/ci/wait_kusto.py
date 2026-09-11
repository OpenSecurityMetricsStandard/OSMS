# SPDX-License-Identifier: MIT
"""Bounded CI startup probe; a timeout is a failure, not a successful skip."""
import time
from kusto_runner import request

deadline=time.monotonic()+240
while True:
    try:
        request('http://localhost:8080','.show version',management=True)
        print('Kusto query engine ready');break
    except Exception:
        if time.monotonic()>=deadline:raise
        time.sleep(2)
