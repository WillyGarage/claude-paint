# Round 22: new tubes and nine boxes (not for painters)

Nine research agents each wrote a materials note (`notes/research/<artist>_materials.md`) and a
tube proposal (`notes/r22/research/<artist>_tubes.md`), under the round 20 rule for historical
painters (`notes/r20/TUBES.md`, "The boxes"): a tube is in the box if its pigment is documented in
use, in his or her working materials, or a one-off purchase nothing contradicts. Faces and any
subject are allowed; no box or note restricts them.

All numbers are estimates in the style of `palette.rs`, not measurements. Each proposal marks
which values have a sourced direction.

## New catalog tubes (12)

Columns: masstone, hiding, stiffness, tinting strength, drying. Letters: L Leonardo, R Rembrandt,
M Monet, V Van Gogh, U Munch, P Picasso, I Miró, D Dalí, K Kahlo.

| tube | pigment | masstone | hid | stiff | str | dry | from | reconciliation |
|---|---|---|---|---|---|---|---|---|
| charcoal black | vegetable carbon (wood or vine charcoal) | `#232529` | 0.75 | 0.6 | 0.7 | `LAMP_BLACK` | L, R, U, D | Four proposals for one pigment (D's "blue black" is vine black). Masstones `#26282b` `#1f2226` `#26282c` `#1d1f25`, all estimates: a middle value. Hiding 0.8/0.75/0.75/0.85: majority 0.75. Stiffness 0.6 (3 of 4). Strength 0.6 (L, U) vs 0.8 (R, D): a tie between estimates, each resting on the same period source's "weaker body than ivory or lamp black" (Salter §290); split at 0.7. Drying `LAMP_BLACK` (3 of 4; L had `BONE_BLACK`) |
| azurite | basic copper carbonate, the ground mineral | `#255786` | 0.55 | 0.5 | 0.45 | `COPPER` | L, R | Masstones `#2a5684` / `#205988` (estimates): between. Hiding 0.55 both. Stiffness 0.45 / 0.6 and strength 0.4 / 0.5: ties between estimates, split. Drying `COPPER` both |
| natural ultramarine | lazurite from lapis lazuli, a full-strength grade | `#1f276e` | 0.25 | 0.5 | 0.8 | `ULTRAMARINE` | L | only L. The catalog's `ultramarine blue` is the synthetic pigment (from 1828) and `ultramarine ash` the pale last extraction |
| whiting | calcium carbonate (chalk) | `#d0c5b2` | 0.08 | 0.75 | 0.1 | `RED_EARTH` | R | only R, proposed as "chalk". Renamed: `chalk` is the easel's chalk pencil (`pencil("chalk")`), so every easel binary holds the word and the export's tube check (`scripts/check_box_tubes`) would find a stray tube in every box without it. Whiting is prepared chalk's trade name |
| Cassel earth | humic earth (lignite brown) | `#45392f` | 0.2 | 0.4 | 0.7 | `BONE_BROWN` | R | only R |
| yellow lake | buckthorn dye laked on chalk or alumina | `#8f6c12` | 0.1 | 0.35 | 0.5 | `MADDER_LAKE` | R | only R |
| cochineal lake | cochineal (carminic acid) lake on alumina | `#6f1032` | 0.1 | 0.35 | 0.8 | `MADDER_LAKE` | R | only R. Kept apart from V's carmine: a different grade and base, with different numbers (the round 20 rule keeps grades a palette lists separately as separate tubes) |
| carmine | cochineal lake on an alumina and calcium base | `#6e1426` | 0.3 | 0.45 | 1.2 | `MADDER_LAKE` | V | only V |
| zinc yellow | lead-free chromate yellow (zinc, barium or strontium chromate) | `#e5dd55` | 0.45 | 0.6 | 0.5 | `MARS` | V, M | V proposed "zinc yellow" (zinc potassium chromate), M "lemon yellow" (barium, zinc and strontium chromates). One tube: masstones `#e3da4f` / `#e8e05c` (estimates), between. Hiding 0.45 and stiffness 0.6 both. Strength 0.6 (V, estimate) / 0.5 (M, direction sourced): M's. Drying `RED_EARTH` (V, estimate) / `MARS` (M, direction sourced: no lead drier): M's. Named for the pigment both found by analysis; M's note maps to it |
| geranium lake | eosin lake on alumina | `#b11d45` | 0.12 | 0.3 | 1.4 | `MADDER_LAKE` | V | only V. It fades fast, which the engine doesn't model |
| titanium white | titanium dioxide | `#f5f5f2` | 0.95 | 0.6 | 2.0 | `ZINC_WHITE` | I | only I. Strength compressed from the measured ~8x lead white's, as Prussian blue's is |
| aureolin | potassium cobaltinitrite | `#d4a52a` | 0.2 | 0.4 | 0.7 | `COBALT_BLUE` | D | only D |

P and K proposed no new tube. Picasso's Ripolin enamel is a medium, not a pigment: its white is
zinc oxide (`zinc white`), and the note says what the easel can't do.

## The boxes

Each is exactly its proposal's box, with the merges above (D's blue black and the charcoal blacks
are `charcoal black`, M's lemon yellow is `zinc yellow`, R's chalk is `whiting`).

