# Lemonade Stand Tycoon

A terminal lemonade-stand business simulator. Each morning you buy supplies, set a recipe and a
price, and look at the forecast. Then the day plays out customer by customer, and you get a report
that explains **why** you sold what you sold. Your score is the cash you have on hand. You go
bankrupt when a day ends with too little cash and too little stock to make even one more cup.

Built with Python 3.11+, [Textual](https://textual.textualize.io/) and Rich.

## Quick start

```bash
uv sync                                   # install
uv run lemonade                           # play (random seed, normal difficulty)
uv run lemonade --seed 42                 # reproducible game
uv run lemonade --difficulty hard         # easy | normal | hard
uv run lemonade-sim                       # headless bot balance report (200 games x 30 days)
uv run lemonade-sim --games 500 --strategy forecast --days 30 --difficulty hard
uv run pytest -q                          # all tests (~7s)
uv run ruff format . && uv run ruff check .
```

## How to play

1. **Plan** (the main screen). The left side shows cash, reputation, stock and the forecast.
   The tabs on the right are:
   - **Shop:** buy packs at today's prices. Bulk discounts and supplier notes (such as a lemon
     shortage) are shown here.
   - **Recipe:** lemons and sugar per pitcher, ice per cup, with a live taste hint for the
     forecast temperature.
   - **Price:** price per cup, with a note on the fair price.
   - **Upgrades:** cooler, juicer, sign, umbrella.

   The bottom bar shows the cart total, cash after buying and cups makeable. **Start day** is
   disabled if you can't afford the cart.
2. **Day result:** revenue, spend and profit; cups sold out of passers-by; why the day stopped
   (e.g. "sold out of lemons"); lost sales by reason; customer feedback ("Too sour!"); events;
   ice melted and lemons spoiled. It ends with an **effects table** that explains the demand
   ("Rainy weather: -55% foot traffic", "Weekend (Saturday): +25% foot traffic", ...).
3. Repeat until you go bankrupt. The **Game over** screen shows your score, and `n` starts a new
   game with a difficulty picker.

| Screen | Keys |
|---|---|
| Plan | `enter` start day · `1`-`4` switch tabs · `t` stats · `?` help · `q` quit |
| Day result | `enter` next day (or game over) |
| Stats | `esc` / `t` back |
| Help | `esc` / `?` close |
| Game over | `n` new game, then pick a difficulty with `1`/`2`/`3` or `e`/`n`/`h` |

Textual ignores letter keys while a text box has focus. The Plan screen therefore starts focused
on **Start day**; press `Tab` or click to edit a field. `enter` inside a field also starts the day,
and `ctrl+q` quits from anywhere.

## Features

- **Core rules:** decisions lock when the day starts, sales stop when any ingredient runs out, and
  leftover **ice melts** overnight. Everything else carries over.
- **Weather:** a forecast that is right about 70% of the time; otherwise the real weather is one
  step off (storm → rainy → cloudy → sunny → hot).
- **Recipe and taste:** taste is the distance from an ideal recipe, and the ideal amount of ice
  rises with temperature. Customers give feedback on the lemonade.
- **Pricing:** a fair price that varies with the weather, bulk discounts (3+ packs −10%, 6+ packs
  −20%), daily supplier price swings (±15%) and random lemon shortages (+50%).
- **Stock:** lemons **spoil** after 5 days, and stock is always used oldest-first.
- **Reputation:** rises with tasty, good-value lemonade and a busy day; it raises the chance that
  each passer-by buys.
- **Upgrades:**

  | Upgrade | Cost | Effect |
  |---|---|---|
  | Cooler | $15 | keeps 50% of leftover ice |
  | Juicer | $12 | 25% more juice per lemon |
  | Sign | $8 | +15% foot traffic |
  | Umbrella | $6 | halves the rain/storm traffic penalty |

- **Events:**

  | Event | Chance | Effect |
  |---|---|---|
  | Heat wave | 15% on sunny/hot days | +40% traffic |
  | Storm | 50% on storm days | closes the stand |
  | Town festival | 5% | +50% traffic |
  | Health inspector | 10% | $5 fine if the taste is bad, or no ice on a hot day |

- **Calendar:** weekends are busier (+25%), and there are holidays on days 4, 12, 21 and 30.
- **Difficulty:**

  | Level | Starting cash | Traffic | Supply prices |
  |---|---|---|---|
  | Easy | $30 | ×1.15 | −10% |
  | Normal | $20 | ×1.0 | base |
  | Hard | $15 | ×0.9 | +10% |

