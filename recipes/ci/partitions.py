# SPDX-License-Identifier: MIT
"""Deterministic disjoint card partitions; no case subset is removed."""
def partition(ids,spec):
    i,n=map(int,spec.split('/'))
    if not 0<=i<n<=len(ids) or len(ids)!=len(set(ids)):
        raise ValueError('Nonempty disjoint card partition I/N required')
    return sorted(ids)[i::n]
