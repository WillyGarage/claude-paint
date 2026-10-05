# Round 22: Claude Code painters, nine new studios, a public site

Built on `round-21.5`'s code. This file and `TUBES.md` are for developers; no studio gets them.

## What changed

- **The painter runs in Claude Code** (`harness/claude-code/`, see its README), in place of pi. It
  is billed to a Claude subscription, never an API key, and kept apart from the machine's own Claude
  Code setup. `easel_mcp.py` gives it the same six tools as `harness/painter/easel-tools.ts`, as a
  stdio MCP server. `paint.py` exports a studio, writes BRIEF.md, and runs the sittings: usage
  limits are waited out, an interrupted sitting carries on in its own session, and a painter an
  earlier runner left running can be taken over (`go --adopt`).
- **Time at the easel.** New paintings default to a 60-minute budget, which the brief states and the
  easel's replies count down (`--clock`), and a 90-minute hard cap. This is a change from the
  rounds' design, which kept every clock away from the painter.
- **A subject.** `paint.py new <profile> --subject "..."` names the subject; the composition stays
  free. It fits the openings of the new studios ("The subject and composition are yours to invent").
- **Default painter: Sonnet 5.5, high effort.** In round 23's test (below) it came close to Opus
  for about a tenth of the usage. Haiku 4.5 wasn't usable.
- **Nine new boxes and studios:** leonardo, rembrandt, monet, van-gogh, munch, picasso, miro, dali
  and kahlo. Each has a materials note (`notes/research/<artist>_materials.md`, researched for this
  round) and a box of documented pigments. Twelve tubes are new in the catalog; `TUBES.md` gives
  their numbers, the merges and the boxes. Every tube's `cfg` in `catalog()` is now generated
  from the box lists. Yellow ochre and bone black are no longer in every box.
- **Export and checks.** There are export profiles for the nine. `check_studio_names` adds Dalí,
  Kahlo and Miró, and matches Monet as `Monet(?!ary)`: Lua's `os.setlocale` names a "monetary"
  category, so every easel binary holds the word. The tube Rembrandt's research called "chalk" is
  `whiting`, because `chalk` is the easel's chalk pencil, whose name every binary holds.
- **Studio viewer.**
  - It reads Claude Code transcripts as well as pi's session logs. `--thinking-display summarized`
    makes Claude Code record the thinking.
  - The static export writes JPEG views (`v/`, 1200 px) and thumbnails (`t/`) beside the PNGs, so
    the page loads quickly.
  - The account-name scrub matches whole words only. It used to turn "billowing" into "userowing".
  - A chunk's reply `ok` (round 21.3 on) counts as success.
- **Public site** (`site/`): `build.py` makes a gallery of finished paintings, a page per painting,
  the artists' boxes and research, how-it-works (an example from stillwet.art, CC BY 4.0, credited)
  and the studio. `publish.py` uploads what changed. Every page credits claude-paint's author and
  links to https://stillwet.art. `site-hidden.txt` and `site-removed.txt` in the studios folder keep
  paintings out of the gallery, or off the site altogether.

## Exporting before this is on a branch

`export_r16_studio` builds from a commit (`R16_BRANCH`). During the round, exports were made from an
off-branch snapshot commit of the working tree (`git commit-tree` with a temporary index), so no
branch moved.

## Verification

- `cargo test --release -p paint`: 169 passed, 2 failed. `-p easel`: 57 passed, 1 failed. The three
  failures are golden-hash tests (`fixture_matches_golden`,
  `ploughing_films_at_the_threshold_leaves_the_recorded_cure`,
  `logs_without_an_engine_line_replay_as_before`). They fail the same way on round 21.5's
  unmodified code on this x86 machine; their goldens were recorded on the author's machine.
- All nine new studios and the seven earlier ones export with every check passing.
  `scripts/tests/box_notes.sh` passes for the nine.
- The MCP tools were exercised one by one, and `claude -p` drove them, images included. The sitting
  loop was tested with a stand-in `claude` (a usage limit, then the same session carrying on; a
  killed runner, then `go`), and the time notes by unit.

## The paintings (Claude Code, the owner's subscription)

Round 22 had one painter per new studio, plus one Friedrich, all on Opus 5.5 at high effort.
Times ran from 8 minutes (Miró) to about 2.5 hours (Rembrandt and Leonardo, which kept reworking
faces and hands). The cap was added after that. A Rembrandt retry under the budget took 47 minutes
and wasn't better: Rembrandt's glazed, soft-edged method fits this easel poorly.

Round 23 compared models and effort levels on Monet and Picasso, each run with a different subject:

| setting | time | API-equivalent cost | result |
|---|---|---|---|
| Opus 5.5, high | 13–60 min | $2–6 | best |
| Opus 5.5, medium | 10–12 min | $1–2 | good to weak |
| Sonnet 5.5, high | 10–12 min | about $0.55 | good |
| Sonnet 5.5, medium | 7–15 min | $0.20–0.30 | uneven |
| Haiku 4.5, high | 5–7 min | $0.25–0.45 | not usable |
