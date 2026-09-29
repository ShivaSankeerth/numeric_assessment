# Core abstractions

This covers the seven abstractions the codebase is built on. Each section gives:

- what it is, with a short excerpt of the real code;
- the problem it solves;
- the alternatives that were considered;
- where it would strain at a larger scale.

The last section follows one real feature, the **Sign** upgrade, through all seven.

About **"Alternatives considered"**: this only lists alternatives that were actually weighed and
written down, in CLAUDE.md, the Phase 0 plan decisions (D1–D21), the Phase 1 lane plan or a
commit. Where nothing was recorded, the section says so and lists options as *not considered at
the time*.

---

## 1. The engine/UI boundary

**What it is.** `engine/` is pure game logic, with no printing, input, file access or Textual
imports (the one exception is `config.load_config`, see §7). The UI holds the current
`GameState`, calls engine functions, and renders what they return. Anything that happens in the
game goes through one entry point, `game.play_day`. The engine reports errors as exceptions, and
the UI turns them into notifications:

```python
# src/lemonade/ui/app.py
def start_day(self, plan: DayPlan) -> None:
    """Play the day via the engine; engine errors become notifications, never crashes."""
    notes = market.market_notes(self.state, self.cfg)
    try:
        self.state, result = game.play_day(self.state, plan, self.cfg)
    except LemonadeError as err:
        self.notify(str(err), title="Can't start the day", severity="error")
        return
    self.push_screen(DayResultScreen(result, self.state, notes))
```

Even the live numbers on the Plan screen come from the engine. `game.preview_plan` exists only so
the UI never has to work out a cost or a cup count itself:

```python
# src/lemonade/ui/screens/plan.py
preview = preview_plan(self.lemonade.state, plan, self.lemonade.cfg)
self._refresh_taste(plan)
over = preview.cash_after < 0
```

**Problem it solves.**
- Game rules live in exactly one place.
- The headless bots in `sim/` run the *same* engine as the player, so the balance report measures
  the real game.
- Engine tests never have to start Textual.
- The UI and bot lanes could be built in parallel with the engine, with almost no shared files.

**Alternatives considered.**
- *The UI computes small numbers itself, e.g. cups makeable.* CLAUDE.md §10 rules this out ("If
  the UI needs a number, add an engine function"). That rule is why `preview_plan` (Phase 0,
  step 4) and `engine/stats.py` (Phase 1 kickoff) exist.
- *Where the TOML is read* (decision D1). The engine was supposed to do no file access, yet
  CLAUDE.md put the loader in `engine/config.py`. The compromise is a pure `parse_config` plus one
  documented file-reading function.

**Where it would strain.**
- **A wide boundary.** The UI imports many engine modules directly: `market`, `demand`, `dates`,
  `stats`, `game`. It isn't a narrow API, so any engine refactor ripples into the UI. The UI also
  uses `getattr` fallbacks for engine features that might not exist yet (added during Phase 1).
  That's a sign the contract is informal.
- **Everything runs on the UI thread.** `preview_plan` re-runs on every keystroke, and `play_day`
  blocks the UI while it runs. At today's sizes (60 customers a day) it's instant. A bigger
  simulation would need a worker thread or incremental results.
- **The UI owns the state.** Save/load, undo, or a second front end (web, API) would each need a
  small application layer holding `GameState` and the config, rather than the Textual `App`.

## 2. GameState immutability

**What it is.** Every domain model is a `@dataclass(frozen=True, slots=True)`. A day never changes
the state; it returns a *new* `GameState` built with `dataclasses.replace`:

```python
# src/lemonade/engine/simulation.py
def _advance(
    state: GameState, cfg: Config, cash: Cents, inv: Inventory, result: DayResult
) -> GameState:
    """Move to the next morning: new cash, stock, reputation, forecast and history."""
    next_day = state.day + 1
    return replace(
        state,
        day=next_day,
        cash=cash,
        inventory=inv,
        reputation=max(0.0, min(1.0, state.reputation + result.reputation_delta)),
        forecast=weather.generate_forecast(day_rng(state.seed, next_day, "forecast"), cfg),
        history=(*state.history, result),
    )
```

**Problem it solves.**
- **Safe failure:** an invalid plan raises before anything changes, and the caller still holds the
  untouched old state. A test checks this (`test_invalid_plan_rejected_and_state_untouched`).
- **Easy invariants:** the property tests compare the "before" and "after" states of every day
  (cash ≥ 0, stock conserved). They only work because "before" can't be modified by accident.