- **leonardo** (15): lead white, lead-tin yellow, yellow ochre, brown ochre, red earth, vermilion,
  rose madder, red lead, azurite, natural ultramarine, copper green, raw umber, bone brown,
  charcoal black, bitumen.
- **rembrandt** (17): lead white, whiting, lead-tin yellow, yellow ochre, yellow lake, vermilion,
  red earth, rose madder, cochineal lake, brown ochre, raw umber, Cassel earth, bone black,
  charcoal black, smalt, pale smalt, azurite.
- **monet** (21): lead white, zinc white, Naples yellow, chrome yellow, zinc yellow, pale cadmium,
  cadmium yellow, deep cadmium, yellow ochre, red earth, burnt sienna, vermilion, rose madder, bone
  black, Prussian blue, cobalt blue, ultramarine blue, cerulean blue, viridian, emerald green,
  cobalt violet.
- **van-gogh** (25): lead white, zinc white, lemon chrome, zinc yellow, chrome yellow, cadmium
  yellow, deep cadmium, orange chrome, yellow ochre, raw sienna, red earth, raw umber, vermilion,
  red lead, geranium lake, carmine, rose madder, cobalt violet, emerald green, viridian, cerulean
  blue, cobalt blue, ultramarine blue, Prussian blue, bone black.
- **munch** (22): lead white, zinc white, vermilion, cadmium red, rose madder, red earth, yellow
  ochre, raw umber, chrome yellow, lemon chrome, pale cadmium, cadmium yellow, deep cadmium,
  viridian, emerald green, Prussian blue, ultramarine blue, cobalt blue, cerulean blue, cobalt
  violet, bone black, charcoal black.
- **picasso** (20): lead white, zinc white, lemon chrome, chrome yellow, cadmium yellow, yellow
  ochre, Mars yellow, Mars orange, vermilion, Mars red, red earth, brown ochre, bone black,
  Prussian blue, ultramarine blue, cobalt blue, cerulean blue, viridian, emerald green, cobalt
  violet.
- **miro** (21): lead white, zinc white, titanium white, pale cadmium, cadmium yellow, deep
  cadmium, cadmium red, vermilion, rose madder, Mars orange, red earth, raw sienna, burnt sienna,
  raw umber, cobalt blue, cerulean blue, ultramarine blue, Prussian blue, viridian, cobalt violet,
  bone black.
- **dali** (26): lead white, zinc white, Naples yellow, aureolin, lemon chrome, pale cadmium,
  cadmium yellow, deep cadmium, yellow ochre, Mars yellow, raw sienna, Mars orange, red earth,
  vermilion, cadmium red, rose madder, Indian red, burnt sienna, bone black, charcoal black, cobalt
  blue, cerulean blue, ultramarine blue, viridian, Rinmann's green, cobalt violet.
- **kahlo** (13): lead white, zinc white, vermilion, cadmium red, red earth, chrome yellow, cadmium
  yellow, yellow ochre, brown ochre, cerulean blue, ultramarine blue, magenta, bone black.

Yellow ochre (not in miro) and bone black (not in leonardo) are no longer in every box, so they
now carry a `cfg` like the rest. Every tube's `cfg` in `catalog()` is generated from the box lists:
`tube_box` if the default box holds it, a `box-*` feature for each box that does, none if every
box does (only lead white now).
