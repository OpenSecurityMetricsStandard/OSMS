#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate version identity and distinguish maintainer drafts from 1.x approval.

This guard does not attest board approval. Stable promotion still requires an
adopted approval/evidence mechanism; see review/METHOD_DECISIONS.md.
"""
import argparse
import re
from pathlib import Path
import yaml


def validate(tag,catalog):
    version=str(catalog['version'])
    if not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', version):
        raise ValueError('Catalog version must be a three-part numeric version')
    if not re.fullmatch(r'v'+re.escape(version)+r'(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?', tag):
        raise ValueError('Tag must identify this catalog version, with an optional prerelease suffix')
    phase=catalog.get('release_phase')
    if phase not in ('working_draft', 'review_candidate'):
        raise ValueError('This release path requires an explicit draft or candidate phase')
    # The maintainer may publish plain v0.x.y tags before the board exists.
    # The release workflow displays these as public prereleases, not board approval.
    if not version.startswith('0.') and '-' not in tag:
        raise ValueError('Stable 1.0+ promotion requires the adopted board approval/evidence gate; not implemented in this draft')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('tag');args=parser.parse_args()
    try:validate(args.tag,yaml.safe_load(Path('catalog/osms-catalog.yaml').read_text()))
    except ValueError as exc:parser.exit(1,f'Release blocked: {exc}\n')