- **Free history:** `history` is the full record of every day, which the Stats screen and the
  balance report both read.

**Alternatives considered.**
- Immutability itself was a CLAUDE.md §3 principle, not debated.
- *Dict fields inside frozen dataclasses* (decision D10). `Inventory.batches` and
  `DayResult.lost_sales` are plain dicts, kept read-only by convention (every change builds a new
  dict), rather than truly immutable mapping types. The cost: `GameState` can't be hashed, and
  nothing stops a mutation except discipline.

**Where it would strain.**
- **History copying grows with game length.** `history=(*state.history, result)` copies the whole
  tuple every day, so a long game does work that grows with the square of its length. That's
  trivial for 30 days but not for 10,000. A persistent list, or keeping history outside
  `GameState`, would fix it.
- **Every `DayResult` keeps its full effect list and several dicts**, so memory grows with game
  length times plugin count.
- **"Frozen" is shallow.** The dict fields can still be mutated. A bug that mutates one would
  silently corrupt history, and the type system wouldn't catch it.

## 3. The Effect and modifier pipeline

**What it is.** Everything that changes demand does it the same way: by returning `Effect`s. An
effect targets one factor (TRAFFIC, PRICE_TOLERANCE, TASTE or BUY_PROB) with a multiplier or an
addition, and carries a human-readable reason:

```python
# src/lemonade/engine/models.py
@dataclass(frozen=True, slots=True)
class Effect:
    factor: Factor
    op: Literal["mul", "add"]
    value: float
    reason: str  # "Heat wave: +40% foot traffic"
    source: str  # modifier/event/upgrade id
```

The demand model folds them together per factor, in any order:

```python
# src/lemonade/engine/demand.py
def combine(effects: Iterable[Effect], factor: Factor) -> tuple[float, float]:
    """(product of 'mul' values, sum of 'add' values) for one factor."""
    mul, add = 1.0, 0.0
    for e in effects:
        if e.factor is not factor:
            continue
        if e.op == "mul":
            mul *= e.value
        else:
            add += e.value
    return mul, add
```

**Problem it solves.**
- **Explainability** (CLAUDE.md principle 7). The day report's "Why?" table is simply the day's
  effects, sorted by `stats.ranked_effects`.
- **Composition.** Weather, weekends, holidays, difficulty, the sign and the heat wave all combine
  with no code knowing about the others.
- **Order independence.** Multiplication and addition don't care about order, so plugin load order
  can't change the result.

**Alternatives considered.**
- The multiply/add model and the four factors come from the CLAUDE.md §7 formula.
- *How lost sales are attributed* (decision D11): blame the weakest factor, rather than splitting a
  lost customer across several reasons.
- No other effect design (priorities, per-customer effects, arbitrary functions) is recorded as
  considered.

**Where it would strain.** These are already visible in the repo:
- **Anything that isn't a demand multiplier needs a new pipeline hook.**
  - The *juicer* changes how many lemons a pitcher uses. It couldn't be an Effect, so it needed
    `recipes.effective_recipe` plus edits to `simulation.py`, `game.py` and the property test
    (commit `9809d07`).
  - The *storm* closes the stand, and the *inspector* fines you. Both are special fields on
    `EventOutcome` (`close_stand`, `cash_delta`), each handled by hand in `simulate_day`.
  - Every new *kind* of consequence adds another such field.
- **Effects can't see each other.** The *umbrella* has to recompute the weather penalty from the
  weather config to "halve" it. That quietly couples it to how the weather plugin works.
- **One mul/add pair per factor, for the whole day.** Nothing can vary by customer (e.g. price
  sensitivity per customer) or over the day (a lunchtime rush).
- **Reasons are English strings baked in at creation.** There's no localisation, and the UI can't
  re-render an effect differently.

## 4. The plugin registry

**What it is.** Modifiers, events and upgrade handlers register themselves with a class
decorator. The decorator stores one stateless instance per id and rejects duplicate ids:

```python
# src/lemonade/engine/registry.py
MODIFIERS: dict[str, Modifier] = {}
EVENTS: dict[str, GameEvent] = {}
UPGRADE_HANDLERS: dict[str, UpgradeHandler] = {}

def _register(registry: dict, cls: T) -> T:
    plugin_id = getattr(cls, "id", None)
    if not isinstance(plugin_id, str) or not plugin_id:
        raise ValueError(f"{cls.__name__} must define a non-empty string `id`")
    if plugin_id in registry:
        raise ValueError(f"duplicate plugin id '{plugin_id}' ({cls.__name__})")
    registry[plugin_id] = cls()
    return cls
```

