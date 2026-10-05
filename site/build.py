# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow", "markdown"]
# ///
"""Build the public site: the gallery of finished paintings, a page per painting, the artists' paint
and method research, how it works, and the studio viewer (live and replays).

    uv run site/build.py [--out DIR]        # default ~/paint-studios/.claude-art-site

Reads the Claude Code painters' studios and run folders (harness/claude-code/paint.py:
PAINT_STUDIOS, default ~/paint-studios), the research notes (notes/research/<artist>_materials.md),
the boxes (crates/paint/src/palette.rs) and the studio export (studio/export_static.py, into
<out>/studio). Every page credits claude-paint's author and links to https://stillwet.art.

Only finished paintings get a page; one still painting shows as "painting now". Nothing that names
this machine's owner is written: the pages are checked for the home folder and the account name.
"""
import argparse
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import markdown
from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
STUDIOS = Path(os.environ.get("PAINT_STUDIOS", "~/paint-studios")).expanduser()
HOME, USER = str(Path.home()), Path.home().name
HOW = HERE / "how.html"
# paintings kept out of the gallery until chosen (studio names, one a line; # comments): they still show in the studio
HIDDEN = STUDIOS / "site-hidden.txt"
# paintings taken off the site altogether (the gallery and the studio): same format
REMOVED = STUDIOS / "site-removed.txt"


def listed(f):
    return {l.split("#")[0].strip() for l in f.read_text().splitlines()} - {""} if f.exists() else set()   # the how-it-works body (an example from stillwet.art, credited there)

# profile -> (name, the name it goes by, materials note, years and medium)
ARTISTS = {
    "leonardo": ("Leonardo da Vinci", "Leonardo", "leonardo", "1452–1519 · oil on wood panel"),
    "rembrandt": ("Rembrandt van Rijn", "Rembrandt", "rembrandt", "1606–1669 · oil on panel and canvas"),
    "friedrich": ("Caspar David Friedrich", "Friedrich", "friedrich", "1774–1840 · oil on canvas"),
    "monet": ("Claude Monet", "Monet", "monet", "1840–1926 · oil on canvas, out of doors"),
    "van-gogh": ("Vincent van Gogh", "Van Gogh", "van_gogh", "1853–1890 · thick oil on canvas"),
    "munch": ("Edvard Munch", "Munch", "munch", "1863–1944 · thin oil on canvas and board"),
    "picasso": ("Pablo Picasso", "Picasso", "picasso", "1881–1973 · oil (and house paint) on canvas"),
    "miro": ("Joan Miró", "Miró", "miro", "1893–1983 · oil on canvas"),
    "dali": ("Salvador Dalí", "Dalí", "dali", "1904–1989 · smooth oil on canvas and panel"),
    "kahlo": ("Frida Kahlo", "Kahlo", "kahlo", "1907–1954 · oil on masonite, metal and canvas"),
}
# the gallery's order (the owner's choice): the strongest first, Friedrich and Rembrandt last
GALLERY_ORDER = ["leonardo", "monet", "van-gogh", "munch", "picasso", "miro", "dali", "kahlo", "friedrich", "rembrandt"]
MODELS = {"claude-opus-5-5": "Claude Opus 5.5", "claude-sonnet-5-5": "Claude Sonnet 5.5", "claude-sonnet-5": "Claude Sonnet 5",
          "claude-haiku-4-5-20251001": "Claude Haiku 4.5", "claude-fable-5-1": "Claude Fable 5.1"}


def model_of(run, meta):
    """The model the painter ran on, by name: from its first sitting's stream (meta.json has only the alias)."""
    for f in sorted(run.glob("*_s*.jsonl")):
        for line in f.open(errors="replace"):
            try:
                m = json.loads(line)
            except ValueError:
                continue
            if m.get("type") == "system" and m.get("model"):
                return MODELS.get(m["model"], m["model"])
    return meta.get("model", "")