- **Achievements:** 8 in total, from "Open for Business" to "Tycoon" ($200 cash). They're shown on
  the Stats screen with progress, and on the day you unlock them.
- **Stats screen:** a cash-over-time chart, totals, sell-through, and the best and worst days.
- **Bots and balance report:** `lemonade-sim` plays three strategies headlessly on the same engine.

## Architecture

```
src/lemonade/
  engine/     pure game logic: no I/O, no printing, no Textual imports
    types.py models.py config.py errors.py rng.py
    market.py inventory.py weather.py demand.py recipes.py dates.py sales.py
    simulation.py   simulate_day(): the ONLY orchestrator of a day
    game.py         new_game / play_day / end_day / is_bankrupt / preview_plan (the UI's entry points)
    registry.py     plugin registries + decorators
    modifiers/ events/ upgrades/   one file per plugin
    stats.py        derived history stats for the Stats screen
  content/    *.toml: every price, chance, multiplier and threshold
  ui/         Textual app + screens (plan, day_result, stats, help, game_over), format.py, theme.tcss
  sim/        bot strategies + headless runner (lemonade-sim)
tests/        engine/ property/ ui/ sim/ + factories.py (make_state, make_plan, make_ctx, ...)
```

Key decisions:

- **Pure engine, thin UI.** The UI only calls engine functions and renders what they return. Even
  the cart total and cups makeable come from `game.preview_plan`. The bots use the same engine, so
  the balance report measures exactly what players play.
- **Money is integer cents** everywhere. Discounts use integer maths with half-up rounding, and
  typed prices are parsed with `Decimal`. Cents only become text in `ui/format.py`.
- **Immutable state.** Every model is a `frozen, slots` dataclass, and a day returns a *new*
  `GameState` plus a `DayResult`. That makes tests trivial and every day replayable.
- **Deterministic, isolated randomness.** Nothing uses the global `random`. Each use gets its own
  stream, `random.Random(f"{seed}:{day}:{stream}")` (`forecast`, `weather`, `sales`, `market`, and
  one per event). The same seed and plans always give the same game, and adding a plugin never
  changes other plugins' rolls, so balance reports stay comparable.
- **Plugins, not edits.** Demand modifiers, events and upgrades register themselves with a
  decorator. Adding one never touches `simulation.py`:

  ```python
  @register_upgrade
  class Sign(BaseUpgrade):
      id = "sign"                      # must match [sign] in upgrades.toml
      def effects(self, ctx: DayContext) -> list[Effect]:
          mul = ctx.cfg.upgrades[self.id].params["traffic_mul"]
          return [Effect(Factor.TRAFFIC, "mul", mul, f"Sign: {fmt_mul(mul)} foot traffic", self.id)]
  ```

  Then import it in `upgrades/__init__.py`, add a `[sign]` table to `upgrades.toml`, and add a test.
- **Explainability.** Every modifier returns `Effect`s with a human-readable `reason`, and the day
  report's effects table is built from them.
- **The day pipeline** (`simulate_day`):
  1. Validate the plan.
  2. Pay for everything up front and add the stock.
  3. Resolve the weather.
  4. Roll the events.
  5. Collect the effects.
  6. Compute demand.
  7. Serve customers one at a time: roll buy/no-buy, make a pitcher when needed, stop when
     something runs out.
  8. Run the end-of-day event hooks.
  9. Melt the ice and spoil the lemons.
  10. Update reputation.
  11. Make the next forecast.

  After the day, `game.end_day` applies bankruptcy and achievements.

## Demand model

```
traffic      = base_traffic * Π(TRAFFIC mul) + Σ(TRAFFIC add)
fair_price   = base_fair_price * Π(PRICE_TOLERANCE mul) + Σ(add)
price_factor = clamp(1 - (price - fair) / fair, 0, max_price_factor)
taste        = clamp(recipe_score * Π(TASTE mul) + Σ(TASTE add), 0, 1)
buy_prob     = clamp(base_prob * min(price_factor, 1)
                     + prob_scale * price_factor * taste * (reputation_offset + reputation),
                     0, max_buy_prob) * Π(BUY_PROB mul) + Σ(add)
customer buys ⇔ rng.random() < buy_prob
```

