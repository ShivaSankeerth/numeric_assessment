# Product decisions: Lemonade Stand Tycoon

The 10 most important product decisions: game rules, player experience, and what was cut. Each
one gives the decision, why it was made, the trade-off, and what to revisit.

## Where each decision came from

There is no `docs/design.md` in the repo. The design-session record used here is the original
`CLAUDE.md` (commit `554d2dc`, written before any code). Every decision is tagged with its
source:

| Tag | Meaning |
|---|---|
| **Brief** | A "core rule from the brief" in CLAUDE.md §1 ("never violate"). |
| **Design** | Specified in the original CLAUDE.md (§5–§10, §15). |
| **Design assumption** | One of the original CLAUDE.md §13 assumptions (A1–A6). |
| **Approved in planning** | Proposed while planning the build (Phase 0 decisions D1–D21, or the Phase 1 lane plan) and approved before any code was written. |
| **Build-time assumption** | Decided while writing code, with no review beforehand. Reported afterwards at most. |

Where no reason is written down anywhere (CLAUDE.md, the plans, commit messages, the README),
the **Why** says `TODO: my reasoning`.

> **Headline finding while writing this: the demand model can be exploited.** The buy-chance
> formula `0.1 + 0.8 × price_factor × taste × (0.5 + reputation)` never drops below 10%, whatever
> the price or the taste. The price cap is $10. Buying a starter kit daily and charging $10 a cup
> ends 30 days with a **median of $1,437 (0/50 games bankrupt)**. Charging 50¢ gives $33, and the
> best balance bot, which prices at the fair price, gets $163. Overpricing doesn't even hurt
> reputation: a perfect recipe at $10 gives a satisfaction of 0.6, above the 0.5 neutral point.
> See decisions 6 and 8.

---

## 1. The day is planned in the morning and played out one customer at a time

- **Decision:**
  - Purchases, recipe and price are locked when the day starts, and there is no restocking
    during the day.
  - Customers arrive one at a time and each rolls buy or no-buy.
  - As soon as the stand can't serve a buyer (no cup, not enough ice, or not enough lemons or
    sugar for a new pitcher), sales stop.
  - Later would-be buyers are counted as "sold out".
- **Why:**
  - Locking decisions and stopping on empty are core rules from the brief.
  - No restocking is assumption A4.
  - The one-at-a-time loop is from CLAUDE.md §6: it "naturally models selling out mid-day and
    gives loss-reason stats".
  - Continuing to count would-be buyers after a sell-out is approved decision D11: it lets the
    report show how many sales stock-outs cost.
- **Trade-off:**
  - Under-stocking is punished with no way to recover in the day. Planning is the only skill
    that counts.
  - The loop costs time per customer. It had to be rewritten to use plain counters (`d55599b`)
    to keep the test and simulation budget.
- **What I'd revisit:** the report says *why* sales stopped ("sold out of lemons") but not
  *when*. Showing "sold out at customer 23 of 60" would make under-stocking easier to learn from.
- **Source:** Brief + Design (§6) + Design assumption A4. The sold-out counting is Approved in
  planning (D11).

## 2. Ice melts overnight, lemons spoil after 5 days, everything else keeps

- **Decision:**
  - All leftover ice melts at the end of the day. The Cooler upgrade keeps 50%.
  - Lemons can be used on the day they're bought and the next 4 days, then spoil at the end of
    their last day. Stock is always used oldest first.
  - Sugar and cups never expire.
- **Why:**
  - Ice melting is a core rule from the brief.
  - The 5-day lemon life and oldest-first use are in CLAUDE.md §5/§9.
  - The exact meaning of "5 days" (the purchase day counts as day 1) is approved decision D13.
  - Why lemons should spoil at all (the design intent behind §9): `TODO: my reasoning`.
- **Trade-off:**
  - Ice is effectively a daily running cost, so buying ice for a cold or rainy day that doesn't
    sell is pure loss.
  - Ice only comes in 100-cube bags, and the default recipe uses 3 cubes a cup. A bag therefore
    covers about 33 cups, and a slow day wastes most of one.
  - Spoilage pulls against the bulk discounts in decision 5.
- **What I'd revisit:** whether 100-cube bags make cold days too punishing. Smaller ice packs
  would soften this, but they're a §9 content change.
