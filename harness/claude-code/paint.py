# /// script
# requires-python = ">=3.10"
# ///
"""Run a painter in a studio with Claude Code (`claude -p`), billed to a Claude subscription.

    uv run harness/claude-code/paint.py login                      # once: sign the painter in (opens a browser link)
    uv run harness/claude-code/paint.py account                    # which account and plan the painter uses
    uv run harness/claude-code/paint.py new <profile> [--model opus] [--effort high] [--sittings 4]
    uv run harness/claude-code/paint.py go <studio>                # carry on: after a stop, a crash or a usage limit
    uv run harness/claude-code/paint.py profiles

The pi runner (notes/round21.5/runner/r21_chains.py) with Claude Code in pi's place, for one
painter in one studio:

- The studio is exported as before (scripts/export_r16_studio, R16_BRANCH, default HEAD), with
  round 21.5's studio notes, trees.md for Friedrich, and BRIEF.md from round 21.5's template.
- The painter's tools are easel_mcp.py, the only tools it has: no shell, no file tools, no web.
  Its system prompt is harness/painter/system_prompt.md, word for word.
- Claude Code runs with its own config folder (PAINTER_CLAUDE_CONFIG, default ~/.claude-paint) and
  an environment built from nothing, so nothing of the machine's own Claude Code setup reaches the
  painter (settings, hooks, CLAUDE.md, memory, skills, MCP servers, a gateway URL or an API key).
  It signs in with that folder's own login (`login`), or with CLAUDE_CODE_OAUTH_TOKEN read from
  ~/.config/claude-paint/oauth-token (from `claude setup-token`). A painter never runs on an API key.
- Sittings as in round 21: sitting 1 gets PAINTER_MSG, later ones SITTING_MESSAGE, each in a new
  session at the same open easel, until a sitting the painter ends adds no chunks (at most
  --sittings). A usage limit is waited out and the same session carries on.

Run data (stream-json of every sitting, sittings.json, the reply) goes to <studios>/runs/<studio>/,
outside the studio, so the painter never reads it. Studios live in PAINT_STUDIOS (~/paint-studios).
"""
import argparse
import fcntl
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import textwrap
import time
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
R21 = REPO / "notes/round21.5/runner"            # brief_template.md, studio_notes.md, trees.md
MCP_SERVER = HERE / "easel_mcp.py"
SYSTEM_PROMPT = REPO / "harness/painter/system_prompt.md"
STUDIOS = Path(os.environ.get("PAINT_STUDIOS", "~/paint-studios")).expanduser()
CONFIG = Path(os.environ.get("PAINTER_CLAUDE_CONFIG", "~/.claude-paint")).expanduser()
TOKEN_FILE = Path("~/.config/claude-paint/oauth-token").expanduser()
TOOLS = ["paint", "look", "note", "status", "log", "read"]

PAINTER_MSG = ("Your brief is in BRIEF.md in this folder. Your last message is your reply: the "
               "painting's title if you give it one and a few sentences about the picture.")
SITTING_MESSAGE = ("You're back at the easel. The painting is as you left it. "
                   "Your brief is in BRIEF.md and your journal in notes/journal.md.")
CONTINUE_MESSAGE = "Carry on where you left off."
MAX_CRASHES = 6
CRASH_WAITS = [90, 180, 300, 600, 900, 1200]
LIMIT_PROBE_S = 30 * 60                          # the wait when a usage limit names no reset time
LIMIT_GIVE_UP_H = 24
# Time at the easel, for a wall that shows one painting after another: the painter is told its budget in
# the brief and, as it runs out, in the easel's replies (easel_mcp.py --clock); the runner starts no new
# sitting once the budget is used, and stops the painter outright at the hard cap. 0 turns either off.
BUDGET_MIN = 60
HARD_CAP_MIN = 90

