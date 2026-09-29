# CLAUDE.md — Lemonade Stand Tycoon

This file is the source of truth for how this codebase is built. Read it fully before writing code.
Every session (including parallel worktrees) must follow these conventions so work merges cleanly.

---

## 1. Project overview

A terminal-based lemonade stand business simulator. The player buys supplies (lemons, sugar, ice, cups),
sets a recipe and a price, then simulates a day of sales. Score = cash on hand. The game ends in bankruptcy
when the player ends a day with no money and not enough inventory to make a single cup.

**Core rules (from the brief — never violate):**
- Decisions (purchases, recipe, price) are locked once the day starts. No changes mid-day.
- If inventory runs out mid-day, sales stop for that day.
- Leftover **ice melts** at end of day. All other resources carry forward (subject to spoilage rules if enabled).
- Bankrupt = end of day, cash is 0 (see assumption A3), and inventory cannot make one cup → game over.

**Goals for this submission:** a large volume of *working* features, clean extensible architecture,
strong tests, polished terminal UI, and a README that explains decisions. Main must always be playable.

---

## 2. Tech stack & commands

- Python **3.11+**
- UI: **Textual** (app/screens/widgets) + **Rich** (tables, panels, sparklines)
- Tests: **pytest**, **hypothesis** (property tests), Textual `Pilot` for UI smoke tests
- Lint/format: **ruff** (lint + format). Type hints everywhere (no mypy gate — time budget).
- Content/config: **TOML** files read with stdlib `tomllib`
- Env/deps: **uv** (`pyproject.toml`)

```bash
uv sync                       # install
uv run lemonade               # play the game (Textual UI)
uv run lemonade --seed 42     # reproducible game
uv run lemonade-sim --games 1000 --strategy greedy   # headless bot / balance report
uv run pytest -q              # all tests
uv run pytest -q tests/engine # engine only
uv run ruff check . && uv run ruff format .
```

Before every commit: `uv run ruff format . && uv run ruff check . && uv run pytest -q` must pass.

---

## 3. Architecture principles (non-negotiable)

1. **Pure engine, thin UI.** `engine/` has zero I/O: no printing, no input, no file access, no Textual imports.
   The UI only calls engine functions and renders returned data. The bot/simulator uses the same engine.
2. **Money is integer cents** (`Cents = int`). Never use floats for money. Format only at the UI layer.
3. **Deterministic randomness.** The engine never calls the global `random`. Every function that needs
   randomness takes an `rng: random.Random`. RNG is derived per day *and per purpose* with
   `rng.day_rng(seed, day, stream)` = `random.Random(f"{seed}:{day}:{stream}")` (streams: `forecast`, `weather`,
   `sales`, `market`, `event:<id>`), so any day of any game is replayable and a new plugin never shifts the
   rolls of existing ones.
4. **Immutable state.** Domain models are `@dataclass(frozen=True, slots=True)`. State transitions return
   new objects (`dataclasses.replace`). This makes tests trivial and enables undo/history.
5. **Extensible by plugins, not by editing the core.** Demand modifiers, events, and upgrades register
   themselves in registries. Adding a feature = adding a new module + a test, *not* editing `simulation.py`.
6. **Content is data.** Item prices, bulk tiers, upgrades, locations, events weights live in `content/*.toml`.
7. **Explainability.** Every modifier produces a human-readable `Effect` with a `reason`. The day report
   shows *why* sales were what they were.

---

## 4. Directory layout

