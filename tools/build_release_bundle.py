#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build a deterministic snapshot archive and checksum every included source file.

Uses tracked paths, reads the working tree, never creates a tag or release.
Stage newly added files first. An archive is not a board approval.
"""
import argparse
import hashlib
import os
import re
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def build(tag, out):
    if not re.fullmatch(r'v[0-9][A-Za-z0-9.+-]*',tag):
        raise ValueError('Tag must be a filename-safe version such as v0.9.2')
    root=Path(__file__).resolve().parents[1]
    files=subprocess.check_output(['git','ls-files','-z'],cwd=root).decode().split('\0')
    payload={p:(root/p).read_bytes() for p in sorted(files) if p and (root/p).is_file()}
    manifest=''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in payload.items())
    epoch=int(os.environ.get('SOURCE_DATE_EPOCH') or subprocess.check_output(['git','show','-s','--format=%ct','HEAD'],cwd=root))
    timestamp=datetime.fromtimestamp(max(epoch,315532800),timezone.utc).timetuple()[:6]
    out.mkdir(parents=True,exist_ok=True)
    archive=out/f'osms-{tag}-catalog.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as target:
        for name,data in {**payload,'MANIFEST-SHA256.txt':manifest.encode()}.items():
            info=zipfile.ZipInfo(name,timestamp);info.compress_type=zipfile.ZIP_DEFLATED
            mode = 0o100755 if name in payload and (root/name).stat().st_mode & 0o111 else 0o100644
            info.external_attr=(mode<<16)
            target.writestr(info,data)
    (out/'MANIFEST-SHA256.txt').write_text(manifest)
    (out/'SHA256SUMS.txt').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
    print(f'{archive}: {len(payload)} source files, complete per-file manifest')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tag');parser.add_argument('--out',type=Path,default=Path('release'))
    args=parser.parse_args();build(args.tag,args.out)