# round 21's openings and reading lists (r21_chains.py), one per export profile
OPENING = {
    "friedrich": "landscape in the manner of Caspar David Friedrich",
    "sargent": "portrait in the manner of John Singer Sargent",
    "inness": "landscape in the manner of George Inness",
    "alma-tadema": "scene from Roman antiquity in the manner of Lawrence Alma-Tadema",
    "hopper": "scene of American city life in the manner of Edward Hopper",
    "tonn": "picture in the manner of Kendric Tonn",
    "leonardo": "picture in the manner of Leonardo da Vinci",
    "rembrandt": "picture in the manner of Rembrandt van Rijn",
    "monet": "picture in the manner of Claude Monet",
    "van-gogh": "picture in the manner of Vincent van Gogh",
    "munch": "picture in the manner of Edvard Munch",
    "picasso": "picture in the manner of Pablo Picasso",
    "miro": "picture in the manner of Joan Miró",
    "dali": "picture in the manner of Salvador Dalí",
    "kahlo": "picture in the manner of Frida Kahlo",
}
OPENING_TEXT = {
    "friedrich": (
        "Compose and paint one original landscape in the manner of Caspar David\n"
        "Friedrich, at the easel, a simulator of oil paint on linen. The place,\n"
        "subject and composition are yours to invent. Work from knowledge and the\n"
        "notes in your studio; don't use reference images, image models or pictures\n"
        "of his work."),
    "sargent": (
        "Compose and paint one original portrait in the manner of John Singer\n"
        "Sargent, at the easel, a simulator of oil paint on linen. The sitter,\n"
        "setting and composition are yours to invent. Work from knowledge and the\n"
        "notes in your studio; don't use reference images, image models or pictures\n"
        "of his work."),
    "inness": (
        "Compose and paint one original landscape in the manner of George Inness,\n"
        "at the easel, a simulator of oil paint on linen. The place, subject and\n"
        "composition are yours to invent. Work from knowledge and the notes in your\n"
        "studio; don't use reference images, image models or pictures of his work."),
    "alma-tadema": (
        "Compose and paint one original scene from Roman antiquity in the manner of\n"
        "Lawrence Alma-Tadema, at the easel, a simulator of oil paint on linen. The\n"
        "subject, setting and composition are yours to invent. Work from knowledge\n"
        "and the notes in your studio; don't use reference images, image models or\n"
        "pictures of his work."),
    "hopper": (
        "Compose and paint one original scene of American city life in the manner\n"
        "of Edward Hopper, at the easel, a simulator of oil paint on linen. The\n"
        "subject, setting and composition are yours to invent. Work from knowledge\n"
        "and the notes in your studio; don't use reference images, image models or\n"
        "pictures of his work."),
    "tonn": (
        "Compose and paint one original picture in the manner of Kendric Tonn, at\n"
        "the easel, a simulator of oil paint on linen. The subject and composition\n"
        "are yours to invent. Work from knowledge and the notes in your studio;\n"
        "don't use reference images, image models or pictures of his work."),
    # round 22's studios (notes/r22/BUILD.md)
    "leonardo": (
        "Compose and paint one original picture in the manner of Leonardo da Vinci,\n"
        "at the easel, a simulator of oil paint on linen. The subject and composition\n"
        "are yours to invent. Work from knowledge and the notes in your studio; don't\n"
        "use reference images, image models or pictures of his work."),
    "rembrandt": (
        "Compose and paint one original picture in the manner of Rembrandt van Rijn,\n"
        "at the easel, a simulator of oil paint on linen. The subject and composition\n"
        "are yours to invent. Work from knowledge and the notes in your studio; don't\n"
        "use reference images, image models or pictures of his work."),
    "monet": (
        "Compose and paint one original picture in the manner of Claude Monet, at the\n"
        "easel, a simulator of oil paint on linen. The subject and composition are\n"
        "yours to invent. Work from knowledge and the notes in your studio; don't use\n"
        "reference images, image models or pictures of his work."),
    "van-gogh": (
        "Compose and paint one original picture in the manner of Vincent van Gogh, at\n"
        "the easel, a simulator of oil paint on linen. The subject and composition\n"
        "are yours to invent. Work from knowledge and the notes in your studio; don't\n"
        "use reference images, image models or pictures of his work."),
    "munch": (
        "Compose and paint one original picture in the manner of Edvard Munch, at the\n"
        "easel, a simulator of oil paint on linen. The subject and composition are\n"
        "yours to invent. Work from knowledge and the notes in your studio; don't use\n"
        "reference images, image models or pictures of his work."),
    "picasso": (
        "Compose and paint one original picture in the manner of Pablo Picasso, at\n"
        "the easel, a simulator of oil paint on linen. The subject and composition\n"
        "are yours to invent. Work from knowledge and the notes in your studio; don't\n"
        "use reference images, image models or pictures of his work."),
    "miro": (
        "Compose and paint one original picture in the manner of Joan Miró, at the\n"
        "easel, a simulator of oil paint on linen. The subject and composition are\n"
        "yours to invent. Work from knowledge and the notes in your studio; don't use\n"
        "reference images, image models or pictures of his work."),
    "dali": (
        "Compose and paint one original picture in the manner of Salvador Dalí, at\n"
        "the easel, a simulator of oil paint on linen. The subject and composition\n"
        "are yours to invent. Work from knowledge and the notes in your studio; don't\n"
        "use reference images, image models or pictures of his work."),
    "kahlo": (
        "Compose and paint one original picture in the manner of Frida Kahlo, at the\n"
        "easel, a simulator of oil paint on linen. The subject and composition are\n"
        "yours to invent. Work from knowledge and the notes in your studio; don't use\n"
        "reference images, image models or pictures of her work."),
}
READING = {
    p: ("notes/easel_guide.md; notes/studio_notes.md;\n"
        f"notes/research/{f}_materials.md (his materials and method)"
        " and\nnotes/research/oil_paint_physics.md as needed.")
    for p, f in [("sargent", "sargent"), ("inness", "inness"), ("alma-tadema", "alma_tadema"),
                 ("tonn", "tonn"), ("hopper", "hopper"),
                 ("leonardo", "leonardo"), ("rembrandt", "rembrandt"), ("monet", "monet"), ("van-gogh", "van_gogh"),
                 ("munch", "munch"), ("picasso", "picasso"), ("miro", "miro"), ("dali", "dali")]
}
READING["kahlo"] = READING["dali"].replace("dali_materials.md (his", "kahlo_materials.md (her")
READING["friedrich"] = ("notes/easel_guide.md; notes/studio_notes.md;\n"
                        "notes/research/friedrich_materials.md (his materials and method, sourced);\n"
                        "notes/research/trees.md (how trees are built) and\n"
                        "notes/research/oil_paint_physics.md as needed.")


