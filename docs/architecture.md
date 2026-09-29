# Architecture

Three diagrams of the code as it is in `src/`: which components depend on which, how one day runs,
and the core data model. Every node was checked against the source; the table at the end lists the
file behind each one. They were drawn from the code (imports extracted with Python's `ast`, fields
read from the dataclasses), not from CLAUDE.md. Where the code differs from CLAUDE.md, the diagrams
follow the code (see "Where the code differs from CLAUDE.md §6" below).

## 1. Components

Arrows mean "imports and calls at runtime". Imports used only for type hints (`if TYPE_CHECKING:`)
are left out, e.g. the screens' import of `ui.app`. Nearly every module imports `engine.models` and
`engine.types`, so those arrows are omitted too. Other edges are a real subset, not the complete
graph.

```mermaid
flowchart LR
    subgraph UI["ui/ (Textual)"]
        app["ui.app<br/>LemonadeApp, main()"]
        screens["ui.screens<br/>plan, day_result, stats,<br/>help, game_over"]
        fmt["ui.format<br/>fmt_cents, fmt_pct, parse_cents"]
    end

    subgraph SIM["sim/ (headless bots)"]
        runner["sim.runner<br/>run_games(), main()"]
        strategies["sim.strategies<br/>naive, greedy, forecast_aware"]
    end

    subgraph ENGINE["engine/ (pure, no I/O)"]
        game["engine.game<br/>new_game, play_day, end_day,<br/>is_bankrupt, preview_plan"]
        simulation["engine.simulation<br/>simulate_day()"]
        market["engine.market"]
        weather["engine.weather"]
        demand["engine.demand"]
        sales["engine.sales<br/>sell()"]
        inventory["engine.inventory"]
        recipes["engine.recipes<br/>effective_recipe()"]
        dates["engine.dates"]
        achievements["engine.achievements"]
        stats["engine.stats"]
        rng["engine.rng<br/>day_rng()"]
        config["engine.config<br/>parse_config, load_config"]
        foundation["engine.models, engine.types,<br/>engine.errors"]
    end

    subgraph PLUGINS["plugin registry"]
        registry["engine.registry<br/>MODIFIERS, EVENTS,<br/>UPGRADE_HANDLERS"]
        modifiers["engine.modifiers<br/>weather, day_of_week,<br/>holiday, difficulty"]
        events["engine.events<br/>heat_wave, storm,<br/>festival, inspector"]
        upgrades["engine.upgrades<br/>cooler, juicer, sign, umbrella"]
    end

    content[("content/*.toml<br/>game, items, upgrades, events,<br/>locations, achievements")]

    app --> screens
    app --> game
    app --> market
    app --> config
    screens --> game
    screens --> market
    screens --> demand
    screens --> dates
    screens --> stats
    screens --> fmt

    runner --> strategies
    runner --> game
    runner --> config
    runner --> fmt
    strategies --> game
    strategies --> demand

    game --> simulation
    game --> market
    game --> achievements
    game --> weather
    game --> inventory
    game --> recipes

    simulation --> market
    simulation --> weather
    simulation --> dates
    simulation --> demand
    simulation --> sales
    simulation --> inventory
    simulation --> recipes
    simulation --> registry
    simulation --> rng
    sales --> inventory
    sales --> demand
    market --> inventory
    market --> rng
    recipes --> registry
    dates --> config

    modifiers -- "@register_modifier" --> registry
    events -- "@register_event" --> registry
    upgrades -- "@register_upgrade" --> registry
    modifiers --> demand
    modifiers --> dates
    events --> demand
    events --> market
    upgrades --> demand

    config -- "read_raw_content()<br/>(the only file read in engine/)" --> content
```

Notes:

- **Plugins register at import time.** `engine/__init__.py` imports the `modifiers`, `events` and
  `upgrades` packages, and each package's `__init__.py` imports its plugin modules. Their decorators
  fill the registry dicts.
- **`sim.runner` depends on `ui.format`** for money and percent formatting in the balance report.
  It's the only place tooling depends on the UI package.