```
src/lemonade/
  __init__.py
  engine/
    __init__.py        # imports plugin packages so registries populate
    types.py           # Cents, Item enum, Weather enum, small value types
    models.py          # GameState, Inventory, Recipe, DayPlan, DayResult, ...
    config.py          # load content/*.toml into typed config objects
    market.py          # supplier prices, bulk pricing, purchase validation
    inventory.py       # add/consume/spoil/melt logic, cups_makeable()
    weather.py         # forecast + actual weather generation
    demand.py          # Effect aggregation, customer buy probability
    simulation.py      # simulate_day(): the ONLY orchestrator of a day
    game.py            # new_game(), start_day(), end_day(), is_bankrupt()
    registry.py        # modifier / event / upgrade registries + decorators
    errors.py          # domain exceptions (InsufficientFunds, InvalidPlan, ...)
    modifiers/         # one file per demand modifier (weather.py, price.py, reputation.py, ...)
    events/            # one file per random/scheduled event
    upgrades/          # upgrade effect handlers
  content/
    items.toml
    upgrades.toml
    events.toml
    locations.toml
  ui/
    app.py             # Textual App, screen routing
    screens/           # plan.py, shop.py, day_result.py, stats.py, upgrades.py, game_over.py, title.py
    widgets/           # inventory_panel.py, forecast_panel.py, cash_chart.py, ...
    format.py          # money/percent formatting helpers
    theme.tcss
  sim/
    strategies.py      # bot strategies (naive, greedy, forecast-aware)
    runner.py          # headless multi-game runner + balance report (lemonade-sim entrypoint)
tests/
  engine/ ui/ sim/ property/
  conftest.py          # shared fixtures: fixed seed, default state, factory helpers
README.md
CLAUDE.md
```

---

## 5. Data model

Sketches below define names and shapes. Keep these names; extend with new optional fields (with defaults)
rather than renaming.

```python
Cents = int

class Item(StrEnum):
    LEMON = "lemon"      # unit: each
    SUGAR = "sugar"      # unit: cup of sugar
    ICE = "ice"          # unit: cube
    CUP = "cup"          # unit: paper cup

class Weather(StrEnum):
    SUNNY = "sunny"; HOT = "hot"; CLOUDY = "cloudy"; RAINY = "rainy"; STORM = "storm"

@dataclass(frozen=True, slots=True)
class Batch:                     # enables spoilage without changing the model later
    qty: int
    expires_on_day: int | None   # None = never expires

@dataclass(frozen=True, slots=True)
class Inventory:
    batches: Mapping[Item, tuple[Batch, ...]]
    def count(self, item: Item) -> int: ...
    # consumption is FIFO by expiry (use oldest first)

@dataclass(frozen=True, slots=True)
class Recipe:                    # per pitcher; one pitcher = CUPS_PER_PITCHER (12) cups
    lemons_per_pitcher: int = 6
    sugar_per_pitcher: int = 4
    ice_per_cup: int = 3

@dataclass(frozen=True, slots=True)
class Purchase:
    item: Item
    packs: int                   # buy in packs defined in items.toml (tiers per pack size)

@dataclass(frozen=True, slots=True)
class DayPlan:
    purchases: tuple[Purchase, ...]
    recipe: Recipe
    price_per_cup: Cents
    location_id: str = "park"
    upgrade_purchases: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class Forecast:
    predicted: Weather
    predicted_temp_f: int

@dataclass(frozen=True, slots=True)
class Effect:
    factor: Factor               # TRAFFIC | PRICE_TOLERANCE | TASTE | BUY_PROB
    op: Literal["mul", "add"]
    value: float
    reason: str                  # "Heat wave: +40% foot traffic"
    source: str                  # modifier/event/upgrade id

@dataclass(frozen=True, slots=True)
class DayResult:
    day: int
    weather: Weather
    temp_f: int
    potential_customers: int
    cups_sold: int
    lost_sales: dict[LossReason, int]   # TOO_EXPENSIVE, BAD_TASTE, SOLD_OUT, NOT_INTERESTED
    stop_reason: StopReason | None      # SOLD_OUT_CUPS / SOLD_OUT_LEMONS / ... / None
    revenue: Cents
    spend: Cents                         # supplies + upgrades + fees
    profit: Cents
    ice_melted: int
    spoiled: dict[Item, int]
    effects: tuple[Effect, ...]          # the explanation breakdown
    events: tuple[str, ...]              # event messages that fired
    reputation_delta: float
    feedback: tuple[str, ...]            # customer comments: "Too sour!", "Needs ice!"

@dataclass(frozen=True, slots=True)
class GameState:
    seed: int
    day: int
    cash: Cents
    inventory: Inventory
    reputation: float                    # 0.0..1.0, starts 0.3
    upgrades: frozenset[str]
    forecast: Forecast                   # for the upcoming day
    history: tuple[DayResult, ...]
    loan: Loan | None = None
    achievements: frozenset[str] = frozenset()
    status: GameStatus = GameStatus.PLAYING   # PLAYING | BANKRUPT | WON
    difficulty: str = "normal"
```