def log(run, msg):
    line = f"{time.strftime('%F %T')} {msg}"
    print(line, flush=True)
    if run:
        with (run / "paint.log").open("a") as f:
            f.write(line + "\n")


def tilde(p):
    home = Path.home()
    return "~/" + str(Path(p).relative_to(home)) if Path(p).is_relative_to(home) else str(p)


# ---- the painter's Claude Code ------------------------------------------------------------------

def claude_bin():
    c = shutil.which("claude")
    if not c:
        sys.exit("paint: no `claude` on PATH (install Claude Code)")
    return c


def painter_env():
    """Built from nothing: the painter's own config folder, no gateway, no API key, no session of ours."""
    claude, uv = claude_bin(), shutil.which("uv") or sys.exit("paint: no `uv` on PATH")
    path = [str(Path(claude).parent), str(Path(uv).parent), "/usr/local/bin", "/usr/bin", "/bin"]
    env = {"HOME": str(Path.home()), "PATH": ":".join(dict.fromkeys(path)), "LANG": os.environ.get("LANG", "C.UTF-8"),
           "TERM": "dumb", "CLAUDE_CONFIG_DIR": str(CONFIG), "MCP_TOOL_TIMEOUT": str(35 * 60 * 1000),
           "DISABLE_AUTOUPDATER": "1",
           # no CLAUDE.md from the studio's parent folders (--system-prompt alone doesn't keep them out), no memory
           "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1", "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
           "CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS": "1"}
    if TOKEN_FILE.exists():
        env["CLAUDE_CODE_OAUTH_TOKEN"] = TOKEN_FILE.read_text().strip()
    if "RAYON_NUM_THREADS" in os.environ:
        env["RAYON_NUM_THREADS"] = os.environ["RAYON_NUM_THREADS"]
    return env