- **Source:** Brief (ice) + Design (§9 shelf life, oldest-first). The day-count meaning is
  Approved in planning (D13). The Cooler's 50% is Design (§9).

## 3. Bankruptcy means you can't afford to make even one cup

- **Decision:**
  - At the end of each day, you're bankrupt if your cash is less than the cost of the packs
    you're missing for a **minimal cup**: 1 lemon and 1 paper cup. Sugar and ice are optional,
    because a recipe can set both to 0.
  - $0 with a makeable cup in stock is not bankruptcy.
- **Why:**
  - The brief defines bankruptcy as no money *and* no way to make a cup.
  - Assumption A3 widened "no money" to "less than the cheapest pack needed".
  - The minimal-cup reading is approved decision D2. A3 didn't say *which* recipe counts, and
    all ice has melted by the time of the check. Any recipe that needs ice would therefore make
    nearly everyone bankrupt every night.
- **Trade-off:**
  - A player can be "alive" holding stock their chosen recipe can't use, e.g. lemons and cups
    but no sugar and $0. They recover only by switching to a no-sugar recipe, and nothing in
    the UI suggests that.
  - **Found while writing this doc:** the check runs *after* the day counter moves on, so it
    prices the missing packs at the **next morning's** prices. That includes that morning's
    ±15% swing, any lemon shortage (+50%) and the difficulty markup. Two players in the same
    position can get different verdicts depending on tomorrow's price roll.
- **What I'd revisit:**
  - Whether next-morning pricing is intended, since it was never decided explicitly.
  - Whether the Game over screen, or a warning before it, should explain how close the player
    is to bankruptcy.
- **Source:** Brief + Design assumption A3. The minimal cup and cost test are Approved in
  planning (D2). Next-morning pricing is a Build-time assumption: it came from how the code
  runs, not a decision.

## 4. The forecast is right about 70% of the time, and misses are one step

- **Decision:**
  - The Plan screen shows one predicted weather and temperature.
  - 70% of the time the weather matches, and the temperature is within ±5°F.
  - Otherwise the weather moves exactly one step on storm → rainy → cloudy → sunny → hot (inward
    at either end), and the temperature is re-rolled within the new weather's range.
- **Why:**
  - The 70% and the one-step shift are assumption A5.
  - The storm-to-hot ordering is approved decision D5, because the weather list in the code has
    no natural order.
  - Why 70% specifically: `TODO: my reasoning`.
  - The ±5°F noise and the forecast weights (sunny 35, cloudy 25, rainy 18, hot 15, storm 7)
    were chosen while writing the code. `TODO: my reasoning` for the values.
- **Trade-off:**
  - The forecast is useful enough that reading it pays. In the balance report the
    forecast-aware bot ends $31 ahead of the greedy bot (median $163 vs $132 on normal).
  - Because misses are only one step, a "sunny" forecast can never turn into a storm. Players
    are never blindsided, but there's less tension.
- **What I'd revisit:** whether the forecast should show its uncertainty (e.g. "Sunny, 70%
  confidence"). Today it presents a single prediction as fact.
- **Source:** Design assumption A5. The ordering is Approved in planning (D5). The temperature
  noise and forecast weights are Build-time assumptions.

## 5. Supplies come in packs with bulk discounts, and prices are shown before you buy

- **Decision:**
  - Packs and base prices:

    | Item | Pack | Price |
    |---|---|---|
    | Lemons | 12 | $4.00 |
    | Sugar | 8 cups | $3.00 |
    | Ice | 100 cubes | $1.50 |
    | Cups | 50 | $2.50 |

  - Lemons and sugar get 10% off for 3+ packs and 20% off for 6+. Ice and cups have no
    discount.
  - Each item's price moves up to ±15% a day.
  - There's an 8% daily chance of a lemon shortage (+50%).
  - Everything is shown on the Shop tab before you buy.
- **Why:**
  - Packs, prices and lemon tiers are from §9 and assumption A2. §9 says sugar's tiers are
    "similar", which was implemented as identical.
  - Ice and cups have no tiers because §9 lists none for them.
  - The ±15% fluctuation is from §9.
  - The shortage is shown before buying, and is a market condition rather than an event, per
    the approved Phase 1 plan: events fire *after* purchases, so a shortage-as-event would
    raise prices the player could never react to.
  - Why 8% and +50%: `TODO: my reasoning`.
