# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.10,<2"]
# ///
"""The painter's tools for Claude Code: the easel, and reading the studio's notes. No shell.

A port of the pi extension's tools (harness/painter/easel-tools.ts, easel-client.ts and
journal.ts) to a stdio MCP server, so a Claude Code painter (`claude -p`, see paint.py) gets the
same six tools with the same replies:

  paint(lua)                          `easel do -`; the reply is what the chunk printed, then `ok`
  look(crop?, mode?, size?, grid?)    `easel look`; the reply is the easel's line and the PNG
  note(text, replaces?)               `easel note -`, or a revision of notes/journal.md
  status, log                         the canvas's setup; the painting so far
  read(path, offset?, limit?)         a file in the studio, refused outside it

As in the pi harness, nothing that counts the painter's work or times the machine reaches the
painter: no chunk numbers, no look numbers, no compute seconds. Each easel call runs the studio's
`bin/easel` with a bare environment (PATH, HOME and RAYON_NUM_THREADS), in its own process group,
and the tools run one at a time.

    uv run harness/claude-code/easel_mcp.py <studio> [--clock <clock.json>]

With --clock (paint.py writes it when the painting has a time budget), every reply also says, once
the time left falls to 15 and 5 minutes, how much is left, and after it runs out, that time is up.
"""
import asyncio
import base64
import json
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.types import ImageContent, TextContent

STUDIO = Path(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else os.getcwd()).resolve()
CLOCK = Path(sys.argv[sys.argv.index("--clock") + 1]) if "--clock" in sys.argv else None
_told = set()   # the time notes already given in this sitting
# a chunk may run 10 minutes (the easel's own limit); a log rebuild gets its own stall budget
WAIT_S = {"do": 12 * 60, "other": 3 * 60, "rebuild": 30 * 60}
JOURNAL = "notes/journal.md"
REVISIONS = "out/easel/journal-revisions.jsonl"
READ_LINES, READ_BYTES = 2000, 50_000

mcp = FastMCP("easel")
_one_at_a_time = asyncio.Lock()


class EaselError(Exception):
    pass