All the constants are in `content/items.toml` under `[demand]`; foot traffic is in `locations.toml`:

| Constant | Value | Meaning / how to tune |
|---|---|---|
| `base_traffic` (park) | 60 | Passers-by on a neutral day. The main lever for overall difficulty. |
| `base_fair_price` | 50¢ | The price that feels fair. Raising it widens margins for good players. |
| `base_prob` | 0.1 | Buy chance even for bad lemonade at a fair price. It fades to 0 as the price rises to 2× fair. |
| `prob_scale` | 0.8 | How much price × taste × reputation matters. |
| `reputation_offset` | 0.5 | Reputation's weight is (0.5 + rep), so it scales demand 0.5× to 1.5×. |
| `max_buy_prob` | 0.95 | Cap before BUY_PROB effects. |
| `max_price_factor` | 1.2 | The most a cheap price can help. |
| `ideal_lemons` / `ideal_sugar` | 6 / 4 | Ideal amount per pitcher. |
| `ideal_ice_base`, `ideal_ice_temp_f`, `ideal_ice_per_10f` | 3, 75°F, 1 | Ideal ice per cup = 3 at 75°F, +1 per 10°F hotter. |
| `taste_penalty_per_unit` | 0.1 | Taste lost for each unit away from the ideal recipe. |
| `reputation_rate` | 0.1 | Most reputation can move in a day. |
| `reputation_taste_weight` | 0.6 | Satisfaction = 0.6 × taste + 0.4 × value for money. |
| `reputation_neutral` | 0.5 | The satisfaction at which reputation doesn't change. |
| `reputation_full_volume` | 40 | Cups needed for the full reputation change. |
| `loss_price_threshold` / `loss_taste_threshold` | 0.5 / 0.5 | How lost sales are attributed in the report. |

Weather traffic multipliers, forecast accuracy and temperature ranges are in `game.toml [weather]`.
The model is deliberately simple: correct, deterministic and explainable matter more than realism.

## Balance

`lemonade-sim` plays three bots on the real engine and content:

- **naive:** the same plan every day, whatever the weather.
- **greedy:** buys for expected demand at the base fair price.
- **forecast:** ideal recipe and fair price for the forecast, with safety stock.

Target: on **normal**, skill should clearly pay and nobody should get rich by accident. On
**hard**, poor play should go bankrupt.

Current results (200 games × 30 days, median final cash from a $20 start on normal):

| Difficulty | naive | greedy | forecast |
|---|---|---|---|
| Easy | $128, 0% bankrupt | $224, 0% | $265, 0% |
| **Normal** | **$74, 0%** | **$132, 0%** | **$163, 0%** |
| Hard | $31, 12% | $37, 12% | $57, 6% |

**Tuning history:** at `base_traffic = 100` the bots made $85/$262/$315 on normal and never went
bankrupt, which was far too easy. Lowering `base_fair_price` hurt skilled players more than naive
ones, because naive's fixed 50¢ then sits above the fair price, so the fair price stayed at 50¢.
Traffic 60 keeps the skill order (forecast > greedy > naive). Hard went from ×0.85 traffic and
+15% prices, where even the best bot was bankrupt 17% of the time, to ×0.9 and +10%.

**The overpricing exploit (fixed).** The bots never price above the fair price, so the table
above couldn't catch this. The original §7 formula applied the 10% `base_prob` floor at *any*
price. A player who bought a starter kit daily and charged the $10 maximum ended 30 days with a
median of **$1,437**, about 9× the best bot. Now the floor shrinks with the price factor and
reaches 0 at twice the fair price. The bots' numbers barely moved (they never priced that high),
and a fixed-price sweep shows the exploit is gone:

| Fixed price (ideal recipe, 1 kit/day, 60 games) | 50¢ | 70¢ | 80¢ | $1 | $10 |
|---|---|---|---|---|---|
| Median cash after 30 days, before the fix | $32 | $150 | $176 | $7 | **$1,440** |
| Median cash after 30 days, after the fix | $32 | $143 | $130 | $9 | $9 |

The best fixed price is now around 70¢ (1.4× the base fair price, helped by hot days). It still
earns less than the forecast bot ($163). `tests/sim/test_exploits.py` guards against the exploit
coming back.

To re-tune, edit the TOML and run `uv run lemonade-sim --strategy all --difficulty <level>`.

## Testing

`uv run pytest -q` runs 262 tests in about 7 seconds.