Registration happens at import time, because each package's `__init__.py` imports its plugins.
The pipeline then walks the registries in sorted id order:

```python
# src/lemonade/engine/simulation.py
def _collect_effects(ctx: DayContext, start_effects: list[Effect]) -> tuple[Effect, ...]:
    effects: list[Effect] = []
    for modifier_id in sorted(MODIFIERS):
        effects.extend(MODIFIERS[modifier_id].effects(ctx))
    for handler in active_upgrades(ctx.state):
        effects.extend(handler.effects(ctx))
    return (*effects, *start_effects)
```

**Problem it solves.**
- Adding a feature means adding a module, not editing the core (CLAUDE.md principle 5).
- In Phase 1, the ENGINE lane added 3 upgrades, 3 events and 3 modifiers. That growth never
  touched the registry, and it never conflicted with the UI lane.
- Plugins hold no state; they read their parameters from `ctx.cfg`, so tuning a plugin is a TOML
  change.

**Alternatives considered.**
- *Class-level default methods* (decision D8). Protocols can't supply default methods, so
  `BaseEvent` and `BaseUpgrade` exist to provide them, and the Protocols are kept for type
  checking.
- *Store the class or an instance* (decision D9). An instance is stored, and duplicate ids are
  rejected.
- *Explicit wiring*: listing plugins in `simulation.py` was rejected by CLAUDE.md §8.

**Where it would strain.**
- **Global mutable state.** The registries are module-level dicts, the only global state
  CLAUDE.md allows. One process can't run two games with different plugin sets (e.g. a mod
  enabled in one game only), and tests that add plugins have to monkeypatch the globals.
- **Import-time side effects.** Forget the import in `__init__.py` and the plugin silently never
  runs. Only upgrades are checked against content (`test_every_upgrade_in_content_has_a_handler_and_vice_versa`);
  events and modifiers aren't.
- **Every plugin is consulted every day.** `_collect_effects` calls every modifier and
  `_fire_start_events` rolls every event, whether or not they can apply. That's fine for 10 or so
  plugins. Hundreds would want indexing by when they can fire.
- **No dependencies or ordering between plugins.** The umbrella's reliance on the weather config
  (§3) is exactly the kind of link a larger system would need to declare.

## 5. Batch-based inventory

**What it is.** Stock is a tuple of `Batch`es per item, each with a quantity and a last usable day,
kept sorted so the oldest is used first:

```python
# src/lemonade/engine/models.py
@dataclass(frozen=True, slots=True)
class Batch:
    """A quantity of one item sharing an expiry day (None = never expires)."""

    qty: int
    expires_on_day: int | None  # last day the batch is usable
```

Use and spoilage both work on batches:

```python
# src/lemonade/engine/inventory.py
def consume(inv: Inventory, item: Item, qty: int) -> Inventory:
    """Remove `qty` units, oldest expiry first. Raises ValueError if there is not enough."""
    ...
    remaining = qty
    kept: list[Batch] = []
    for b in inv.batches.get(item, ()):
        take = min(b.qty, remaining)
        remaining -= take
        if b.qty > take:
            kept.append(Batch(b.qty - take, b.expires_on_day))
    return _with_batches(inv, item, tuple(kept))
```

**Problem it solves.**
- **Spoilage and oldest-first use without special cases.** CLAUDE.md §5 chose batches upfront
  ("enables spoilage without changing the model later"). Lemon spoilage then landed in Phase 0
  with no model change.
- **Required tests are easy to write.** "Spoilage uses FIFO" and stock conservation (start + bought
  = used + remaining + melted + spoiled) are simple to state over batches.
- **One shape for every item.** The same representation works for items that never expire (sugar,
  cups) and for ice, which melts in `melt()` rather than expiring.

**Alternatives considered.**
- *Plain counts per item* is the alternative CLAUDE.md §5 implicitly rejected. It still shows up
  as an internal optimisation: commit `d55599b` changed the sell loop to track plain counters
  during the day and write the batches back once at the end, because rebuilding batch tuples for
  every cup was too slow.

**Where it would strain.**
- **Performance already strained once.** `Inventory.count()` walks every batch, and `consume()`
  rebuilds tuples. The per-cup cost is why the sell loop now uses counters (`d55599b`). Anything
  else that uses stock often would need the same trick.
- **Expiry is the only attribute.** Quality, freshness-dependent taste, or a supplier per batch
  would need a richer `Batch`, and changes to every function that splits or merges batches.