def easel(args, stdin="", timeout=None):
    """Run the studio's easel client; (exit code or None on a timeout, stdout and stderr together)."""
    env = {"PATH": "/usr/bin:/bin", "HOME": os.environ.get("HOME", "")}
    if "RAYON_NUM_THREADS" in os.environ:
        env["RAYON_NUM_THREADS"] = os.environ["RAYON_NUM_THREADS"]
    p = subprocess.Popen([str(STUDIO / "bin" / "easel"), *args], cwd=STUDIO, env=env, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        out, _ = p.communicate(stdin.encode(), timeout=timeout)
        return p.returncode, out.decode(errors="replace")
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        p.communicate()
        return None, ""


def step(args, stdin, deadline):
    return easel(args, stdin, max(1.0, deadline - time.monotonic()))


def ensure_open(deadline):
    """Open the easel if needed, waiting out a rebuild from the log; whether a rebuild was awaited."""
    code, out = step(["status"], "", deadline)
    opened = rebuilding = False
    completed, total = -1, None
    progress_deadline = deadline
    while True:
        if code is None:
            raise EaselError("the easel rebuild stalled without progress" if rebuilding
                             else "the easel didn't open in time" if opened else "the easel isn't answering")
        m = re.fullmatch(r"rebuilding from the log \((\d+) of (\d+) chunks\)", out.strip())
        if m:
            k, n = int(m[1]), int(m[2])
            if code != 0 or k > n or k < completed or (total is not None and n != total):
                raise EaselError(f"the easel returned invalid rebuild progress: {out.strip()}")
            total = n
            if not rebuilding or k > completed:
                completed = k
                progress_deadline = time.monotonic() + WAIT_S["rebuild"]
            rebuilding = True
            if time.monotonic() >= progress_deadline:
                raise EaselError("the easel rebuild stalled without progress")
            time.sleep(0.1)
            code, out = step(["status"], "", progress_deadline)
            continue
        if code == 0:
            return rebuilding
        # never open a second easel after an open or a rebuild failure
        if opened or rebuilding:
            raise EaselError(out.strip() or "the easel didn't open")
        opened = True
        code, out = step(["open"], "", deadline)


def at_easel(args, stdin=""):
    """An easel command at an open easel; a failure becomes the tool's error, in the easel's words."""
    wait = WAIT_S["do"] if args[0] == "do" else WAIT_S["other"]
    deadline = time.monotonic() + wait
    if ensure_open(deadline):
        deadline = time.monotonic() + wait
    code, out = step(args, stdin, deadline)
    if code is None:
        raise EaselError("the easel didn't answer; `log` shows whether the chunk ran")
    out = out.rstrip()
    if code != 0:
        raise EaselError(out or "the easel gave no answer")
    return out


def hide_counters(t):
    t = re.sub(r'\[string "chunk \d+"\]', '[string "chunk"]', t)
    return re.sub(r"the chunk ran longer than \d+ minutes and was stopped", "the chunk didn't finish and was stopped", t)


def paint_reply(reply):
    """`ok · chunk 12 (76.50 s to compute)` reads `ok`; lines the chunk printed above it stay."""
    return hide_counters(re.sub(r"(^|\n)ok · chunk \d+(?: \(\d+(?:\.\d+)? s to compute\))?(\n?)$", r"\1ok\2", reply))


def status_reply(reply):
    return re.sub(r"^\d+px · ", "", re.sub(r"^\d+ chunks? · ", "", reply))


def log_reply(log):
    return re.sub(r"^--@ chunk \d+[ \t]*$", "--@ chunk", log, flags=re.M)


def tail(t, max_chars=50_000, whole="paintings/lua/painting.lua"):
    if len(t) <= max_chars:
        return t
    return f"(the first {len(t) - max_chars} characters are left out; read {whole} for all of it)\n" + t[-max_chars:]


def tool_words(t):
    """The easel's look messages name its command-line flags; the tool's words name its options."""
    t = re.sub(r"--crop exceeds 1200 pixels per side; choose a smaller crop \(crops stay 1:1\)",
               "a crop may be at most 500 units on either side; choose a smaller crop", t)
    return re.sub(r"--(crop|mode|size|grid)\b", r"\1", t)


def rename_look(said):
    """`<dir>/look-0012.png (1000x714, 0.04s)` becomes `<dir>/<uuid>.png (1000x714)`, the file renamed to match."""
    lines = said.split("\n")
    m = re.fullmatch(r"(.*\.png)(?: \((\d+x\d+)(?:, \d+(?:\.\d+)?s)?\))?", lines[-1])
    if not m:
        return said, re.sub(r" \(.*\)$", "", lines[-1])
    new = Path(m[1]).parent / f"{uuid.uuid4()}.png"
    (STUDIO / m[1]).rename(STUDIO / new)
    lines[-1] = f"{new} ({m[2]})" if m[2] else str(new)
    return "\n".join(lines), str(new)


def studio_path(path):
    """The file `path` names, links followed; None if that is outside the studio."""
    p = re.sub(r"[\u00A0\u2000-\u200A\u202F\u205F\u3000]", " ", path)
    p = p[1:] if p.startswith("@") else p
    p = re.sub(r"^file://", "", os.path.expanduser(p))
    real = (STUDIO / p).resolve()
    return real if real == STUDIO or STUDIO in real.parents else None


def revise_journal(old, text):
    """Replace the one occurrence of `old` in the journal with `text`; every revision is kept whole."""
    path = STUDIO / JOURNAL
    if not old.strip():
        raise EaselError("note: `replaces` is empty; give the exact text of the passage to replace")
    if not path.exists():
        raise EaselError(f"note: {JOURNAL} has no entries yet")
    before = path.read_text()
    at = before.find(old)
    if at < 0:
        raise EaselError(f"note: the passage given in `replaces` isn't in {JOURNAL} (it has to match exactly)")
    if before.find(old, at + 1) >= 0:
        raise EaselError(f"note: the passage given in `replaces` is in {JOURNAL} more than once; give more of it")
    log = STUDIO / REVISIONS
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as f:
        f.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "replaced": old, "with": text, "before": before}) + "\n")
    path.write_text(before[:at] + text + before[at + len(old):])
    return f"revised in {path}\n"


def image(path):
    suffix = Path(path).suffix.lower()
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}[suffix]
    return ImageContent(type="image", data=base64.b64encode(Path(path).read_bytes()).decode(), mimeType=mime)


def time_note():
    """What the easel says about the time left, or "": at 15 and 5 minutes once each, then at every reply."""
    if not CLOCK:
        return ""
    try:
        c = json.loads(CLOCK.read_text())
    except (OSError, ValueError):
        return ""
    left = (c["budget_s"] - c["used_s"] - (time.time() - c["since"])) / 60
    if left <= 0:
        return "\n\n(Your time at the easel is up. Finish now: the painting will be stopped soon.)"
    for mark, say in ((5, "About 5 minutes of easel time left: bring the painting to a finish."),
                      (15, "About 15 minutes of easel time left.")):
        if left <= mark:
            if mark in _told:
                return ""
            _told.update(m for m in (5, 15) if m >= mark)
            return f"\n\n({say})"
    return ""


