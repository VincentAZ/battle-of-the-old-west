# Portable solo opponent

`OldWestAI.h` exposes `oldwest::AIPlayer(catalog, difficulty, seed)` and
`Choose(viewJson, legalActionsJson)`. The returned string is an unchanged legal
command; an empty string means there is no decision. Call it again after each
accepted action, including choices assigned to the AI during the human's turn.
`Reset(seed)` clears decision history for a rematch. Repeated calls with identical
inputs are idempotent, including the seeded random tie breaker.

The policy receives only the AI seat's player view, its legal action list, and
the public catalog. It has no rules-engine or authoritative-save dependency.
Opponent hand contents are ignored even if mistakenly supplied by a caller.
The AI may use a Wanted Poster Board inspection only when it is present in its own view.

Difficulty affects decisions, not water, cards, health, or rules:

- Easy selects less consistently among plausible legal actions and drafts varied
  camps. It still resolves mandatory choices and completes turns.
- Normal evaluates immediate attacks, protection, healing, events, resources,
  hand retention, placement, and camp combinations.
- Hard adds camp synergy scoring and a bounded two-attack projection of the
  visible battlefield, including clearing a guard before attacking its camp.

Hard is a tactical heuristic opponent, not a solved-game or search-engine claim.
It does not simulate unknown future draws. Compound choices use the public
English labels emitted by the rules core; changing/localizing those labels
requires updating the policy or adding structured public choice metadata.

The policy remembers Silo use within a turn to avoid a store/junk cycle. A
128-action safeguard ends a voluntary action phase if a future card combination
creates an unproductive loop; mandatory choices are always resolved first.

Build and run the portable tests:

```sh
cmake -S game/tests/core -B /tmp/oldwest-ai-core-build -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/oldwest-ai-core-build -j2
ctest --test-dir /tmp/oldwest-ai-core-build --output-on-failure
```

The AI tests verify unchanged authoritative state during decisions, membership
in the legal action list, deterministic and cached decisions, invariance under
changed opponent hands/hidden punk faces/deck order/secret RNG, immediate lethal
play, defensive Stampede choices, victory before retaliation, Silo handling,
shielding a damaged camp, and a concrete Hard-versus-Normal tactical difference.
They also run 18 complete matches across all three difficulties and both camp
sets. These portable tests complement native solo-menu and cinematic testing.