---

## 6. The day pipeline (`simulation.simulate_day`)

`simulate_day(state: GameState, plan: DayPlan, cfg: Config) -> tuple[GameState, DayResult]`

Steps, in order. Each step is a small pure function in its own module; `simulate_day` only orchestrates.

1. **Validate plan** (`market.validate_plan`). Raise `InvalidPlan` / `InsufficientFunds` with clear messages.
2. **Apply purchases** — deduct cash, add inventory batches (with expiry for lemons).
3. **Apply upgrade purchases.**
4. **Resolve actual weather** from the forecast (+ noise), via `weather.resolve(forecast, rng)`.
5. **Fire start-of-day events** (`on_day_start` hooks) → may add effects or alter the day (e.g. storm closes stand).
6. **Collect effects** from every registered modifier, active upgrade, and fired event.
7. **Compute demand**: `potential_customers` from TRAFFIC effects; per-customer buy probability from
   PRICE_TOLERANCE, TASTE, BUY_PROB effects.
8. **Sell loop**: iterate customers one at a time. For each: roll buy/no-buy (record loss reason); if buying,
   make a pitcher if needed (consume lemons+sugar), consume ice+cup. If we can't serve → stop, record `stop_reason`.
   (Per-customer loop is intentional: it naturally models selling out mid-day and gives loss-reason stats.)
9. **Fire end-of-day events** (`on_day_end` hooks).
10. **End-of-day upkeep**: melt ice (minus cooler retention), spoil expired batches, loan interest, fees.
11. **Update reputation** from taste score and price fairness.
12. **Check achievements, bankruptcy, win condition.** Generate next day's forecast.
13. Return new state + `DayResult`.

---

## 7. Demand model (keep simple, keep documented)

```
traffic        = base_traffic[location] * Π(TRAFFIC mul) + Σ(TRAFFIC add)
fair_price     = base_fair_price * Π(PRICE_TOLERANCE mul)
price_factor   = clamp(1 - (price - fair_price) / fair_price, 0, 1.2)
taste          = recipe_score(recipe, temp_f)  in [0,1]  (+ TASTE adds)
buy_prob       = clamp(0.1 + 0.8 * price_factor * taste * (0.5 + reputation), 0, 0.95) * Π(BUY_PROB mul)
customer buys  = rng.random() < buy_prob
```

- `recipe_score`: distance from an "ideal" recipe; ideal ice goes up with temperature. Returns feedback strings.
- All constants live in `content/items.toml` under `[demand]` so balancing never touches code.
- The README must document every constant and how to tune it (and the `lemonade-sim` balance report).
- **Timebox:** do not spend time making this realistic. Correct, deterministic, explainable > realistic.

---

## 8. Plugin contracts

```python
# registry.py
MODIFIERS: dict[str, Modifier] = {}
EVENTS: dict[str, GameEvent] = {}
UPGRADE_HANDLERS: dict[str, UpgradeHandler] = {}

def register_modifier(cls): ...     # decorator; keys by cls.id
def register_event(cls): ...
def register_upgrade(cls): ...

class Modifier(Protocol):
    id: str
    def effects(self, ctx: DayContext) -> list[Effect]: ...

class GameEvent(Protocol):
    id: str
    def chance(self, ctx: DayContext) -> float: ...              # 0..1, may depend on day/weather
    def on_day_start(self, ctx: DayContext) -> EventOutcome: ...  # effects + message + optional state patch
    def on_day_end(self, ctx: DayContext, result: DayResult) -> EventOutcome: ...

class UpgradeHandler(Protocol):
    id: str                                  # must match an entry in upgrades.toml
    def effects(self, ctx: DayContext) -> list[Effect]: ...
    def ice_retention(self) -> float: return 0.0
    def lemon_yield_bonus(self) -> float: return 0.0
```