- **The UI reaches into several engine modules**, not only `game`:
  - `market`: `todays_pack_prices`, `market_notes`, `purchase_cost`, `discount_pct`;
  - `demand`: `recipe_score` in the Plan screen, and `fmt_mul` in `day_result`;
  - `dates`: day names and holidays;
  - `stats`: the Stats and Game over screens.

## 2. One day: `game.play_day`

This is the real call order in `engine/game.py` and `engine/simulation.py` (`simulate_day` and its
private helpers `_context`, `_fire_start_events`, `_collect_effects`, `_run_sales`, `_result`,
`_upkeep` and `_advance`). Each random step uses its own seeded stream from `rng.day_rng`, shown
as `rng "..."`.

```mermaid
sequenceDiagram
    autonumber
    participant Plan as PlanScreen
    participant App as LemonadeApp
    participant Game as engine.game
    participant Sim as engine.simulation
    participant Market as engine.market
    participant Weather as engine.weather
    participant Reg as engine.registry plugins
    participant Demand as engine.demand
    participant Sales as engine.sales
    participant Inv as engine.inventory

    Plan->>App: start_day(plan)
    App->>Market: market_notes(state, cfg)
    App->>Game: play_day(state, plan, cfg)
    Note over Game: raises GameOverError unless status is PLAYING
    Game->>Sim: simulate_day(state, plan, cfg)

    Sim->>Market: validate_plan(state, plan, cfg)
    Note over Sim,Market: InvalidPlan or InsufficientFunds propagate to the app, state unchanged
    Sim->>Market: plan_cost(state, plan, cfg)
    Sim->>Market: apply_purchases(state, plan, cfg)
    Market->>Inv: add(inv, item, qty, expires_on_day)
    Market-->>Sim: bought state (cash charged, stock and upgrades added), purchased

    Sim->>Weather: resolve(forecast, rng "weather", cfg)
    Weather-->>Sim: actual weather and temp_f
    Note over Sim: _context builds DayContext with dates.day_of_week and dates.holiday_name

    loop every id in sorted(EVENTS)
        Sim->>Reg: event.chance(ctx) vs rng "event:id"
        opt event fires
            Sim->>Reg: event.on_day_start(ctx)
            Reg-->>Sim: EventOutcome (effects, message, close_stand, cash_delta)
        end
    end

    Sim->>Reg: _collect_effects: every MODIFIERS effects(ctx)
    Sim->>Reg: active_upgrades(state) effects(ctx)
    Note over Sim: effects = modifiers + owned upgrades + fired event effects

    Sim->>Demand: compute_demand(ctx, effects)
    Demand-->>Sim: DemandBreakdown (customers, price_factor, taste, feedback, buy_prob)

    alt an event set close_stand
        Note over Sim: _closed_sales gives 0 cups and StopReason.STAND_CLOSED
    else stand open
        Sim->>Sim: recipes.effective_recipe(state, recipe, cfg)
        Sim->>Sales: sell(customers, demand, inventory, recipe, cfg, rng "sales")
        loop each customer
            Note over Sales: roll below buy_prob buys, else a LossReason. First failed serve sets stop_reason, later buyers count SOLD_OUT. A new pitcher uses lemons and sugar, each cup uses ice and a cup.
        end
        Sales->>Inv: consume(inv, item, qty) once per item (FIFO write-back)
        Sales-->>Sim: SalesOutcome (cups_sold, inventory, consumed, lost_sales, stop_reason)
    end

    Sim->>Demand: reputation_delta(demand, cups_sold, cfg) in _result
    Note over Sim: _result builds the DayResult (revenue, spend, profit, effects, feedback)

    loop every fired event
        Sim->>Reg: event.on_day_end(ctx, result)
        Reg-->>Sim: EventOutcome (e.g. inspector cash_delta)
    end

    Sim->>Inv: melt(inv, best upgrade ice_retention)
    Sim->>Inv: spoil(inv, day)
    Note over Sim: cash = max(0, cash + revenue + event cash). The result gets profit, cash_end, ice_melted, spoiled, events.
    Sim->>Weather: generate_forecast(rng "forecast" for day + 1)
    Note over Sim: _advance returns a new GameState (day + 1, cash, inventory, reputation, forecast, history + result)
    Sim-->>Game: new_state, result

    Game->>Game: end_day(state, cfg)
    Game->>Market: cost_to_make_one_cup(state, cfg) in is_bankrupt
    Note over Game: BANKRUPT if cash is below that cost, then achievements.unlock adds new achievements
    Game-->>App: final state, final.history[-1]
    App->>App: push DayResultScreen(result, state, notes)
```

