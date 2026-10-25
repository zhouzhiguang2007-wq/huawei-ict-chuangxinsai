# Intake and Output Reference

Use this reference for incomplete prompts, complex constraints, follow-up changes, and file-ready travel reports.

## Intake fields

| Field | Required | Default when omitted |
|---|---|---|
| Destination | Yes | Ask if absent |
| Duration | Yes | Ask if absent |
| Total budget | Yes for budget planning | If absent, provide a tiered estimate and label it |
| Party size | No | 1 traveler |
| Intercity transport included | No | Show excluded total and a separate placeholder/estimate |
| Dates or season | No | Recommend the best period and warn that prices are date-sensitive |
| Arrival/departure times | No | Assume arrival 09:00 and departure 18:00 |
| Origin city | No | Needed only for intercity fare calculation |
| Interests | No | Balanced food, landmark, culture, and relaxed walking |
| Walking/mobility | No | Moderate walking, no special accessibility needs |
| Local transport | No | Metro/bus/walking first |
| Accommodation | No | Clean budget lodging near a major transit hub |
| Sources/platforms | No | Public web plus official sources; add named platforms |
| Output | No | Concise report in chat |

State every consequential default under “规划假设”. Do not ask a chain of questions when assumptions can produce a useful first draft.

## Planning units

Each itinerary row should include:

- Time block, allowing buffers.
- Origin → destination sequence.
- Recommended transport and approximate duration.
- Activity and why it fits.
- Nearby dish or food district.
- Estimated cost per person and for the group when applicable.
- Reservation, closure, weather, or accessibility note.

## Mandatory transport section in a travel-plan report

Include “交通查询与接驳” in every generated itinerary or travel-plan file, including short answers. Use one row per meaningful leg; cover origin access when known, intercity travel, airport/station transfer, destination arrival, daily local moves, and the return leg when within scope.

| Date/leg | Exact endpoints | Mode and service | Depart–arrive / duration | Transfers and walk | Fare and inclusion | Source and query time | Buffer / status |
|---|---|---|---|---|---|---|---|

For a flight-plus-rail journey, name the airport terminal and the separate railway station. Count time from scheduled landing to train departure, then allow for deplaning, baggage, walking, security, and boarding cutoff. A map's short POI-to-POI walking time is not the full transfer time. Use 12306 alone for train facts; show seat class and availability wording. For flights, distinguish listing price from confirmed checkout total. Put access fares, local transit, and exclusions in the budget without double counting.

If the origin, travel date, exact terminal, live page, or price is missing, write “待查询/未核实” in the affected cell and identify the missing input or blocked source. Do not substitute an arbitrary future date as a real itinerary. A clearly labeled sample date is acceptable only for a scenario demonstration.

## Output templates

### Fast answer

Use for simple requests:

1. Feasibility and assumptions.
2. Transport query and connection table, including pending fields.
3. Day-by-day route.
4. Budget summary.
5. Best time, practical cautions, and sources.

### Comparison report

Use when the user asks to compare Douyin, Xiaohongshu, and browser results:

1. Research scope and access status per platform.
2. Repeated recommendations across sources.
3. Platform-specific emphasis.
4. Official verification and conflicts.
5. Final retained/removed candidates with reasons.
6. Transport query and connection table.
7. Optimized itinerary and budget.

### File-ready report

Use descriptive headings, repeated table headers, currency units, page-friendly tables, a “交通查询与接驳” table, and a final “价格与开放信息核验日期” note. Put citations or source links near the relevant sections. Do not let decorative layout hide assumptions or estimates.

## Follow-up modifications

Apply changes as a minimal diff:

| User change | Recalculate |
|---|---|
| Lower budget | Tickets, lodging, meals, transit, contingency |
| Arrival/departure change | First/last day, transfers, meals, total cost |
| Elderly/children | Walking, stairs, rest, queues, taxis, closing time |
| Rain | Outdoor stops, indoor substitutes, transit buffers |
| Food-heavy | Meal timing, markets/food districts, reduce duplicate attractions |
| Add remote attraction | Travel time, early start, last transport, opportunity cost |

End with a short “本次调整” summary rather than rewriting explanations that did not change.