- **Stock is global.** There's one inventory per game. Multiple stands or locations (a cut Tier 3
  feature) would need inventory per location, plus transfer rules.

## 6. Per-day seeded RNG streams

**What it is.** Nothing uses the global `random`. Every random decision draws from a fresh RNG seeded
by the game seed, the day and a *stream name*:

```python
# src/lemonade/engine/rng.py
def day_rng(seed: int, day: int, stream: str) -> random.Random:
    """Return a fresh RNG for one purpose on one day of one game.

    Streams isolate consumers (e.g. "weather", "sales", "event:heat_wave") so that adding a new
    plugin never shifts the random draws of existing ones. String seeding is stable across runs
    (it does not depend on PYTHONHASHSEED).
    """
    return random.Random(f"{seed}:{day}:{stream}")
```

Each event gets its own stream, so events can't affect each other:

```python
# src/lemonade/engine/simulation.py
for event_id in sorted(EVENTS):
    event = EVENTS[event_id]
    event_ctx = replace(ctx, rng=day_rng(ctx.state.seed, ctx.state.day, f"event:{event_id}"))
    if event_ctx.rng.random() < event.chance(event_ctx):
        fired.append(_FiredEvent(event, event_ctx))
```

**Problem it solves.**
- **Replayable games.** `--seed 42` gives the same game on any machine, and the property test
  "same seed and plans give identical results" relies on it.
- **Any day can be recomputed on its own.** The market works out a day's prices from
  `(seed, day, "market")` whenever it's asked, so nothing needs to store them.
- **Balance reports stay comparable across branches.** Adding the festival event in Phase 1
  didn't change a single weather or sales roll.

**Alternatives considered.**
- *One RNG per day*, `random.Random(f"{seed}:{day}")`, as CLAUDE.md §3 originally said. Decision D4
  rejected it: with one shared stream, any plugin that draws a number shifts every later draw
  that day. CLAUDE.md §3 was updated to match.

**Where it would strain.**
- **Order within a stream still matters.** The market has to roll the shortage *before* the price
  swings ("so toggling fluctuation never changes whether a shortage hits"). The sell loop rolls
  for every customer even after a sell-out, so the number of draws doesn't depend on stock.
  Changing either loop changes every downstream result for that stream.
- **Streams are named by free-form strings.** A typo or a name clash would silently share or split
  randomness.
- **RNGs are created constantly.** `market_day` builds a new RNG on every call, and it's called on
  every keystroke via `preview_plan`. Cheap now, but it's per-call overhead that caching would
  remove at scale.
- **Reproducibility depends on Python's `random` staying the same.** Seeding with a string is stable
  in current Python 3, but it's not something to promise for saved games across interpreter
  versions.

## 7. TOML content

**What it is.** Every price, chance, multiplier, threshold and piece of text for the player lives in
`src/lemonade/content/*.toml` (game, items, upgrades, events, locations, achievements). It's
parsed once into typed, validated, frozen config objects:

```python
# src/lemonade/engine/config.py
def read_raw_content(content_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    """Read every content TOML into plain dicts (the one sanctioned file read)."""
    base = content_dir or resources.files("lemonade") / "content"
    raw: dict[str, dict[str, Any]] = {}
    for name in CONTENT_FILES:
        raw[name] = tomllib.loads((base / f"{name}.toml").read_text(encoding="utf-8"))
    return raw


def load_config(content_dir: Path | None = None) -> Config:
    """Load and validate the game content. Defaults to the packaged `lemonade/content`."""
    return parse_config(read_raw_content(content_dir))
```

```toml
# src/lemonade/content/upgrades.toml
[sign]
name = "Sign"
cost = 800
description = "A bright sign that draws 15% more foot traffic."
traffic_mul = 1.15
```

**Problem it solves.**
- **Balancing is a data change** (CLAUDE.md principle 6). The whole balance pass (`49a7d06`)
  changed only `locations.toml` and `game.toml`, plus tests that had hard-coded those values.
- **Bad content fails at load time.** A missing key or negative price raises `ConfigError` at
  startup with its path, e.g. `missing key 'items.lemon.pack_price'`.
- **The UI builds itself from content.** It lists upgrades, difficulties and achievements from
  config, so new content appears in the UI without UI code (see the walkthrough below).

**Alternatives considered.**
- *TOML with the standard library's `tomllib`* was the CLAUDE.md §2 choice. No other format is
  recorded as considered.
- *Where TOML is read* (decision D1, see §1).
- *A new content file versus sticking to the four listed* (decision D15). `game.toml` was added for
  the rules and weather; `achievements.toml` came later in Phase 1.