- **Trade-off:**
  - Bulk discounts reward buying lemons ahead, and spoilage (decision 2) punishes it. Whether
    that tension is the intended design is `TODO: my reasoning`.
  - Fluctuating prices meant tests needed a special test-only config with fixed prices
    (`tests/factories.py`).
- **What I'd revisit:** whether swings should apply to all four items or just lemons. Today a
  +11% on cups mostly adds noise to the numbers.
- **Source:** Design (§9) + Design assumption A2. The shortage timing and placement are Approved
  in planning (Phase 1 plan). Sugar tiers identical to lemons, and 8%/+50%, are Build-time
  assumptions.

## 6. The demand model is deliberately simple and always explains itself

- **Decision:**
  - Demand uses the one-line formula in CLAUDE.md §7: traffic × a buy chance built from price,
    taste and reputation.
  - Every modifier, upgrade and event adds an `Effect` with a readable reason.
  - The day report shows an effects table ("Rainy weather: -55% foot traffic"), lost sales by
    reason, and customer feedback.
- **Why:**
  - Principle 7 in CLAUDE.md §3: the report must show *why* sales were what they were.
  - §7 itself: "Correct, deterministic, explainable > realistic", with a timebox against
    realism.
  - The formula's constants (0.1 floor, 0.8 scale, 0.5 reputation offset, 0.95 cap) are written
    into §7.
- **Trade-off:**
  - It isn't realistic.
  - **The 10% floor is exploitable** (see the headline finding). It applies at any price and
    any taste. Together with the $10 price cap (approved decision D17), it makes "always charge
    $10" the dominant strategy.
  - Each lost customer is blamed on a single reason, the weakest factor (approved decision D11).
    A customer put off by *both* price and taste only counts as "too expensive".
- **What I'd revisit:**
  - **First priority:** make the floor shrink with the price factor (or apply only at or below
    the fair price), and/or lower the $10 cap. Then re-run the balance.
  - Make overpricing lower reputation even with a perfect recipe.
- **Source:** Design (§3 principle 7, §7 formula and constants). The single-reason attribution
  and the price cap are Approved in planning (D11, D17).

## 7. Money only moves at the start of the day, apart from fines

- **Decision:**
  - Every plan cost (supplies, upgrades, rent) is paid up front, so cash can never go negative.
  - Event fines (the health inspector's $5) apply at the end of the day and never take cash
    below $0.
  - Lemonade left in a half-used pitcher at close is thrown away; its lemons and sugar count as
    used.
- **Why:**
  - Paying up front is approved decision D12: it guarantees cash ≥ 0, which is a required
    invariant.
  - The fine behaviour is approved decision D7.
  - Throwing away the leftover pitcher is approved decision D6: there's no "pitcher" stock item,
    which keeps the model simple.
- **Trade-off:**
  - The fine counts in profit and cash but **not in "spend"**, so on a fined day revenue minus
    spend ≠ profit in the report.
  - A broke player's fine is partly forgiven by the $0 floor.
  - The discarded pitcher can waste up to 11 cups' worth of lemons and sugar a day, which makes
    slow days more expensive than they look.
- **What I'd revisit:** counting fines as spend, so the report's arithmetic always adds up.
- **Source:** Approved in planning (D6, D7, D12). The fine amount and inspection rules are a
  Build-time assumption (ENGINE lane).

## 8. Difficulty levels, with normal tuned against bots rather than players

- **Decision:**

  | Level | Starting cash | Traffic | Supply prices |
  |---|---|---|---|
  | Easy | $30 | ×1.15 | −10% |
  | Normal | $20 | ×1.0 | base |
  | Hard | $15 | ×0.9 | +10% |

  - Normal was tuned so a forecast-reading bot ends 30 days at about 8× its starting cash
    ($163), and a weather-blind one at about 3.7×.
  - To get there, park foot traffic went from 100 to 60, and hard was softened from ×0.85
    traffic / +15% prices.
- **Why:**
  - Difficulty levels are listed in Tier 2 of CLAUDE.md §15.
  - The balance targets and all the tuning were a Build-time assumption made during the balance
    pass (`49a7d06`). At traffic 100 the bots never went bankrupt and ended at $85–$315, "far
    too easy".
  - The targets themselves ("skill should clearly pay and nobody should get rich by accident")
    were never agreed. `TODO: my reasoning` on whether they're right.
- **Trade-off:**
  - The balance bots all price at or below the fair price, so **the balance numbers completely
    miss the $10 exploit**.
  - On normal, no bot ever goes bankrupt (0%). A careful human may still find normal easy.
- **What I'd revisit:**
  - Add an "overpricer" and a "random" bot to `lemonade-sim`, fix decision 6, then re-tune.
  - Tune against a playtest or two, not only bots.
- **Source:** Design (Tier 2 lists difficulty). The level values are a Build-time assumption
  (ENGINE lane), and the balance targets and tuning are a Build-time assumption (balance pass).

## 9. The Plan screen opens on the Start button

- **Decision:**
  - The Plan screen starts with **Start day** focused. `enter` starts the day from anywhere,
    including inside a text box.
  - `q`, `t` and `?` only work when no text box has focus. `ctrl+q` always quits.
  - Buttons are also clickable.
- **Why:**
  - CLAUDE.md §10 requires `q`, `t` and `?` on the Plan screen.
  - Textual 8 deliberately ignores letter shortcuts while a text box has focus, even
    high-priority ones. This was found while building the UI (step 5).
  - Starting on the button was the smallest fix that kept the §10 keys.
- **Trade-off:**
  - Players have to Tab or click into a field before typing.
  - If the Start button becomes disabled while it has focus (cart over budget), focus can jump
    into a text box, and the letter shortcuts stop working until the player Tabs out.
- **What I'd revisit:** moving shortcuts to keys a text box never wants (e.g. `F1` help, `F2`
  stats), so they work everywhere.