def account():
    """The painter's sign-in, as `claude auth status` reports it; exits if it can't paint on a subscription."""
    r = subprocess.run([claude_bin(), "auth", "status", "--json"], env=painter_env(), capture_output=True, text=True,
                       stdin=subprocess.DEVNULL)
    try:
        a = json.loads(r.stdout)
    except json.JSONDecodeError:
        sys.exit(f"paint: `claude auth status` said:\n{r.stdout}{r.stderr}")
    if not a.get("loggedIn"):
        sys.exit("paint: the painter isn't signed in. Run: uv run harness/claude-code/paint.py login")
    method = str(a.get("authMethod", ""))
    if a.get("apiProvider") != "firstParty" or "api" in method.lower():
        sys.exit(f"paint: the painter is signed in with {method or a.get('apiProvider')}, not a Claude subscription; "
                 "sign it in to your Claude account (`paint.py login`)")
    return a


def system_prompt():
    t = SYSTEM_PROMPT.read_text()
    return re.sub(r"\A\s*<!--.*?-->\s*", "", t, flags=re.S).strip()


def painter_cmd(studio, meta, message, session=None, clock=None):
    servers = {"mcpServers": {"easel": {"command": shutil.which("uv"),
                                        "args": ["run", "--quiet", str(MCP_SERVER), str(studio)]
                                                + (["--clock", str(clock)] if clock else [])}}}
    cmd = [claude_bin(), "-p", message,
           "--model", meta["model"], "--effort", meta["effort"],
           # the thinking, summarized, in the transcript and the stream (Claude Code omits it by default;
           # the showThinkingSummaries setting via --settings doesn't take in -p, tested)
           "--thinking-display", "summarized",
           "--system-prompt", system_prompt(),
           "--tools", "",
           "--strict-mcp-config", "--mcp-config", json.dumps(servers),
           "--allowedTools", ",".join(f"mcp__easel__{t}" for t in TOOLS),
           "--permission-mode", "dontAsk",
           "--disable-slash-commands",
           "--output-format", "stream-json", "--verbose"]
    return cmd + (["--resume", session] if session else [])


# ---- the studio ---------------------------------------------------------------------------------

def brief(profile, studio, budget_min=0, subject=None):
    t = (R21 / "brief_template.md").read_text()
    opening = OPENING_TEXT[profile]
    if subject:   # a subject given (a wall's suggestion): the composition stays the painter's
        flat = re.sub(r"\s+", " ", opening)
        assert "The subject and composition are yours to invent." in flat, f"{profile}: its opening has no free subject to replace"
        flat = flat.replace("The subject and composition are yours to invent.",
                            f"The subject: {subject.strip().rstrip('.')}. The composition is yours to invent.")
        opening = "\n".join(textwrap.wrap(flat, 76))
    t = t.replace("{OPENING}", opening).replace("{STUDIO}", tilde(studio)).replace("{READING}", READING[profile])
    if budget_min:
        done = "- Develop the painting until you judge it complete."
        assert done in t, "brief_template.md changed: the line about finishing isn't there"
        t = t.replace(done, f"- You have about {budget_min} minutes at the easel for this picture; the easel's\n"
                            "  replies tell you when time is nearly up. Develop the painting until you judge\n"
                            "  it complete, within that time.")
    return t