### Where the code differs from CLAUDE.md §6

CLAUDE.md §6 lists 13 pipeline steps. The code differs in four places, and the diagram follows the
code:

1. **Purchases and upgrades are one call.** Buying supplies (§6 step 2) and upgrades (step 3) both
   happen in `market.apply_purchases`.
2. **The reputation change is computed early.** It's computed in `_result`, *before* the end-of-day
   events (§6 step 9) and upkeep (step 10). It's applied to the state in `_advance`.
3. **Bankruptcy and achievements are outside `simulate_day`.** They happen in `game.end_day`,
   called by `game.play_day` after `simulate_day` returns. This was Phase 0 decision D3, which
   avoids a circular import between `game` and `simulation`.
4. **Loan interest and fees don't exist.** They appear in §6 step 10, but there's no loan or fee
   logic in `_upkeep`. `GameState.loan` exists but is never set (see §3 below).

## 3. Core data model

All of these are `@dataclass(frozen=True, slots=True)` in `engine/models.py`. Fields and types are
copied from the dataclass definitions, including fields that have defaults. `Cents` is an alias for
`int`. `Item`, `Weather`, `Factor`, `LossReason`, `StopReason` and `GameStatus` are `StrEnum`s in
`engine/types.py`.

```mermaid
classDiagram
    direction LR

    class GameState {
        +int seed
        +int day
        +Cents cash
        +Inventory inventory
        +float reputation
        +frozenset~str~ upgrades
        +Forecast forecast
        +tuple~DayResult~ history
        +Loan loan = None
        +frozenset~str~ achievements
        +GameStatus status = PLAYING
        +str difficulty = normal
    }

    class Inventory {
        +Mapping batches
        +empty() Inventory
        +count(item) int
    }

    class Batch {
        +int qty
        +int expires_on_day
    }

    class Recipe {
        +int lemons_per_pitcher = 6
        +int sugar_per_pitcher = 4
        +int ice_per_cup = 3
    }

    class DayPlan {
        +tuple~Purchase~ purchases
        +Recipe recipe
        +Cents price_per_cup
        +str location_id = park
        +tuple~str~ upgrade_purchases
    }

    class Purchase {
        +Item item
        +int packs
    }

    class Forecast {
        +Weather predicted
        +int predicted_temp_f
    }

    class Loan {
        +Cents principal
        +int rate_pct
        +int due_day
    }

    class DayResult {
        +int day
        +Weather weather
        +int temp_f
        +int potential_customers
        +int cups_sold
        +dict lost_sales
        +StopReason stop_reason
        +Cents revenue
        +Cents spend
        +Cents profit
        +int ice_melted
        +dict spoiled
        +tuple~Effect~ effects
        +tuple~str~ events
        +float reputation_delta
        +tuple~str~ feedback
        +dict purchased
        +dict consumed
        +float taste_score
        +float buy_prob
        +Cents cash_end
        +tuple~str~ achievements_unlocked
    }

    class Effect {
        +Factor factor
        +str op
        +float value
        +str reason
        +str source
    }

    GameState *-- Inventory : inventory
    GameState *-- Forecast : forecast
    GameState o-- "0..*" DayResult : history
    GameState o-- "0..1" Loan : loan (never set)
    Inventory *-- "0..*" Batch : batches per Item
    DayPlan *-- Recipe : recipe
    DayPlan *-- "0..*" Purchase : purchases
    DayResult *-- "0..*" Effect : effects
```

Types simplified in the diagram (to keep the Mermaid syntax portable):

- `Inventory.batches` is `Mapping[Item, tuple[Batch, ...]]`.
- `Batch.expires_on_day` and `GameState.loan` are optional (`int | None` and `Loan | None`, where
  `None` means "never expires" and "no loan").
