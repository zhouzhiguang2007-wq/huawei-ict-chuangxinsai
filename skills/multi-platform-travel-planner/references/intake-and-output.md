# Intake and Output Reference

Use this reference for incomplete prompts, complex constraints, follow-up changes, and file-ready travel reports.

## Intake fields

| Field | Required for a full trip | If missing |
|---|---|---|
| Destination | Yes | Ask if absent |
| Departure date or date window | Yes | Ask before date-specific planning |
| Approximate budget and per-person/group scope | Yes | Ask; retain any previously stated limit |
| Duration | Yes | Ask if absent |
| Party size | Yes for group cost/rooms | Ask if absent |
| Intercity transport included | Yes for a capped total | Ask if the answer changes affordability |
| Arrival/departure times | When fixed by user | Keep unknown until transport is selected |
| Origin city | No | Needed only for intercity fare calculation |
| Interests | Confirm after core fields | Derive only a tentative hypothesis from what the user said, then ask |
| Walking/mobility | Ask if group composition or activities make it material | Keep unknown; do not assume everyone can walk moderately |
| Local transport | No | Compare available modes; do not record a preference without evidence |
| Accommodation | Ask room distribution for a group | Keep room count as a scenario until confirmed |
| Sources/platforms | No | Public web plus official sources; add named platforms |
| Output | No | Concise report in chat |

Ask one question per turn in this order: destination, departure date, budget amount/scope, days, group size, then preference confirmation. Skip known fields and accept volunteered answers to future questions. A preference inferred from “美食为主” or “想拍照” is a proposal, not an approved constraint. While awaiting an answer, research stable facts and photos, but leave the itinerary and computed package price pending. If the user wants an explicit demonstration, use a visible “假设情境” label and do not present it as the user's actual trip.

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

1. Confirmed inputs, outstanding question, then feasibility once core fields are known.
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