CREDIT = ('Made with <a href="https://stillwet.art">claude-paint</a>, the open-source oil-paint simulator and '
          'AI painters\' studio by Alice (<a href="https://stillwet.art">stillwet.art</a>). '
          'Code MIT; paintings and logs CC BY 4.0.')

CSS = """
:root{--bg:#fbfaf7;--ink:#1d1d1b;--mute:#66645e;--rule:#e4e1d8;--card:#fff;--accent:#8a5d0e}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
a{color:var(--accent)}
.top{border-bottom:1px solid var(--rule);background:var(--bg)}
.top .in{max-width:1100px;margin:0 auto;padding:12px 16px;display:flex;flex-wrap:wrap;gap:6px 18px;align-items:baseline}
.brand{font:600 21px Georgia,"Times New Roman",serif;color:var(--ink);text-decoration:none;margin-right:auto}
.top nav a{color:var(--ink);text-decoration:none;font-size:15px} .top nav a:hover{color:var(--accent)} .top nav{display:flex;gap:16px;flex-wrap:wrap}
main{max-width:1100px;margin:0 auto;padding:24px 16px 48px}
h1,h2,h3{font-family:Georgia,"Times New Roman",serif;font-weight:500} h1{font-size:32px;line-height:1.2;margin:4px 0 8px} h2{font-size:24px;margin:28px 0 8px}
.lede{font-size:18px;color:#3b3a36;max-width:760px;margin:0 0 16px}
.credit{background:var(--card);border:1px solid var(--rule);border-left:4px solid var(--accent);border-radius:6px;padding:12px 16px;margin:16px 0 24px;max-width:760px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:22px}
.card{background:var(--card);border:1px solid var(--rule);border-radius:8px;overflow:hidden;text-decoration:none;color:var(--ink);display:block}
.card img{width:100%;aspect-ratio:4/3;object-fit:cover;display:block;background:#eee}
.card .cap{padding:10px 14px 14px} .card .t{font:500 18px Georgia,serif;margin:0} .card .by{color:var(--mute);font-size:14px}
.live{background:#fff4f2;border:1px solid #f2c9c2;border-radius:6px;padding:10px 16px;margin:0 0 22px}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:#d23b2a;margin-right:8px}
.meta{color:var(--mute);font-size:15px;margin:0 0 14px}
.hero{width:100%;height:auto;display:block;border:1px solid var(--rule);border-radius:4px;background:#eee}
blockquote{margin:10px 0 16px;padding:4px 0 4px 16px;border-left:3px solid var(--accent);color:#3b3a36}
details{margin:14px 0} summary{cursor:pointer;color:var(--accent);font-weight:600}
.note{font-size:15px;overflow-x:auto} .note table{border-collapse:collapse;font-size:13px;margin:8px 0} .note td,.note th{border:1px solid var(--rule);padding:4px 6px;vertical-align:top}
.box{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:8px 14px;margin:12px 0}
.sw{display:flex;align-items:center;gap:8px;font-size:14px} .chip{width:26px;height:26px;border-radius:5px;border:1px solid rgba(0,0,0,.15);flex:none}
.new{font-size:11px;color:#fff;background:var(--accent);border-radius:3px;padding:0 4px;margin-left:4px;font-weight:600}
.alist{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px}
.acard{background:var(--card);border:1px solid var(--rule);border-radius:8px;padding:14px;text-decoration:none;color:var(--ink)}
.acard .n{font:500 19px Georgia,serif} .acard .e{color:var(--mute);font-size:14px} .strip{display:flex;gap:4px;margin-top:10px} .strip span{flex:1;height:14px;border-radius:2px}
footer{border-top:1px solid var(--rule);color:var(--mute);font-size:14px}
footer .in{max-width:1100px;margin:0 auto;padding:16px}
pre{background:#f2efe7;border:1px solid var(--rule);border-radius:6px;padding:12px;overflow-x:auto;font-size:13px}
@media (max-width:560px){h1{font-size:26px}.grid{grid-template-columns:1fr}.box{grid-template-columns:1fr 1fr}}
"""