**Where it would strain.**
- **Plugin parameters are untyped.** `params` is a `dict[str, float]` of whatever extra keys the
  TOML table has, so `params["traffic_mul"]` spelled wrong fails with a `KeyError` mid-game, not at
  load time. Only the core sections get field-by-field validation.
- **The hand-written parser grows with the content.** `config.py` is about 420 lines. Every new
  content file or section means new parsing code. A schema library would shrink it, at the cost of
  a dependency.
- **Tests depend on content values.** Balancing broke three tests that hard-coded difficulty
  numbers, and `tests/factories.py` has to turn off price swings and achievements to keep test
  numbers stable. More content means more of these couplings.
- **No versioning or overrides.** There's one content set shipped inside the package. Mods,
  difficulty packs or A/B balance tests would need layered content directories and a version
  field.

---

## How a new feature flows through these: the Sign upgrade

The **Sign** ("+15% foot traffic", $8) came in with commit `9809d07`
(`feat(engine): sign, umbrella and juicer upgrades`). This is its full path, and nothing in the
engine core or the UI had to change for it.

1. **Content (§7).** A `[sign]` table goes in `upgrades.toml`: name, cost 800, description,
   `traffic_mul = 1.15`. `parse_config` turns it into
   `UpgradeConfig(name="Sign", cost=800, params={"traffic_mul": 1.15})`.
2. **Plugin and registry (§4).** The whole implementation is one module, registered on import
   through `upgrades/__init__.py`:

   ```python
   # src/lemonade/engine/upgrades/sign.py
   @register_upgrade
   class Sign(BaseUpgrade):
       id = "sign"

       def effects(self, ctx: DayContext) -> list[Effect]:
           mul = ctx.cfg.upgrades[self.id].params["traffic_mul"]
           return [Effect(Factor.TRAFFIC, "mul", mul, f"Sign: {fmt_mul(mul)} foot traffic", self.id)]
   ```

3. **UI, for free (§1).** The Upgrades tab builds itself from `cfg.upgrades`, so the Sign shows up
   as "Sign — $8.00" with a checkbox, with no UI code:

   ```python
   # src/lemonade/ui/screens/plan.py
   for up_id, up in cfg.upgrades.items():
       owned = up_id in self.lemonade.state.upgrades
       yield Checkbox(
           upgrade_label(up_id, cfg, owned),
           value=False,
           id=f"upgrade-{up_id}",
           disabled=owned,
           compact=True,
       )
   ```

   Ticking the box puts `"sign"` into `DayPlan.upgrade_purchases`. The cart total comes from
   `preview_plan`, which already includes upgrade costs.
4. **Buying it (§2).** `market.validate_plan` checks the Sign exists, isn't already owned and is
   affordable. `market.apply_purchases` then returns a *new* state with the cost deducted and
   `upgrades | {"sign"}`. If validation fails, nothing has changed.
5. **Effect pipeline (§3).**
   - From that day on, `_collect_effects` finds the Sign through `active_upgrades(state)`, and it
     contributes `Effect(TRAFFIC, "mul", 1.15, "Sign: +15% foot traffic", "sign")`.
   - `demand.traffic` folds it into the day's other traffic effects (weather, weekend, holiday,
     difficulty). Order doesn't matter.
6. **Inventory (§5).** The extra customers are served by the sell loop, which draws down stock
   using counters and writes the batches back oldest-first at the end of the day.
7. **RNG (§6).** The Sign uses no randomness, so adding it didn't shift any random draw. Games with
   the same seed still get the same weather, events and customer rolls. Only the number of
   customers changes, which is the intended effect.
8. **Explanation (§3).** The effect appears in `DayResult.effects`, and the day report's "Why?"
   table shows "Sign: +15% foot traffic".
9. **Tests.**
   - `tests/engine/plugins/test_sign.py` checks the effect and its reason, and that owning the
     Sign increases customers across a whole simulated day.
   - The registry test confirms the `upgrades.toml` entry has a handler.
   - The property tests' plan generator buys every upgrade, so all the invariants also cover
     games with a Sign (commit `d6dcd4e`).

**The contrast from the same commit.** The **juicer** couldn't follow this path. It changes how
many lemons a pitcher needs, which isn't a demand effect. It needed a new
`recipes.effective_recipe` hook, used in `simulation.py` (flagged in the commit subject as
required by the rules), in `game.preview_plan` and in the property test.

That's the boundary of the Effect abstraction (§3): anything shaped like a demand multiplier is a
single file, and anything else is a pipeline change.