- **Engine unit tests** for every module and plugin. Required edge cases: bankruptcy (cash 0 and
  no cup possible → bankrupt; cash 0 but a cup possible → not bankrupt), selling out mid-day sets
  the stop reason, invalid plans are rejected with the state untouched, and spoilage is FIFO.
- **Property tests** (hypothesis, multi-day random games on the real config):
  - cash never goes negative;
  - cups sold ≤ cups makeable from the stock after purchases (using the juicer-adjusted recipe);
  - stock is conserved: start + bought = used + remaining + melted + spoiled;
  - the same seed and plans give identical results;
  - ice is 0 at the end of the day without a cooler;
  - achievements are never lost.

  The plan generator is weighted toward affordable starter kits so most generated days actually
  sell. I measured this, because the first version sold on only 1% of days.
- **UI tests** (Textual Pilot): each screen mounts and its keys work, a full day there and back,
  overspending and bad input show notifications, and bankruptcy → game over → new game with a
  chosen difficulty.
- **Sim tests:** each bot plays 100 seeded games without exceptions, plus a CLI smoke test and an
  exploit regression test (charging $10 must not beat fair pricing).

`tests/factories.py` gives tests fixed supplier prices and no achievements by default, so their
numbers are stable. Tests that cover fluctuation and achievements opt in with `market_cfg()` and
`achievements_cfg()`.

## Assumptions

1. One pitcher is 12 cups, made on demand. Cups left in a pitcher at close are thrown away (their
   lemons and sugar count as used).
2. Supplies come in packs. Every purchase, upgrade and rent is paid at the start of the day, and
   there is no restocking mid-day. Cash can never go negative; the inspector's fine is applied at
   the end of the day and clamped at $0.
3. **Bankruptcy** is checked at the end of the day: you are bankrupt if your cash is less than the
   cost, at today's prices, of the packs missing for a *minimal* cup (1 lemon + 1 paper cup). Cash
   $0 with a makeable cup in stock is not bankruptcy, and melted ice alone never bankrupts you.
4. The forecast is right about 70% of the time; otherwise the real weather is one step off.
5. Lemons last the purchase day plus 4 more days. Stock is used oldest first.
6. Supplier prices, shortages and the difficulty markup are known before you buy.
7. A customer who doesn't buy is blamed on the weakest factor (price, then taste, else "not
   interested"). After a sell-out, would-be buyers count as "sold out".
8. The juicer means fewer lemons per pitcher; taste is still judged on your recipe. Upgrades work
   on the day you buy them.
9. Day 1 is a Monday. Holidays fall on fixed game days.
10. There is no end to the game (a 30-day challenge mode is a TODO).

## Dependencies

- Runtime: `textual`, `rich`.
- Dev: `pytest`, `pytest-asyncio` (async Pilot tests), `hypothesis`, `ruff`.

Everything else is standard library (`tomllib`, `decimal`, `random`, `dataclasses`).

## Known issues and TODO

- **Inspector fine:** it counts in profit and cash but not in "spend", so on a fined day revenue
  minus spend ≠ profit.
- **Holidays:** they don't repeat after day 30.
- **Keyboard focus:** if Start becomes disabled while it has focus, focus can move into a text box,
  and letter shortcuts then need a `Tab` out first. `ctrl+q` always works.
- **"Perfect Pitcher":** this achievement effectively needs the exact ideal recipe (taste ≥ 0.99).
- **Balance:** it is tuned only against the bots, not real players; the fair price and reputation
  constants are the next levers.
- **Overpricers never lose:** a player who prices far above fair sells almost nothing, but keeps
  enough stock to "make a cup", so they are never declared bankrupt. The game just stalls.
- **Not built (tier 3):** loans with interest; more locations with rent (beach, downtown); a second
  stand and a helper; competitor and viral-post events; save/load, high scores and a title screen;
  a 30-day challenge mode.

## How it was built

The engine skeleton, a minimal UI and the core property tests were built first and merged to
`main`. Then two parallel lanes worked in separate git worktrees:

- **ENGINE:** upgrades, events, market, calendar, difficulty, achievements.
- **UI+TOOLS:** tabbed plan screen, stats, help, game over, bots and the balance report.

Each lane owned its own files, the few interfaces they shared were agreed in a kickoff commit, and
each lane merged fast-forward only at checkpoints. Conventions are in `CLAUDE.md`.