def page(title, body, depth=0, desc=""):
    up = "../" * depth
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>{f'<meta name="description" content="{html.escape(desc)}">' if desc else ''}
<link rel="stylesheet" href="{up}style.css"></head><body>
<div class="top"><div class="in"><a class="brand" href="{up}index.html">Claude Art</a>
<nav><a href="{up}index.html">Gallery</a><a href="{up}studio/">Studio</a><a href="{up}artists/index.html">Artists</a><a href="{up}how.html">How it works</a></nav></div></div>
<main>{body}</main>
<footer><div class="in">{CREDIT}</div></footer></body></html>"""


# ---- data ----------------------------------------------------------------------------------------

def boxes():
    pal = (REPO / "crates/paint/src/palette.rs").read_text(encoding="utf-8")
    colors = {m[1]: m[2] for m in re.finditer(r'tube\("((?:[^"\\]|\\.)*)", "[^"]*", "(#[0-9a-f]{6})"', pal)}
    named = {m[1]: re.findall(r'"((?:[^"\\]|\\.)*)"', m[2])
             for m in re.finditer(r'\(\s*"([a-z-]+)",\s*&\[(.*?)\],\s*\)', pal, re.S)}
    named["friedrich"] = re.findall(r'"((?:[^"\\]|\\.)*)"', re.search(r"const TUBE_BOX: &\[&str\] = &\[(.*?)\];", pal, re.S)[1])
    return named, colors


def r22_new_tubes():
    """The tubes round 22 added (notes/r22/TUBES.md's table), for the "new" tag."""
    t = (REPO / "notes/r22/TUBES.md").read_text(encoding="utf-8")
    return set(re.findall(r"^\| ([a-zA-Z' ]+) \| [^|]+ \| `#", t, re.M))


def title_and_text(reply):
    """The title (the reply's first bold line: "**Title: *X* (Y)**", "**X**") and the description after it."""
    lines = reply.strip().splitlines()
    # the first bold span, also inside a sentence ('I called it **"Old Man Reading."**'): "**X** (a translation)" keeps X
    at = next((i for i, l in enumerate(lines) if re.search(r"\*\*.+?\*\*", l)), None)
    if at is None:
        return "Untitled", []
    bold = re.search(r"\*\*(.+?)\*\*", lines[at])[1].strip().strip('"“”').rstrip(".").strip('"“”')
    title = re.sub(r"^Title:\s*", "", re.sub(r"[*_]", "", bold)).strip()
    body = "\n".join(lines[at + 1:])
    paras = [p.strip() for p in body.split("\n\n") if p.strip() and not p.strip().startswith(("In this session", "- ", "I looked", "I came back", "I left", "I'm leaving", "I've stopped", "I stopped", "I'm calling", "I didn't"))]
    return title, [re.sub(r"[*_]{1,2}", "", p) for p in paras[:2]]


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (OSError, TypeError):
        return False


def final_image(studio):
    """The finished canvas: live.png, else the painter's last look at the whole canvas (the widest recent one)."""
    live = studio / "out/easel/painting/live.png"
    if live.exists():
        return live
    log = studio / "paintings/lua/painting.lua"
    m = re.search(r"aspect\s*=\s*([\d.]+)", log.read_text()) if log.exists() else None
    if not m:
        return None
    aspect = float(m[1])
    looks = sorted((studio / "out/easel/painting").glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)[:60]
    for p in looks:   # a whole look has the canvas's shape; a crop (at most 500 units a side) rarely does
        w, h = Image.open(p).size
        if w >= 600 and abs(w / h - aspect) < 0.01:
            return p
    return None


def paintings():
    """(done, live): the Claude Code painters' paintings, finished and still painting."""
    done, live = [], []
    hidden = listed(HIDDEN) | listed(REMOVED)
    for meta_f in sorted(STUDIOS.glob("runs/paint-studio-*/meta.json")):
        if meta_f.parent.name in hidden:
            continue
        run = meta_f.parent
        meta = json.loads(meta_f.read_text())
        studio = Path(meta["studio"])
        prof = meta.get("profile")
        if prof not in ARTISTS:
            continue
        sittings = json.loads((run / "sittings.json").read_text()) if (run / "sittings.json").exists() else []
        running = [s for s in sittings if s["status"] == "running" and alive(s.get("pid"))]
        if running:
            live.append({"profile": prof, "studio": studio.name})
            continue
        # finished: the easel writes the canvas (live.png) when it closes; a painter stopped at the hard cap
        # may leave none, and then its last whole look stands in
        image = final_image(studio)
        if not (run / "reply.md").exists() or not image:
            continue
        title, text = title_and_text((run / "reply.md").read_text())
        opening = re.search(r"^# Paint a picture\s*\n\s*\n(.*?)\n\s*\n", (studio / "BRIEF.md").read_text(), re.S | re.M)
        done.append({"profile": prof, "studio": studio.name, "title": title, "text": text,
                     "model": model_of(run, meta), "effort": meta.get("effort", ""),
                     "minutes": round(sum(s.get("minutes") or 0 for s in sittings)),
                     "blocks": max([s.get("chunks_after") or 0 for s in sittings] or [0]),
                     "sittings": len({s["sitting"] for s in sittings}),
                     "brief": re.sub(r"\s+", " ", opening[1]).strip() if opening else "",
                     "journal": (studio / "notes/journal.md").read_text() if (studio / "notes/journal.md").exists() else "",
                     "image": image,
                     "slug": f"{prof}-{studio.name.split('-')[-1]}",
                     "created": meta.get("created", "")})
    order = list(GALLERY_ORDER)
    done.sort(key=lambda p: (order.index(p["profile"]) if p["profile"] in order else len(order), p["created"]))
    return done, live


# ---- writing -------------------------------------------------------------------------------------

def jpg(src, dest, side, q):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
        return
    im = Image.open(src).convert("RGB")
    im.thumbnail((side, side))
    im.save(dest, "JPEG", quality=q, optimize=True)


def summary(slug):
    t = (REPO / f"notes/research/{slug}_materials.md").read_text(encoding="utf-8")
    m = re.search(r"^## Summary\s*\n(.*?)(?=^\*\*Terms|^## )", t, re.S | re.M)
    s = re.sub(r"\s+", " ", re.sub(r"\s*\[[^\]]*\]", "", m[1] if m else "")).strip()
    out = ""
    for x in re.split(r"(?<=[.!?])\s+(?=[A-Z])", s):
        if len(out) + len(x) > 600:
            break
        out += (" " if out else "") + x
    return out


def note_html(slug):
    t = (REPO / f"notes/research/{slug}_materials.md").read_text(encoding="utf-8")
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    t = re.sub(r"^# .*\n", "", t, count=1)
    return markdown.markdown(t, extensions=["tables"])


def swatches(tubes, colors, new):
    return "".join(f'<div class="sw"><span class="chip" style="background:{colors.get(t, "#ccc")}"></span>'
                   f'<span>{html.escape(t)}{" <b class=new>new</b>" if t in new else ""}</span></div>' for t in tubes)


def build(out):
    named, colors = boxes()
    new = r22_new_tubes()
    done, live = paintings()
    if out.exists():
        for p in out.iterdir():
            if p.name != "studio":
                shutil.rmtree(p) if p.is_dir() else p.unlink()
    out.mkdir(parents=True, exist_ok=True)
    (out / "style.css").write_text(CSS)
    imgcache = STUDIOS / ".claude-art-img"

    # images (cached by source time), copied into the site
    for p in done:
        for name, side, q in (("t", 700, 82), ("v", 1600, 86), ("f", 2400, 90)):
            c = imgcache / f"{p['slug']}-{name}.jpg"
            jpg(p["image"], c, side, q)
            (out / "img").mkdir(exist_ok=True)
            shutil.copy(c, out / "img" / c.name)

    by = {a: [p for p in done if p["profile"] == a] for a in ARTISTS}
    livehtml = "".join(f'<div class="live"><span class="dot"></span><b>Painting now:</b> a picture in the manner of '
                       f'{ARTISTS[l["profile"]][0]}. <a href="studio/?p={l["studio"]}">Watch it live &rarr;</a></div>' for l in live)
    cards = "".join(f'''<a class="card" href="p/{p['slug']}.html"><img src="img/{p['slug']}-t.jpg" alt="{html.escape(p['title'])}" loading="lazy">
<div class="cap"><p class="t">{html.escape(p['title'])}</p><div class="by">After {ARTISTS[p['profile']][0]}</div></div></a>''' for p in done)
    home = f"""<h1>Paintings by Claude, in the manner of the masters</h1>
<p class="lede">Claude paints with code. Every brushstroke is a line of a program, and a simulation of bristles, wet oil paint and linen carries it out. There's no image generator, and the painter never sees a picture of the artist's work: it works from written research on how the artist painted, and only with the pigments that artist is documented using.</p>
<div class="credit"><b>Built on claude-paint, by Alice.</b> The oil-paint simulator, the easel and the studio these paintings were made in are the work of the artist and developer who publishes as Alice. Their own gallery of AI paintings, and the experiments behind it, are at <a href="https://stillwet.art"><b>stillwet.art</b></a>. This site adds new artists' studios and runs the painters through Claude Code.</div>
{livehtml}
<h2>Gallery</h2>
<div class="grid">{cards}</div>
<h2>More</h2>
<p><a href="studio/">The studio</a>: watch each painting being made, with the painter's thinking. <a href="artists/index.html">The artists</a>: how each one really worked, and the paints in their box. <a href="how.html">How it works</a>: what the painter is given and how it paints.</p>"""
    (out / "index.html").write_text(page("Claude Art", home, 0, "AI paintings made with code, in the manner of the masters"))

    (out / "p").mkdir(exist_ok=True)
    for p in done:
        a = ARTISTS[p["profile"]]
        others = [q for q in by[p["profile"]] if q is not p]
        body = f"""<p class="meta"><a href="../index.html">&larr; Gallery</a></p>
<a href="../img/{p['slug']}-f.jpg"><img class="hero" src="../img/{p['slug']}-v.jpg" alt="{html.escape(p['title'])}"></a>
<h1>{html.escape(p['title'])}</h1>
<p class="meta">After <a href="../artists/{p['profile']}.html">{a[0]}</a> · {html.escape(p['model'] or '')}{f", {p['effort']} effort" if p['effort'] else ''} · {p['blocks']} blocks of code · {p['minutes']} minutes · {p['sittings']} sitting{'s' if p['sittings'] != 1 else ''} · <a href="../img/{p['slug']}-f.jpg">full size</a></p>
{''.join(f'<p>{html.escape(t)}</p>' for t in p['text'])}
<p class="meta">The painter's own words, from its reply when it finished.</p>
<p><a href="../studio/?p={p['studio']}"><b>Watch it being painted, with its thinking &rarr;</b></a></p>
<details><summary>What the painter was asked</summary><blockquote>{html.escape(p['brief'])}</blockquote><p class="meta">It also had the easel's guide, notes on how the easel behaves, and the <a href="../artists/{p['profile']}.html">research on {a[1]}'s materials and method</a>.</p></details>
{f'<details><summary>The painter\'s journal</summary><div class="note">{markdown.markdown(p["journal"])}</div></details>' if p['journal'].strip() else ''}
{''.join(f'<p>Also after {a[1]}: <a href="{q["slug"]}.html">{html.escape(q["title"])}</a></p>' for q in others)}"""
        (out / "p" / f"{p['slug']}.html").write_text(page(f"{p['title']} · Claude Art", body, 1, f"After {a[0]}"))

    (out / "artists").mkdir(exist_ok=True)
    acards = ""
    for prof, (name, short, slug, era) in ARTISTS.items():
        tubes = named.get(prof, [])
        if not tubes or not (REPO / f"notes/research/{slug}_materials.md").exists():
            continue
        strip = "".join(f'<span style="background:{colors.get(t, "#ccc")}"></span>' for t in tubes)
        acards += f'<a class="acard" href="{prof}.html"><div class="n">{name}</div><div class="e">{era}</div><div class="e">{len(tubes)} paints · {len(by[prof])} painting{"s" if len(by[prof]) != 1 else ""}</div><div class="strip">{strip}</div></a>'
        works = "".join(f'''<a class="card" href="../p/{p['slug']}.html"><img src="../img/{p['slug']}-t.jpg" alt="{html.escape(p['title'])}" loading="lazy"><div class="cap"><p class="t">{html.escape(p['title'])}</p></div></a>''' for p in by[prof])
        nnew = sum(1 for t in tubes if t in new)
        body = f"""<p class="meta"><a href="index.html">&larr; Artists</a></p>
<h1>{name}</h1><p class="meta">{era} · {len(tubes)} paints in the box{f' · {nnew} added to the simulator for this studio' if nnew else ''}</p>
<p class="lede">{html.escape(summary(slug))}</p>
<h2>The paint box</h2><p class="meta">Only pigments {short} is documented using, shown as each paint looks laid thick. The colours are estimates from the research, not measurements.</p>
<div class="box">{swatches(tubes, colors, new)}</div>
{f'<h2>Painted here</h2><div class="grid">{works}</div>' if works else ''}
<h2>Materials and method</h2><p class="meta">The research the painter reads before it starts (the painter's copy has the source keys stripped).</p>
<div class="note">{note_html(slug)}</div>"""
        (out / "artists" / f"{prof}.html").write_text(page(f"{name} · Claude Art", body, 1, f"How {name} painted, and the paints in the box"))
    (out / "artists" / "index.html").write_text(page("Artists · Claude Art", f"""<h1>The artists</h1>
<p class="lede">Each painter works in a studio made for one artist: a research note on how that artist really painted (supports, grounds, drawing, pigments, layers, working order), with sources, and a box of tubes holding only the pigments the artist is documented using.</p>
<div class="alist">{acards}</div>""", 1))

    how = HOW.read_text(encoding="utf-8")
    (out / "how.html").write_text(page("How it works · Claude Art", how, 0))

    # the studio viewer, as the public studio exports it, with a way home
    subprocess.run(["uv", "run", "--quiet", str(REPO / "studio/export_static.py"), str(out / "studio"),
                    "--skip", *sorted(listed(REMOVED))], check=True, stdout=subprocess.DEVNULL)
    idx = out / "studio/index.html"
    s = idx.read_text(encoding="utf-8")
    if 'id="home"' not in s:
        s = s.replace("<header>\n", '<header>\n  <a id="home" href="../index.html" style="color:#e8e6df;text-decoration:none;font:600 16px Georgia,serif;margin-right:10px">Claude Art</a>\n', 1)
        idx.write_text(s, encoding="utf-8")

    # nothing that names this machine's owner
    name = re.compile(r"(?<![A-Za-z0-9])" + re.escape(USER) + r"(?![A-Za-z0-9])", re.I)
    for f in out.rglob("*.html"):
        t = f.read_text(encoding="utf-8", errors="replace")
        if HOME in t or name.search(t):
            sys.exit(f"build: {f} names the home folder or the account")
    print(f"built {len(done)} paintings, {len(live)} painting now, into {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(STUDIOS / ".claude-art-site"))
    build(Path(ap.parse_args().out))