def new_studio(profile, args):
    if profile not in OPENING_TEXT:
        sys.exit(f"paint: no profile {profile!r}; one of: {', '.join(OPENING_TEXT)}")
    a = account()
    name = "paint-studio-" + secrets.token_hex(3)
    d, run = STUDIOS / name, STUDIOS / "runs" / name
    run.mkdir(parents=True)
    branch = os.environ.get("R16_BRANCH", "HEAD")
    log(run, f"{name}: exporting the {profile} studio from {branch}")
    env = {**os.environ, "R16_BRANCH": branch}
    r = subprocess.run([str(REPO / "scripts/export_r16_studio"), profile, str(d)], env=env, capture_output=True,
                       text=True, stdin=subprocess.DEVNULL)
    (run / "export.log").write_text(r.stdout + r.stderr)
    if r.returncode:
        sys.exit(f"paint: the export failed (see {run / 'export.log'})")
    shutil.copy(R21 / "studio_notes.md", d / "notes" / "studio_notes.md")
    if profile == "friedrich":
        shutil.copy(R21 / "trees.md", d / "notes" / "research" / "trees.md")
        subprocess.run([str(REPO / "scripts/strip_sources"), str(d / "notes" / "research" / "trees.md")],
                       stdin=subprocess.DEVNULL, check=True)
    (d / "BRIEF.md").write_text(brief(profile, d, args.budget, args.subject))
    meta = {"studio": str(d), "profile": profile, "model": args.model, "effort": args.effort, "sittings": args.sittings,
            "budget_min": args.budget, "hard_cap_min": args.hard_cap, "subject": args.subject,
            "branch": branch, "account": a.get("email"), "plan": a.get("subscriptionType"),
            "created": time.strftime("%F %T")}
    (run / "meta.json").write_text(json.dumps(meta, indent=1))
    log(run, f"{name}: studio ready at {d}; painter {args.model} ({args.effort}) on {a.get('email')} ({a.get('subscriptionType')})")
    return d


def count_chunks(studio):
    p = studio / "paintings/lua/painting.lua"
    return sum(1 for line in p.read_text().splitlines() if line.startswith("--@ chunk")) if p.exists() else 0


