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
| Earliest feasible outbound departure or departure window | When planning a specific outbound train or leave-home time | Ask; a travel date alone does not mean the traveler is free all day |
| Arrival/return times | Needed for first/last day boundaries | Use confirmed services; otherwise ask when they change the feasible route, or mark the draft incomplete |
| Origin city and actual start point | Yes for a complete door-to-door route | Ask after core fields if not supplied or derivable from confirmed transport |
| End point or return service | Yes for a complete route | Ask after core fields if not supplied or derivable from confirmed transport |
| Interests | Confirm after core fields | Derive only a tentative hypothesis from what the user said, then ask |
| Walking/mobility | Ask if group composition or activities make it material | Keep unknown; do not assume everyone can walk moderately |
| Local transport | No | Compare available modes; do not record a preference without evidence |
| Accommodation | Ask room distribution for a group | Keep room count as a scenario until confirmed |
| Sources/platforms | No | Public web plus official sources; add named platforms |
| Output | No | Concise report in chat |

Ask one question per turn in this order: destination, departure date, budget amount/scope, days, group size, then preference confirmation. After these, ask for the next material missing start/return point, fixed service or feasible departure window when needed to close a precise route. Skip known fields and accept volunteered answers to future questions. A preference inferred from “美食为主” or “想拍照” is a proposal, not an approved constraint. While awaiting an answer, research stable facts and photos, but leave the itinerary and computed package price pending. If the user wants an explicit demonstration, use a visible “假设情境” label and do not present it as the user's actual trip.

## Planning units

For a full trip, use one continuous daily route rather than one row per morning or afternoon. Read [complete-route and rich-content standard](route-timeline.md) before writing. Each day has named start/end anchors and ordered segments for travel, visits, meals, rest, check-in and return. Each segment records start/end time and place; a visit records actual play/visit minutes and at least two concrete things to see or do. Every change of place has a named transfer with duration and buffer. Keep unknown times and locations explicit so the route check can return `incomplete`.

After the timeline, explain why the route fits the user's interests, how much time each main attraction deserves, what to do there, where to eat, and what the nearby weather/closure substitute changes. Include per-person and group cost where applicable, plus reservation, access and source status. A single “上午景区、下午街区” row is an overview, not a usable itinerary.

## Complete transport record for internal plans and detailed reports

Keep “交通查询与接驳” in the internal plan and every detailed travel-plan file. Use one row per meaningful leg; cover origin access when known, intercity travel, airport/station transfer, destination arrival, daily local moves, and the return leg when within scope. In the default chat answer, show only connections that affect the traveler's immediate decision, in short bullets rather than a wide table.

| Date/leg | Exact endpoints | Mode and service | Depart–arrive / duration | Transfers and walk | Fare and inclusion | Source and query time | Buffer / status |
|---|---|---|---|---|---|---|---|

For a flight-plus-rail journey, name the airport terminal and the separate railway station. Count time from scheduled landing to train departure, then allow for deplaning, baggage, walking, security, and boarding cutoff. A map's short POI-to-POI walking time is not the full transfer time. Use 12306 alone for train facts; show seat class and availability wording. For flights, distinguish listing price from confirmed checkout total. Put access fares, local transit, and exclusions in the budget without double counting.

If the origin, travel date, exact terminal, live page, or price is missing, write “待查询/未核实” in the affected cell and identify the missing input or blocked source. Do not substitute an arbitrary future date as a real itinerary. A clearly labeled sample date is acceptable only for a scenario demonstration.

## Output templates

### Default traveler answer

Use for ordinary travel requests, including complete multi-day trips. Build and validate the full time sequence internally, then show a screen-sized first answer: one-line conclusion; one short route line per day; compact confirmed/estimated/unknown budget; up to three decision-critical checks; one next action. No Markdown table or raw JSON. Give the traveler a clear option to see the full route, visit durations, transfer legs, food/rest, prices and sources. If core inputs are missing, ask the single most important question instead of generating a long placeholder report.

### Comparison report

Use when the user asks to compare Douyin, Xiaohongshu, and browser results:

1. Research scope and access status per platform.
2. Repeated recommendations across sources.
3. Platform-specific emphasis.
4. Official verification and conflicts.
5. Final retained/removed candidates with reasons.
6. Transport query and connection table.
7. Optimized continuous daily itinerary with attraction detail and budget.

### Detailed or file-ready report

When explicitly requested, use descriptive headings, repeated table headers, currency units, page-friendly tables, a “交通查询与接驳” table, complete daily time sequences, and a final “价格与开放信息核验日期” note. Put citations or source links near the relevant sections. Do not let decorative layout hide assumptions, estimates, missing time segments or short attraction descriptions.

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