`DayContext` is a frozen, read-only bundle: state, plan, weather, temp, day-of-week, holiday, rng, cfg.

**To add a feature:** create `engine/modifiers/<name>.py` (or events/upgrades), decorate with the register
decorator, import it in that package's `__init__.py`, add TOML content if needed, add tests. Do **not** edit
`simulation.py` unless a new pipeline hook is genuinely needed — if so, note it in the PR/commit message.

---

## 9. Content defaults (`content/*.toml`)

- Starting cash: **$20.00** (2000 cents). Starting inventory: empty.
- Items (pack size, base price per pack, bulk tiers):
  - Lemons: pack of 12, $4.00; 3+ packs −10%, 6+ packs −20%. Expire after **5 days**.
  - Sugar: pack of 8 cups, $3.00; bulk tiers similar. No expiry.
  - Ice: bag of 100 cubes, $1.50. Melts end of day.
  - Cups: pack of 50, $2.50. No expiry.
- Supplier prices fluctuate ±15% daily (seeded) when the "market fluctuation" feature is on.
- Locations: park (default), beach (high traffic when hot, higher rent), downtown (high price tolerance, rent).
- Upgrades: cooler (keep 50% ice), juicer (+25% lemon yield), sign (+15% traffic),
  umbrella (rain penalty halved), helper (+20% max customers served), second stand.

---

## 10. UI (Textual)

Screens (4 total — keep it tight):
- **Plan** (main hub) — header: day, cash, reputation. Left: inventory panel + forecast panel.
  Right: `TabbedContent` with tabs **Shop** (pack purchases, bulk-tier display, running total, blocks overspending),
  **Recipe** (lemons/sugar/ice inputs + taste hint), **Price**, **Upgrades** (cost, owned, description).
  Footer: live "cups makeable" + cart total. Keys: `enter` start day, `t` stats, `?` help, `q` quit.
- **Day result** — revenue, spend, profit, stop reason, loss-reason breakdown, **effects breakdown table**
  (reason → impact), events, customer feedback, melted/spoiled summary. `enter` → next day.
- **Stats** — cash-over-time sparkline, best/worst day, totals, achievements.
- **Game over** — final score, days survived, summary. `n` new game.
- Stretch only: title screen, save/load UX, high scores, animated sales tick-up.

Rules:
- UI never computes game logic. If the UI needs a number (e.g. "cups makeable"), add an engine function.
- All money formatting via `ui/format.py` (`fmt_cents(1234) -> "$12.34"`).
- Errors from the engine (`InsufficientFunds`, etc.) surface as Textual notifications, never crashes.
- Styles in `theme.tcss`; lemon-yellow accent color.

---

## 11. Testing rules

- Every engine module has tests in `tests/engine/test_<module>.py`. Every new plugin gets at least one test.
- Use `conftest.py` factories (`make_state(...)`, `make_plan(...)`, `fixed_rng()`) — don't hand-build state.
- **Required invariant/property tests** (`tests/property/`, hypothesis):
  - Cash never goes negative.
  - `cups_sold <= cups makeable from start-of-day inventory + purchases`.
  - Inventory conservation: start + bought = used + remaining + melted + spoiled.
  - Same seed + same plans ⇒ identical results (determinism).
  - Ice count is 0 at end of day (unless cooler owned).
- **Required edge-case tests**: bankruptcy (cash 0 + can't make a cup ⇒ bankrupt; cash 0 but can make cups ⇒
  not bankrupt), selling out mid-day sets `stop_reason`, invalid plan rejected, spoilage uses FIFO.
- UI: one Pilot smoke test per screen (mounts without error, key bindings work) + one full-day flow test.
- Sim: bot runs 100 seeded games without exceptions.
- Tests must be fast (< 10s total). No sleeping, no real time.