def open_easel(studio, run):
    """Replay the painting before the painter starts, so 'the painting is as you left it' is true."""
    p = subprocess.Popen([str(studio / "bin/easel"), "open"], cwd=studio, stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in p.stdout:
        if not line.startswith("resuming "):
            log(run, f"easel: {line.rstrip()}")
    return p.wait() == 0


def close_easel(studio):
    subprocess.run(["timeout", "60", str(studio / "bin/easel"), "close"], cwd=studio, stdin=subprocess.DEVNULL,
                   capture_output=True)


# ---- a sitting ----------------------------------------------------------------------------------

def read_stream(path):
    """(session id, the result message or None, the last assistant text, tool calls made) from a sitting's stream-json."""
    session, result, text, calls = None, None, "", 0
    if not path.exists():
        return session, result, text, calls
    for line in path.read_text(errors="replace").splitlines():
        try:
            m = json.loads(line)
        except json.JSONDecodeError:
            continue
        session = m.get("session_id") or session
        if m.get("type") == "result":
            result = m
        elif m.get("type") == "assistant":
            for c in (m.get("message") or {}).get("content") or []:
                if c.get("type") == "text" and c.get("text", "").strip():
                    text = c["text"]
                elif c.get("type") == "tool_use":
                    calls += 1
    return session, result, text, calls


LIMIT = re.compile(r"usage limit|limit reached|rate.?limit|out of (?:extra )?usage|session limit|weekly limit|5-hour limit", re.I)


def limit_reset_s(text, now=None):
    """Seconds until a usage limit lifts, from `...|<epoch>` or `resets 3pm` / `resets 2:30am`, or None."""
    now = now or time.time()
    m = re.search(r"\|(\d{10})\b", text)
    if m:
        return max(0, int(m[1]) - now)
    m = re.search(r"resets?(?: at)? (\d{1,2})(?::(\d{2}))?\s*([ap]m)", text, re.I)
    if m:
        h = int(m[1]) % 12 + (12 if m[3].lower() == "pm" else 0)
        t = datetime.fromtimestamp(now).replace(hour=h, minute=int(m[2] or 0), second=0, microsecond=0)
        if t.timestamp() <= now:
            t += timedelta(days=1)
        return t.timestamp() - now
    m = re.search(r"resets? in ((?:\s*[\d.]+\s*(?:days?|d|hours?|hrs?|h|minutes?|mins?|m)\b)+)", text, re.I)
    if m:
        unit = {"d": 86400, "h": 3600, "m": 60}
        return sum(float(v) * unit[u[0].lower()] for v, u in re.findall(r"([\d.]+)\s*([a-z]+)", m[1], re.I))
    return None


def alive(pid):
    """Whether `pid` is a running Claude Code (a painter left from an earlier run)."""
    try:
        os.kill(pid, 0)
        return "claude" in Path(f"/proc/{pid}/cmdline").read_bytes().decode(errors="replace")
    except (OSError, TypeError):
        return False


def settle(rec, rc, studio):
    """Fill in a sitting's record from its stream: completed, limited, crashed or interrupted (rc None)."""
    sid, result, last_text, calls = read_stream(Path(rec["stream"]))
    errtext = Path(rec["stream"]).with_suffix(".err").read_text(errors="replace") if Path(rec["stream"]).with_suffix(".err").exists() else ""
    if rc is None:
        status, why = "interrupted", ""
    else:
        # a clean exit with no result line still counts, if the painter said something last
        failed = rc != 0 or (result.get("is_error") if result else not last_text)
        why = (((result or {}).get("result") or "") + "\n" + errtext).strip() if failed else ""
        status = ("limited" if LIMIT.search(why + " " + last_text) else "crashed") if failed else "completed"
    rec.update(status=status, exit=rc, session=sid or rec.get("session"), worked=calls > 0,
               chunks_after=count_chunks(studio), end=time.time(), minutes=round((time.time() - rec["start"]) / 60, 1),
               reply=((result or {}).get("result") or last_text) if status == "completed" else None,
               error=why[-4000:] or None, cost_equiv_usd=(result or {}).get("total_cost_usd"))


def used_minutes(sittings):
    """Minutes at the easel so far: the sittings that ended (a usage limit's wait isn't counted)."""
    return sum(s.get("minutes") or 0 for s in sittings if s["status"] != "running")


def settle_adopted(rec, studio):
    """A sitting whose painter this runner didn't start: its stream says whether it finished."""
    _, result, _, _ = read_stream(Path(rec["stream"]))
    settle(rec, 0 if result and not result.get("is_error") else None, studio)


def stop_group(pid):
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass


def sitting(studio, run, meta, sittings, save, k, message, session=None, part=1, chunks_before=None):
    """One sitting (or one part of a sitting carried on in its session), recorded before it starts."""
    stem = f"{len(sittings) + 1:02d}_s{k}" + (f"_part{part}" if part > 1 else "")
    before = count_chunks(studio)
    rec = {"sitting": k, "part": part, "message": message, "session": session, "status": "running", "pid": None,
           "start": time.time(), "stream": str(run / f"{stem}.jsonl"),
           "chunks_before": before if chunks_before is None else chunks_before}
    sittings.append(rec)
    save()
    log(run, f"sitting {k}{f' (part {part}, same session)' if session else ''}: {meta['model']}, {before} chunks on the easel")
    used = used_minutes(sittings)
    budget, cap = meta.get("budget_min") or 0, meta.get("hard_cap_min") or 0
    clock = None
    if budget:
        clock = run / "clock.json"   # easel_mcp.py reads it on every reply: the time left, as the painter is told
        clock.write_text(json.dumps({"used_s": used * 60, "since": time.time(), "budget_s": budget * 60}))
    capped = False
    with open(run / f"{stem}.jsonl", "w") as o, open(run / f"{stem}.err", "w") as e:
        # its own process group: a runner stopped with Ctrl-C stops the painter too
        p = subprocess.Popen(painter_cmd(studio, meta, message, session, clock), cwd=studio, env=painter_env(),
                             stdin=subprocess.DEVNULL, stdout=o, stderr=e, start_new_session=True)
        rec["pid"] = p.pid
        save()
        try:
            try:
                rc = p.wait(timeout=max(1, (cap - used) * 60) if cap else None)
            except subprocess.TimeoutExpired:
                log(run, f"the hard cap ({cap} min at the easel) is reached: stopping the painter")
                stop_group(p.pid)
                p.wait()
                rc, capped = None, True
        except BaseException:
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            p.wait()
            settle(rec, None, studio)
            save()
            raise
    settle(rec, rc, studio)
    if capped:
        rec["status"] = "capped"
    save()
    log(run, f"sitting {k} ended ({rec['status']}, exit {rc}) after {rec['minutes']} min: "
             f"chunks {before} -> {rec['chunks_after']}")
    return rec


def go(studio, adopt=False, **overrides):
    """Paint (or carry on) in a studio. overrides: sittings, budget_min, hard_cap_min (saved to meta.json).
    adopt: if a painter from an earlier runner is still painting, wait for it (stopping it at the hard cap)
    instead of refusing."""
    studio = Path(studio).expanduser().resolve()
    if not (studio / "bin/easel").exists() and (STUDIOS / studio.name / "bin/easel").exists():
        studio = STUDIOS / studio.name
    run = STUDIOS / "runs" / studio.name
    meta = json.loads((run / "meta.json").read_text())
    if any(v is not None for v in overrides.values()):
        meta.update({k: v for k, v in overrides.items() if v is not None})
        (run / "meta.json").write_text(json.dumps(meta, indent=1))
    lock = open(run / "lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit(f"paint: another runner is painting {studio.name}")
    a = account()
    if meta.get("account") and a.get("email") != meta["account"]:
        log(run, f"note: the painter is now signed in as {a.get('email')}, not {meta['account']}")
    sf = run / "sittings.json"
    sittings = json.loads(sf.read_text()) if sf.exists() else []
    save = lambda: sf.write_text(json.dumps(sittings, indent=1))
    if sittings and sittings[-1]["status"] == "running":   # the runner stopped during this sitting
        last = sittings[-1]
        if last.get("pid") and alive(last["pid"]) and not adopt:
            sys.exit(f"paint: a painter from an earlier run is still painting {studio.name} (pid {last['pid']}); "
                     "stop it, let it finish, or `go --adopt` to wait for it")
        capped = False
        if last.get("pid") and alive(last["pid"]):
            cap = meta.get("hard_cap_min") or 0
            before = used_minutes(sittings)
            log(run, f"adopting sitting {last['sitting']} (pid {last['pid']}), still painting"
                     + (f"; it stops at {cap} min at the easel" if cap else ""))
            while alive(last["pid"]):
                if cap and before + (time.time() - last["start"]) / 60 >= cap:
                    log(run, f"the hard cap ({cap} min at the easel) is reached: stopping the painter")
                    stop_group(last["pid"])
                    capped = True
                    for _ in range(60):
                        if not alive(last["pid"]):
                            break
                        time.sleep(1)
                    break
                time.sleep(10)
        if capped:
            settle(last, None, studio)
            last["status"] = "capped"
        else:
            settle_adopted(last, studio)
        save()
        log(run, f"sitting {last['sitting']} ended ({last['status']}) after {last['minutes']} min: "
                 f"chunks {last['chunks_before']} -> {last['chunks_after']}")
    try:
        why = paint_on(studio, run, meta, sittings, save)
    finally:
        close_easel(studio)
    reply = next((s["reply"] for s in reversed(sittings) if s.get("reply")), None)
    if reply:
        (run / "reply.md").write_text(reply + "\n")
    log(run, f"{why}. {count_chunks(studio)} chunks. Log: {studio / 'paintings/lua/painting.lua'}"
             + (f"; reply: {run / 'reply.md'}" if reply else ""))


def paint_on(studio, run, meta, sittings, save):
    """Sittings until the painter is done; the reason the run stops."""
    budget, cap = meta.get("budget_min") or 0, meta.get("hard_cap_min") or 0
    while True:
        last = sittings[-1] if sittings else None
        done = {s["sitting"] for s in sittings if s["status"] == "completed"}
        crashes = sum(1 for s in sittings if s["status"] == "crashed")
        used = used_minutes(sittings)
        if (last and last["status"] == "capped") or (cap and used >= cap):
            return f"the hard cap ({cap} min at the easel) is reached: stopped"
        if last and last["status"] == "completed" and last["chunks_after"] == last["chunks_before"]:
            return f"the painter ended sitting {last['sitting']} without painting: done"
        if last and last["status"] == "completed" and len(done) >= meta["sittings"]:
            return f"{meta['sittings']} sittings: done"
        if last and last["status"] == "limited":
            since = last["end"]   # the limit has held since the first of the limited parts in a row
            for s in reversed(sittings):
                if s["status"] != "limited":
                    break
                since = s["end"]
            if time.time() - since > LIMIT_GIVE_UP_H * 3600:
                return f"a usage limit held for {LIMIT_GIVE_UP_H} h: stopped (run `go` again to carry on)"
            wait = limit_reset_s(last["error"] or "", last["end"])
            wait = LIMIT_PROBE_S if wait is None else wait + 60
            log(run, f"usage limit; waiting {wait / 60:.0f} min")
            time.sleep(max(0, last["end"] + wait - time.time()))
        elif last and last["status"] == "crashed":
            if crashes >= MAX_CRASHES:
                return f"{crashes} crashes: stopped (see {run})"
            w = CRASH_WAITS[min(crashes, len(CRASH_WAITS)) - 1]
            log(run, f"sitting {last['sitting']} crashed ({(last['error'] or '')[-200:].strip()}); "
                     f"another sitting in {w} s")
            time.sleep(w)
        cont = dict(session=None, part=1, chunks_before=None)
        if last and last["status"] in ("limited", "interrupted") and last.get("worked") and last.get("session"):
            # a sitting stopped by a limit or by the runner carries on in its session
            k, msg = last["sitting"], CONTINUE_MESSAGE
            cont = dict(session=last["session"], part=last["part"] + 1, chunks_before=last["chunks_before"])
        else:
            # a crash, or a stop before the painter did anything, takes the sitting again in a new session
            k = (last["sitting"] + 1) if last and last["status"] == "completed" else (last["sitting"] if last else 1)
            msg = PAINTER_MSG if count_chunks(studio) == 0 else SITTING_MESSAGE
            if budget and used >= budget and count_chunks(studio):
                return f"its {budget} minutes at the easel are used: done"
        if not open_easel(studio, run):
            return "the easel didn't open: stopped (run `go` again to retry)"
        sitting(studio, run, meta, sittings, save, k, msg, **cont)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login", help="sign the painter's Claude Code in to your Claude account")
    sub.add_parser("account", help="which account and plan the painter uses")
    sub.add_parser("profiles", help="the studios a painter can be given")
    n = sub.add_parser("new", help="export a studio and paint in it")
    n.add_argument("profile")
    # Sonnet 5.5 at high effort: close to Opus for about a tenth of the usage (round 23's test, notes/r22/BUILD.md)
    n.add_argument("--model", default="sonnet")
    n.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    n.add_argument("--sittings", type=int, default=4)
    n.add_argument("--budget", type=int, default=BUDGET_MIN, help="minutes at the easel the painter is told it has (0: none)")
    n.add_argument("--hard-cap", type=int, default=HARD_CAP_MIN, help="minutes at the easel after which it is stopped (0: none)")
    n.add_argument("--subject", help="the subject to paint (the brief then leaves only the composition free)")
    n.add_argument("--no-paint", action="store_true", help="only export the studio")
    g = sub.add_parser("go", help="paint (or carry on painting) in a studio")
    g.add_argument("studio")
    g.add_argument("--adopt", action="store_true", help="wait for a painter an earlier runner left painting")
    g.add_argument("--sittings", type=int, help="change the most sittings")
    g.add_argument("--budget", type=int, help="change the minutes the painter is told it has")
    g.add_argument("--hard-cap", type=int, help="change the minutes after which it is stopped")
    args = ap.parse_args()
    if args.cmd == "login":
        CONFIG.mkdir(parents=True, exist_ok=True)
        print(f"Signing the painter in (its own login, in {tilde(CONFIG)}). Pick the Claude account it should bill to.")
        sys.exit(subprocess.run([claude_bin(), "auth", "login"], env=painter_env()).returncode)
    if args.cmd == "account":
        a = account()
        print(f"{a.get('email')} · {a.get('subscriptionType')} plan · {a.get('authMethod')} · config {tilde(CONFIG)}")
    elif args.cmd == "profiles":
        for p, what in OPENING.items():
            print(f"{p:12} {what}")
    elif args.cmd == "new":
        d = new_studio(args.profile, args)
        if not args.no_paint:
            go(d)
    elif args.cmd == "go":
        go(args.studio, adopt=args.adopt, sittings=args.sittings, budget_min=args.budget, hard_cap_min=args.hard_cap)


if __name__ == "__main__":
    main()
