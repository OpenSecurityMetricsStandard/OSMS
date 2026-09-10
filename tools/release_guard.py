#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prevent an unfinished working draft from being released under a final tag.

This guard does not attest board approval. Stable promotion still requires an
adopted approval/evidence mechanism; see review/METHOD_DECISIONS.md.
"""
import argparse
from pathlib import Path
import yaml


def validate(tag,catalog):
    version=str(catalog['version'])
    if tag != 'v'+version and not tag.startswith('v'+version+'-'):
        raise ValueError('Tag and catalog version differ')
    phase=catalog.get('release_phase')
    if phase=='working_draft' and not tag.startswith('v'+version+'-'):
        raise ValueError('A working draft requires an explicit prerelease tag')
    if tag.startswith('v1.') and '-' not in tag:
        raise ValueError('Stable 1.x promotion requires the adopted board approval/evidence gate; not implemented in this draft')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('tag');args=parser.parse_args()
    try:validate(args.tag,yaml.safe_load(Path('catalog/osms-catalog.yaml').read_text()))
    except ValueError as exc:parser.exit(1,f'Release blocked: {exc}\n')
