# /// script
# requires-python = ">=3.10"
# dependencies = ["paramiko", "pillow", "markdown"]
# ///
"""Publish the site (site/build.py) to the web server, and keep it current while painters work.

    uv run site/publish.py                 # build once and upload what changed
    uv run site/publish.py --every 60      # rebuild and upload every 60 s (live paintings appear as they go)

The server and its login come from SITE_ENV (default ~/.config/seestar/willygarage.env: WG_HOST,
WG_USER, WG_PASSWORD); the site goes to SITE_DIR on it (default /var/www/claude-art, served by
site/deploy/nginx-claude-art.thomlex.conf). Uploads only files whose contents changed since the last
upload (a manifest of hashes next to the local build) and removes the ones the build no longer has.
The studio's full-size PNGs (studio/data/*/img/) aren't uploaded: the page shows its JPEG views.
"""
import argparse
import hashlib
import json
import os
import posixpath
import sys
import time
from pathlib import Path

import paramiko

HERE = Path(__file__).resolve().parent
STUDIOS = Path(os.environ.get("PAINT_STUDIOS", "~/paint-studios")).expanduser()
OUT = STUDIOS / ".claude-art-site"
ENV = Path(os.environ.get("SITE_ENV", "~/.config/seestar/willygarage.env")).expanduser()
REMOTE = os.environ.get("SITE_DIR", "/var/www/claude-art")
MANIFEST = STUDIOS / f".claude-art-site.{REMOTE.strip('/').replace('/', '_')}.manifest.json"   # one per destination


def skip(rel):
    parts = rel.split("/")
    return (len(parts) >= 5 and parts[0] == "studio" and parts[3] == "img") or parts[-1] == ".studio-export"


def connect():
    cfg = {k.strip(): v.strip() for k, v in (l.split("=", 1) for l in ENV.read_text().splitlines() if "=" in l and not l.startswith("#"))}
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(cfg["WG_HOST"], username=cfg["WG_USER"], password=cfg["WG_PASSWORD"], timeout=30, look_for_keys=False, allow_agent=False)
    return c


def scan(cache):
    """{rel: [size, mtime_ns, sha1]} of the build, reusing a cached hash when size and mtime match."""
    out = {}
    for p in sorted(OUT.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(OUT).as_posix()
        if skip(rel):
            continue
        st = p.stat()
        old = cache.get(rel)
        if old and old[0] == st.st_size and old[1] == st.st_mtime_ns:
            out[rel] = old
        else:
            out[rel] = [st.st_size, st.st_mtime_ns, hashlib.sha1(p.read_bytes()).hexdigest()]
    return out


def publish():
    sent = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    now = scan(sent)
    up = [r for r, v in now.items() if r not in sent or sent[r][2] != v[2]]
    gone = [r for r in sent if r not in now]
    if not up and not gone:
        return 0, 0
    # index.html last, so a page never links to something not yet there
    up.sort(key=lambda r: (r.endswith("index.html"), r))
    c = connect()
    sftp = c.open_sftp()
    made = set()
    for rel in up:
        d = posixpath.dirname(posixpath.join(REMOTE, rel))
        if d not in made:
            c.exec_command(f"mkdir -p '{d}'")[1].channel.recv_exit_status()
            made.add(d)
        tmp = posixpath.join(REMOTE, rel) + ".part"
        sftp.put(str(OUT / rel), tmp)
        sftp.posix_rename(tmp, posixpath.join(REMOTE, rel))
        sent[rel] = now[rel]
    for rel in gone:
        try:
            sftp.remove(posixpath.join(REMOTE, rel))
        except OSError:
            pass
        sent.pop(rel, None)
    sftp.close()
    c.close()
    for rel, v in now.items():   # files whose mtime changed but not their contents
        sent[rel] = v
    MANIFEST.write_text(json.dumps(sent))
    return len(up), len(gone)


def build():
    import subprocess
    r = subprocess.run(["uv", "run", "--quiet", str(HERE / "build.py"), "--out", str(OUT)], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"build failed: {r.stderr[-800:]}")
    return r.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=int, default=0, help="seconds between rebuild-and-upload passes (0: once)")
    a = ap.parse_args()
    while True:
        try:
            said = build()
            n_up, n_gone = publish()
            print(f"{time.strftime('%F %T')} {said}; uploaded {n_up}, removed {n_gone}", flush=True)
        except Exception as e:   # a failed pass (the network, a build) is retried next time
            print(f"{time.strftime('%F %T')} publish failed: {e}", file=sys.stderr, flush=True)
            if not a.every:
                sys.exit(1)
        if not a.every:
            break
        time.sleep(a.every)


if __name__ == "__main__":
    main()