- `DayResult.stop_reason` is `StopReason | None`.
- `DayResult.lost_sales` is `dict[LossReason, int]`. `spoiled`, `purchased` and `consumed` are
  `dict[Item, int]`.
- `Effect.op` is `Literal["mul", "add"]`.
- `upgrade_purchases`, `achievements`, `status`, `difficulty`, `location_id` and the later
  `DayResult` fields from `purchased` on all have defaults.

How they're used:

- **`simulation.simulate_day(state, plan, cfg)`** takes a `GameState` and a `DayPlan`, and returns
  a new `GameState` plus a `DayResult`. The input state is never modified.
- **Mutable-looking fields.** `Inventory.batches` and the dict fields on `DayResult` are plain
  dicts, read-only by convention (Phase 0 decision D10). Every change builds a new one.
- **How `Batch` expiry works.** `expires_on_day` is the last day a batch can be used.
  `inventory.spoil(inv, day)` drops batches with `expires_on_day <= day`, and `inventory.consume`
  takes stock oldest-expiry first.
- **Other models not drawn.** `engine/models.py` also defines `EventOutcome`, `DayContext` and
  `PlanPreview`. They're left out because they aren't part of the core model you asked for.

## Verification: every node and where it lives

| Diagram node | Real code |
|---|---|
| `ui.app`: `LemonadeApp`, `main()`, `start_day` | `src/lemonade/ui/app.py` |
| `ui.screens`: `PlanScreen`, `DayResultScreen`, stats, help, game_over | `src/lemonade/ui/screens/{plan,day_result,stats,help,game_over}.py` |
| `ui.format` | `src/lemonade/ui/format.py` |
| `sim.runner`: `run_games`, `main` | `src/lemonade/sim/runner.py` |
| `sim.strategies`: `naive`, `greedy`, `forecast_aware` | `src/lemonade/sim/strategies.py` |
| `engine.game`: `new_game`, `play_day`, `end_day`, `is_bankrupt`, `preview_plan` | `src/lemonade/engine/game.py` |
| `engine.simulation`: `simulate_day` and its helpers | `src/lemonade/engine/simulation.py` |
| `engine.market`: `validate_plan`, `plan_cost`, `apply_purchases`, `market_notes`, `cost_to_make_one_cup` | `src/lemonade/engine/market.py` |
| `engine.weather`: `resolve`, `generate_forecast` | `src/lemonade/engine/weather.py` |
| `engine.demand`: `compute_demand`, `reputation_delta` | `src/lemonade/engine/demand.py` |
| `engine.sales`: `sell`, `SalesOutcome` | `src/lemonade/engine/sales.py` |
| `engine.inventory`: `add`, `consume`, `melt`, `spoil` | `src/lemonade/engine/inventory.py` |
| `engine.recipes`: `effective_recipe` | `src/lemonade/engine/recipes.py` |
| `engine.dates`: `day_of_week`, `holiday_name` | `src/lemonade/engine/dates.py` |
| `engine.achievements`: `unlock` | `src/lemonade/engine/achievements.py` |
| `engine.stats` | `src/lemonade/engine/stats.py` |
| `engine.rng`: `day_rng` | `src/lemonade/engine/rng.py` |
| `engine.config`: `parse_config`, `read_raw_content`, `load_config` | `src/lemonade/engine/config.py` |
| `engine.models`, `engine.types`, `engine.errors` | `src/lemonade/engine/{models,types,errors}.py` |
| `engine.registry`: `MODIFIERS`, `EVENTS`, `UPGRADE_HANDLERS`, `active_upgrades` | `src/lemonade/engine/registry.py` |
| modifiers: weather, day_of_week, holiday, difficulty | `src/lemonade/engine/modifiers/*.py` |
| events: heat_wave, storm, festival, inspector | `src/lemonade/engine/events/*.py` |
| upgrades: cooler, juicer, sign, umbrella | `src/lemonade/engine/upgrades/*.py` |
| content TOML (6 files) | `src/lemonade/content/*.toml`, listed in `config.CONTENT_FILES` |
| `GameState`, `Inventory`, `Batch`, `Recipe`, `DayPlan`, `Purchase`, `Forecast`, `Loan`, `DayResult`, `Effect` | `src/lemonade/engine/models.py` |
