# Painter harness: Claude Code

The painter runs in Claude Code (`claude -p`) in place of pi and is billed to a Claude
subscription, never an API key. The studio, brief, system prompt, tools and sittings are round
21.5's (`notes/round21.5/runner/`, `harness/painter/`).

| file | what it is |
|---|---|
| `easel_mcp.py` | the painter's six tools (`paint`, `look`, `note`, `status`, `log`, `read`) as a stdio MCP server, ported from `harness/painter/easel-tools.ts`, `easel-client.ts` and `journal.ts`, with the same replies and the same hidden counters |
| `paint.py` | the runner: exports a studio, writes BRIEF.md, signs the painter in, runs the sittings and waits out usage limits |

## Use

```sh
uv run harness/claude-code/paint.py login                # once: sign the painter in to your Claude account
uv run harness/claude-code/paint.py account              # who it bills to: email, plan
uv run harness/claude-code/paint.py profiles             # friedrich, sargent, inness, alma-tadema, hopper, tonn
uv run harness/claude-code/paint.py new monet --subject "haystacks at sunset"   # export a studio and paint (sonnet, high effort)
uv run harness/claude-code/paint.py go paint-studio-1a2b3c   # carry on after a stop
uv run harness/claude-code/paint.py go paint-studio-1a2b3c --adopt --hard-cap 150   # take over a painter an earlier runner left painting
```

**Time at the easel.** A new painting has a budget (`--budget`, default 60 minutes) and a hard cap
(`--hard-cap`, default 90). The brief tells the painter its budget, and the easel's replies say when
15 and 5 minutes are left and when time is up (easel_mcp.py `--clock`, from the run folder's
`clock.json`). The runner starts no new sitting once the budget is used, and it stops the painter at
the hard cap. Time is counted from the sittings' own run time, so a usage limit's wait doesn't count.
`--budget 0 --hard-cap 0` paints without a limit, as the rounds before did. This is a change from the
rounds' design, which kept every clock and count away from the painter.

Studios go to `~/paint-studios/` (`PAINT_STUDIOS`). The run data goes to
`~/paint-studios/runs/<studio>/`, outside the studio: `meta.json`, `sittings.json`, each sitting's
`NN_s<k>[_part<p>].jsonl` (stream-json) and `.err`, `paint.log`, and `reply.md`. The session transcripts are
Claude Code's own, in `~/.claude-paint/projects/`.

## Isolation

The painter's Claude Code has its own config folder (`PAINTER_CLAUDE_CONFIG`, default
`~/.claude-paint`) and an environment built from nothing: `HOME`, `PATH`, `LANG`,
`CLAUDE_CONFIG_DIR`, `CLAUDE_CODE_DISABLE_CLAUDE_MDS` and `_AUTO_MEMORY` (a CLAUDE.md in a
folder above the studio otherwise reaches the painter, even with `--system-prompt`; tested), `MCP_TOOL_TIMEOUT` (35 min: past the 12 a chunk may run and the 30 a stalled replay may wait) and, if present,
`CLAUDE_CODE_OAUTH_TOKEN` from `~/.config/claude-paint/oauth-token` (made by `claude setup-token`).
This keeps out everything from the machine's own Claude Code: its login, its `settings.json` env
(a gateway `ANTHROPIC_BASE_URL`, custom headers), hooks, `CLAUDE.md`, memory, skills, plugins and
MCP servers. `--bare` can't be used, because it accepts only an API key.

The flags: `--thinking-display summarized` (Claude Code otherwise records no thinking, and the
viewer shows it), `--system-prompt` (harness/painter/system_prompt.md, word for word), `--tools ""` (no
built-in tools), `--strict-mcp-config --mcp-config` (only the easel), `--allowedTools
mcp__easel__*`, `--permission-mode dontAsk`, `--disable-slash-commands`, `--output-format
stream-json --verbose`.

`account` and every `new`/`go` refuse to paint unless `claude auth status` shows a first-party
subscription login.

## Differences from the pi harness

- **Tool names.** The model sees `mcp__easel__paint` and so on. The guide's names (`paint`,
  `look`) still map onto them.
- **Images and compaction.** Claude Code's own: images stay in context until auto-compaction,
  which writes a model summary. pi's `context-images.ts` pruning and `compaction.ts`
  deterministic summary aren't ported.
- **Usage limits.** The run waits out a limit (the reset time from the message, else 30-minute
  probes, giving up after 24 h), then resumes the same session with "Carry on where you left off."
  pi held the request and retried with nothing added. A sitting stopped by the runner (Ctrl-C, a
  kill) carries on in its session the same way when `go` runs again. A crash, or a stop before the
  painter did anything, takes the sitting again in a new session.
- **One runner per studio.** `go` holds a lock in the run folder, and refuses to start while a
  painter from an earlier run is still alive.
- **Sittings.** A later sitting is a new session with SITTING_MESSAGE. pi's
  PAINTER_SITTING_RECOVERY summary isn't ported; the painter reads its journal and looks.
- **Viewer.** `studio/studio.py` reads pi session logs and doesn't yet read Claude Code
  transcripts.