- **Source:** Build-time assumption (step 5, reported afterwards). The required keys are Design
  (§10).

## 10. What was cut: all of Tier 3, and any way to win

- **Decision:**
  - Not built:
    - loans with interest;
    - more locations with rent (beach, downtown). Only the park exists;
    - a second stand and a helper;
    - competitor and viral-post events, and word of mouth;
    - save/load, high scores and a title screen;
    - the 30-day challenge mode.
  - The game is endless, and the only ending is bankruptcy. A "won" game status exists, and the
    Game over screen can show "You won", but **nothing in the engine ever sets it**.
- **Why:**
  - CLAUDE.md's 3-hour budget: Tier 3 is "stretch, only if ahead of schedule; otherwise list as
    TODO in README".
  - An endless game by default is assumption A6.
  - Why these items went in Tier 3 rather than higher: `TODO: my reasoning`.
- **Trade-off:**
  - With no goal and no end, sessions just stop. The score is "cash on hand" whenever you quit.
  - Achievements (8, e.g. "Tycoon" at $200) are the only goals.
  - With one location, the §9 location designs (beach: busy when hot; downtown: price-tolerant)
    don't exist. Neither does rent, although the engine supports it.
- **What I'd revisit:** the 30-day challenge mode first. It's the smallest change that gives the
  game an ending and a meaningful score, and the unused "won" status and "You won" screen are
  already waiting for it.
- **Source:** Design (§15 tiers, time budget) + Design assumption A6.

---

## Summary

| # | Decision | Source |
|---|---|---|
| 1 | Plan in the morning, one customer at a time, stop on sell-out | Brief, Design, A4, D11 |
| 2 | Ice melts; lemons spoil after 5 days, oldest first | Brief, Design, D13 |
| 3 | Bankrupt = can't afford a minimal cup | Brief, A3, D2; next-morning pricing is **build-time** |
| 4 | Forecast ~70%, one-step misses | A5, D5; noise and weights **build-time** |
| 5 | Packs, bulk tiers, daily prices seen before buying | Design, A2, Phase 1 plan; some values **build-time** |
| 6 | Simple, self-explaining demand model | Design, D11, D17; **exploit found** |
| 7 | Pay up front; fines end-of-day and never below $0; leftover pitcher thrown away | D6, D7, D12 |
| 8 | Difficulty levels; normal tuned against bots | Design (Tier 2); values and targets **build-time** |
| 9 | Plan screen opens on Start | **Build-time** |
| 10 | Tier 3 cut; no way to win | Design, A6 |