def with_note(reply):
    """A tool's reply with the time note added to its text."""
    note = time_note()
    if not note:
        return reply
    if isinstance(reply, str):
        return reply + note
    return [TextContent(type="text", text=reply[0].text + note), *reply[1:]] if reply and reply[0].type == "text" else reply


async def serial(fn, *args):
    """One tool at a time, and the event loop free while the easel works."""
    async with _one_at_a_time:
        return await asyncio.to_thread(fn, *args)


@mcp.tool(structured_output=False, description="Run a chunk of Lua at the easel (notes/easel_guide.md). The reply is what the chunk printed, "
                      "then `ok`. A chunk that stops with an error changes nothing.")
async def paint(lua: str) -> str:
    try:
        return with_note(paint_reply(await serial(at_easel, ["do", "-"], lua)))
    except EaselError as e:
        raise EaselError(hide_counters(str(e))) from None


@mcp.tool(structured_output=False, description="Look at the canvas as it is now. Without options: the whole canvas, scaled down. "
                      "crop: \"x0,y0,x1,y1\" in canvas units (two opposite corners), shown at 1:1 pixels. "
                      "mode: \"value\", \"squint\", \"mirror\" or several, comma-separated. size: the long side in pixels. "
                      "grid: true, or a spacing in canvas units.")
async def look(crop: str | None = None, mode: str | None = None, size: int | None = None,
               grid: bool | float | None = None) -> list[TextContent | ImageContent]:
    args = ["look"]
    if crop:
        args += ["--crop", crop]
    if mode:
        args += ["--mode", mode]
    if size is not None:
        args += ["--size", str(size)]
    if grid is True:
        args += ["--grid"]
    elif grid not in (None, False):
        args += ["--grid", str(int(grid) if float(grid).is_integer() else grid)]
    try:
        said = await serial(at_easel, args)
    except EaselError as e:
        raise EaselError(tool_words(str(e))) from None
    said, path = rename_look(said)
    return with_note([TextContent(type="text", text=said), image(STUDIO / path)])


@mcp.tool(structured_output=False, description="Add an entry to your journal, notes/journal.md, stamped with the painting's time. "
                      "To revise what is already there, give the exact passage to change as `replaces`: `text` takes its place.")
async def note(text: str, replaces: str | None = None) -> str:
    if replaces is not None:
        return with_note(await serial(revise_journal, replaces, text))
    return with_note(await serial(at_easel, ["note", "-"], text))


@mcp.tool(structured_output=False, description="The canvas's setup.")
async def status() -> str:
    return with_note(status_reply(await serial(at_easel, ["status"])))


@mcp.tool(structured_output=False, description="The painting so far: every chunk that ran, in order (paintings/lua/painting.lua).")
async def log() -> str:
    return with_note(tail(log_reply(await serial(at_easel, ["log"]))))


@mcp.tool(structured_output=False, description="Read a file in the studio: a text file (from line `offset`, at most `limit` lines; "
                      f"by default the first {READ_LINES} lines or {READ_BYTES // 1000} KB) or an image.")
async def read(path: str, offset: int | None = None, limit: int | None = None) -> list[TextContent | ImageContent]:
    real = studio_path(path)
    if real is None:
        raise EaselError(f"{path} is outside the studio")
    if not real.is_file():
        raise EaselError(f"{path}: no such file in the studio")
    if real.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        return [TextContent(type="text", text=f"{path}"), image(real)]
    lines = real.read_text(errors="replace").split("\n")
    start = max(1, offset or 1)
    end = min(len(lines), start - 1 + (limit or READ_LINES))
    out, size = [], 0
    for i in range(start - 1, end):
        size += len(lines[i]) + 1
        if size > READ_BYTES and out:
            end = i
            break
        out.append(lines[i])
    text = "\n".join(out)
    if end < len(lines):
        text += f"\n\n[lines {start}-{end} of {len(lines)}; read again with offset={end + 1} for more]"
    return [TextContent(type="text", text=text)]


if __name__ == "__main__":
    if not (STUDIO / "bin" / "easel").exists():
        sys.exit(f"easel_mcp: {STUDIO} has no bin/easel (export a studio first: scripts/export_r16_studio)")
    mcp.run()