---

## 12. Code conventions

- Type hints on every function. No `Any` in engine code unless unavoidable.
- Small functions (< ~40 lines). Pure where possible.
- Names: modules `snake_case`, classes `PascalCase`, plugin ids `snake_case` strings.
- Docstrings on public engine functions: one line on what, plus notes on invariants.
- No global mutable state except the registries.
- No new dependencies without noting them in the README.
- Commits: small and frequent, conventional style — `feat(engine): lemon spoilage`, `test(property): ...`,
  `feat(ui): day result screen`, `docs: ...`. One feature per commit where possible.

---

## 13. Assumptions (record new ones here AND in README)

- A1. One pitcher = 12 cups. Pitchers are made on demand during the day.
- A2. Supplies are bought in packs, not single units.
- A3. Bankruptcy is checked at end of day: `cash == 0` (or less than the cheapest pack needed to complete one cup)
  **and** current inventory cannot make one cup. Implemented as `cash < market.cost_to_make_one_cup(...)`: the
  cost, at today's prices, of the packs missing for a *minimal* cup (1 lemon + 1 paper cup; sugar and ice are
  optional in a recipe), so melted ice alone never bankrupts a player.
- A4. Purchases happen at the start of the day before selling; there is no mid-day restocking.
- A5. Weather forecast accuracy is ~70%; actual weather may shift one step from the forecast.
- A6. Game length is unlimited by default; "Challenge mode" is 30 days with a target cash goal (not built yet).
- A7. Lemonade left in a partly sold pitcher at close is discarded; its lemons and sugar count as used.
- A8. Every plan cost (supplies, upgrades, rent) is paid up front, so cash never goes negative. Event cash
  changes (the inspector's fine) apply at end of day and are clamped at $0.
- A9. Lemons are usable on the purchase day plus 4 more days (`expires_on_day = day + 5 - 1`) and spoil at the
  end of their last day. Stock is always used oldest-expiry first (FIFO).
- A10. A non-buyer is blamed on the weakest factor: price (price factor < 0.5), then taste (< 0.5), else "not
  interested". After a sell-out, customers keep arriving and would-be buyers count as "sold out".
- A11. Supplier prices (±15% daily fluctuation, lemon shortage, difficulty markup) are known before buying.
  A lemon shortage is therefore a market condition, not an `EVENTS` plugin (events fire after purchases).
- A12. The juicer lowers lemons used per pitcher (`ceil(lemons / 1.25)`); taste is still judged on the
  player's recipe. An upgrade bought today works today.
- A13. Day 1 is a Monday; Saturday and Sunday are busier. Holidays are fixed game days (4, 12, 21, 30) and
  don't repeat.
- A14. Normal difficulty is tuned with `lemonade-sim` so a forecast-aware player roughly 8x's the starting cash
  in 30 days, a weather-blind one about 3.7x, and hard can bankrupt all strategies (see README "Balance").
- A15. Textual never fires letter shortcuts while a text input has focus, so the Plan screen starts focused on
  the Start button and `ctrl+q` always quits.

---

## 14. Build phases & parallel lanes

### Timeline (3h hard budget)
| Clock | Phase |
|---|---|
| 0:00–0:10 | Repo + tooling setup |
| 0:10–1:00 | **Phase 0 — Skeleton** (sequential, single session). Merge to main before parallel work. |
| 1:00–2:15 | **Phase 1 — Two parallel lanes** (git worktrees), merge to main every ~20 min |
| 2:15–2:40 | **Phase 2 — Tier 2 features** on main |
| 2:40–3:00 | **Hard stop:** README, full test run, demo rehearsal. No new features after 2:40. |

### Phase 0 — Skeleton
`types`, `models`, `config` + TOML, `inventory`, `market`, `weather`, `demand`, `simulation`, `game`,
`registry` with **one** example modifier (weather), **one** example event (heat wave), **one** example upgrade
(cooler), conftest factories + core tests, minimal Plan → Day result UI loop.

### Phase 1 — Two lanes. Stay inside your lane's files.

| Lane | Owns | Features |
|---|---|---|
| **ENGINE** | `engine/**` (except shared-file rules), `content/**`, `tests/engine`, `tests/property` | bulk tiers, price fluctuation, spoilage, upgrades, reputation, day-of-week, events, property tests |
| **UI+TOOLS** | `ui/**`, `sim/**`, `tests/ui`, `tests/sim` | Plan tabs, Day result, Stats, Game over, bot strategies, balance report |

Shared files (`models.py`, `simulation.py`, `registry.py`): only additive changes (new optional fields with
defaults). Merge to main frequently and rebase the other lane.

**Ownership exceptions:** `engine/stats.py` (derived history stats) and `[project.scripts]` in
`pyproject.toml` belong to UI+TOOLS. Everything else under `engine/` belongs to ENGINE.

**Cross-lane contracts (already on main):** the UI shows prices via `market.todays_pack_prices`, bulk
discounts via `market.discount_pct` / `purchase_cost`, price notes via `market.market_notes`, the cart via
`game.preview_plan`, and cash over time via `DayResult.cash_end` / `stats.cash_series`. Never read
`cfg.items[...].pack_price` directly in the UI (prices will fluctuate).

**Merge rules:**
1. Every ~20 min: rebase on `main`, run the full pre-commit check, fast-forward merge to `main`, push;
   the other lane then rebases.
2. If both lanes are ready at once, ENGINE merges first.
3. `README.md` and the section 15 checklist are edited only on `main` after a merge, never in a lane.
4. Shared files (`models.py`, `simulation.py`, `registry.py`, `pyproject.toml`) are additive only; any
   `simulation.py` change is called out in the commit message.
5. After each merge, `uv run lemonade --seed 42` must still launch.
6. Commits: short one-line conventional messages, authored by the repo owner, no co-author trailer.

---

## 15. Feature checklist (update status as you go)

**Tier 1 — must ship (by 2:15)**
- [x] Core loop: buy → recipe → price → simulate → report
- [x] Ice melts; other items carry over
- [x] Bankruptcy / game over
- [x] Weather forecast vs actual
- [x] Tweakable recipe + taste score + customer feedback
- [x] Effects breakdown ("why did I sell this much?")
- [x] Bulk pricing tiers
- [x] Lemon spoilage (FIFO)
- [x] Reputation
- [x] Upgrades: cooler, juicer, sign, umbrella
- [x] Events: heat wave, storm, inspector, lemon shortage, festival
- [x] Plan (tabs), Day result, Game over screens
- [x] Core + property tests, UI smoke tests

**Tier 2 — next (until 2:40)**
- [x] Daily supplier price fluctuation
- [x] Day-of-week + holidays
- [x] Stats screen with cash chart
- [x] Achievements
- [x] Difficulty levels
- [x] Headless bot strategies + balance report

**Tier 3 — stretch (only if ahead of schedule; otherwise list as TODO in README)**
- [ ] Loans with interest
- [ ] Locations with rent; second stand; helper
- [ ] Competitor, viral post events; word of mouth
- [ ] Save / load (JSON), high scores, title screen
- [ ] Challenge mode (30 days, target)

- [x] README complete (not optional — starts at 2:40)

---

## 16. Definition of done (per feature)

1. Implemented as a plugin/module following the contracts above.
2. Tests added and passing; full suite green; ruff clean.
3. Visible in the UI (or explicitly engine-only and noted).
4. Content in TOML, not hard-coded constants.
5. Checklist updated; README section updated if it adds a mechanic or assumption.
6. Committed with a conventional commit message.

## 17. Don'ts

- Don't put game logic in the UI.
- Don't use floats for money or global `random`.
- Don't tune the demand model beyond "reasonable" — write a TODO in the README instead.
- Don't leave main broken. If a feature isn't working at the time limit, disable it via config and note it.
- Don't rename existing model fields; add new ones with defaults.
