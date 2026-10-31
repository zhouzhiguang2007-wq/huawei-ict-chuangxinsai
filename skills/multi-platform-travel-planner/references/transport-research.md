# Multi-Source Transport Research

Read this reference when a travel plan contains railway travel, flights, coaches, ferries, airport or station transfers, local public transit, driving, cycling, walking, live traffic, or route-cost comparisons.

The goal is a feasible door-to-door movement plan. A route is not complete merely because a platform shows a line between two places; it must use the correct terminal, fit the operating window, include transfers and walking, and preserve enough buffer for the traveler.

## 1. Collect the transport request

Resolve the following before a live search when they materially affect the result:

- Origin and destination, including the exact station, airport, terminal, attraction, or accommodation when known.
- Travel date and preferred departure or arrival window.
- Earliest feasible time the traveler can actually leave on the departure date, or explicit confirmation that the day is flexible. A date alone supplies no time window.
- Party size, child/student/senior status only when relevant to an estimate, and luggage burden.
- Mobility limits, transfer tolerance, maximum walking distance, and acceptable modes.
- Whether the budget includes intercity travel and whether overnight travel is acceptable.

If a named origin or return point maps to several real places, present distinct candidate names and addresses and ask the traveler to select the intended one when the choice changes the route, time, cost or a hard deadline. This applies to campuses, hospital sites, chain-store branches, same-name POIs, stations and entrances. A map's first result or popularity ranking is not user confirmation. Preserve the user's raw place name and the selected provider POI ID separately. If unresolved, leave the affected access route, earliest departure, access cost and arrival-by deadline unknown; any broader itinerary must be labeled provisional. Do not interrupt a city-level inspiration request for an immaterial entrance detail.

Do not guess a railway date, city station, or airport when multiple choices would produce materially different results. A past or missing date cannot support a live booking claim: ask for a future date when essential, or use a clearly labeled illustrative date for a scenario and leave the actual itinerary unconfirmed. Prefer a named terminal over a city centroid.

If departure availability is unknown, ask before recommending a specific outbound train or leave-home time. A map estimate from home to station can be calculated as a duration, but cannot establish that the traveler is free at 06:30 or any other chosen time.

## 2. Assign each source a role

| Source | Use it for | Do not use it for |
|---|---|---|
| China Railway 12306 | China railway train numbers, origin/destination stations, schedules, duration, seat classes, fares, remaining tickets, sale times, delay/status and railway ticket rules | Local navigation, flights, coaches, ferries, or unverified resale offers |
| Amap/Gaode | Primary mainland-China POI matching, walking, cycling, driving, public-transit routes, distance, estimated duration and traffic-aware routing | Authoritative railway availability or fare |
| Baidu Maps | Mainland-China POI/station-exit cross-check, walking/driving/transit alternatives, route duration and traffic context | Authoritative railway availability or fare |
| Tencent Maps | Additional mainland-China POI, route and live-traffic cross-check when accessible | Authoritative railway availability or fare |
| Google Maps | International routes and a secondary geographic cross-check; use cautiously where mainland-China coverage or service availability differs | Sole authority for mainland-China public transit, traffic or railway data |
| Ctrip/Trip.com | Flights, hotels, airport transfers and non-rail transport listings on public browser pages | Any railway schedule, fare, remaining-ticket or recommendation in this skill |
| Tongcheng | Flights, coaches, ferries, transfers and price discovery from accessible public pages | Any railway schedule, fare, remaining-ticket or recommendation in this skill |
| Official operator | Metro/bus/airport/coach/ferry timetables, closures, first/last service, boarding and baggage rules | Replacing 12306 for China railway ticket data |

Search social platforms only for practical observations such as a confusing exit, long security queue, difficult uphill walk, or common taxi pickup point. Verify operational facts elsewhere.

## 3. Enforce the 12306 railway boundary

### Automatic lookup gate

Once the actual travel date, origin and destination are known, check both outbound and return railway legs **during this turn**, before choosing train-dependent activities or handing the result to the traveler. When a preferred time window is missing, query all-day options first, but ask the traveler for their available period before selecting a train or fixing the day's schedule. The user does not need to repeat a command to look up tickets. First inspect the tools available in the current runtime: use a browser/page-operation tool to open an official 12306 surface if available. An Amap MCP can resolve station access, but cannot verify railway trains, fares or seats. A repository Skill, RAG instruction, or open browser tab by itself does not grant the agent the ability to operate that page.

For each leg, record `lookup_status` as `verified`, `no_result`, `blocked`, `tool_unavailable`, or `needs_station_clarification`, plus `queried_at`, official URL/surface and actual station pair when known. `verified` requires a successful official result for the requested date and station pair. `no_result` means the official search ran and returned no matching service; it is not the same as failure to access the page. If the page fails, retry at most once using another official 12306 surface or simplified station/date search, then stop and record the concrete reason. Never claim to have searched 12306 merely because a general web search returned its homepage or a snippet.

If no official result is available, preserve the itinerary as provisional and leave the train-dependent departure/arrival, fare and seats unknown. A rough corridor duration may be shown only as an explicitly labeled planning estimate with its basis; never present it as a train time or use it to prove a connection. Do not tell the traveler only “请自行查询12306” while showing a precise unverified rail block. Give a single next action only when the agent truly lacks official lookup access or an essential station choice, and explain which missing fact prevents a final schedule.

For every railway query:

1. Use only an official `12306.cn`, `kyfw.12306.cn`, or `mobile.12306.cn` page or an explicitly verified official 12306 application surface.
2. Require origin, destination, and travel date for availability. Resolve the exact station names before comparing trains.
3. On a city-wide result page, inspect the actual origin and destination stations shown in each row; filter to the intended pair. A query header such as “郑州东→开封北” can still list “新郑机场→开封” trains after city expansion. Distinguish “机场→开封北无车” from “机场→开封站有车”.
4. Record the query timestamp in China Standard Time and distinguish scheduled data from live remaining-ticket status.
5. Capture train number, departure/arrival station and time, duration, seat class, displayed fare, availability wording, and transfer count.
6. State that remaining tickets and fares can change before payment. When 12306 indicates that station announcements or checkout prevail, preserve that qualification.
7. For delays, platform/gate, temporary suspension, or same-day disruption, prefer the relevant live 12306 function and station announcement.

Never call or quote a Ctrip/Trip.com, Tongcheng, map, social, or search-engine train result as railway evidence. If 12306 is inaccessible, blocked by login/CAPTCHA, outside its service window, or returns no usable result, report that limitation and leave railway values blank. Do not silently substitute another source.

Do not automate account registration, passenger identity entry, CAPTCHA solving, order submission, payment, refund, or rescheduling unless the user explicitly requests an allowed action and the environment provides a supported confirmation flow. Never place identity-document numbers, phone numbers, passenger names, or payment data in logs or generated reports.

## 4. Query map routes safely

For mainland-China routes, prefer Amap as the primary estimate and use Baidu or Tencent Maps when a second estimate can expose POI ambiguity, station-exit differences, or live-traffic variation. Use Google Maps primarily for international trips or as a clearly labeled secondary reference.

Use an already connected and authorized Amap MCP for map research when available; otherwise use public browser route pages. Confirm that the resolved place is the intended station, airport terminal, or destination rather than a similarly named company or city centroid. Map results do not verify 12306 railway facts.

Map providers use different coordinate systems and POI identifiers. Do not directly combine raw coordinates from Amap/Tencent, Baidu, and Google without a documented conversion. Prefer verified place names, provider POI IDs, station exits, and route-level distance/time results.

For every useful route candidate, capture:

- Exact origin and destination names as resolved by the provider.
- Mode: walking, cycling, public transit, taxi/ride-hail estimate, driving, coach, ferry, or flight transfer.
- Distance, estimated duration, departure/arrival time when available, transfers, walking distance, and fare/toll estimate.
- First/last service or operating window when the route depends on it.
- Traffic basis and query time for traffic-sensitive driving estimates.
- Accessibility, luggage, late-night, weather, and station-exit concerns.

Map estimates are snapshots. Do not present a traffic-aware duration as a guaranteed arrival time. For a high-consequence connection, plan against the slower credible estimate and add terminal-specific buffer. An airport POI-to-rail-station walk such as 161 m/3 min describes map geometry only; include deplaning, baggage claim, terminal navigation, railway security, and boarding cutoff before recommending a train.

## 5. Use travel platforms without blurring authority

Use Ctrip/Trip.com or Tongcheng public browser pages for supported flight, hotel, coach, ferry, or transfer searches when accessible. Never invoke either platform's train-search feature under this workflow.

For flights, compare at least route, date, airport/terminal, departure and arrival time, elapsed duration, transfer cities, baggage inclusion when exposed, and current displayed fare. Treat OTA fares as listing snapshots; do not call a displayed “¥260起” a payable total until checkout fees and optional packages are confirmed. Do not start a booking merely to obtain a quote. Prefer airline or airport notices for cancellations, terminal changes, and baggage rules.

For coaches and ferries, verify the correct terminal, service date, operating company, boarding cutoff, baggage restrictions, and weather-related suspension risk. Prefer the operator's notice over an older OTA listing.

## 6. Resolve source conflicts

Use this authority order for conflicts:

1. Current official warning, closure, or operator notice.
2. 12306 for all China railway facts.
3. Official metro, bus, airport, coach, ferry, road, or airline source for its own service.
4. A recently queried map provider for route geometry and traffic-aware estimates.
5. Ctrip/Trip.com or Tongcheng for supported non-rail commercial inventory.
6. Social posts and search snippets as weak context only.

When map providers disagree materially, confirm that they resolved the same POIs, terminals, and travel mode. Preserve a range rather than choosing the shortest estimate without evidence.

## 7. Build a transport matrix

Before writing the itinerary, compare meaningful options in this structure:

| Segment | Mode/provider | Depart-arrive | Duration | Transfers/walk | Fare estimate | Source time | Decision |
|---|---|---|---:|---|---:|---|---|

Select the option that best fits the user's budget, time, luggage, mobility, and risk tolerance. Do not optimize only for the lowest headline fare; include airport/station access, baggage, local transfers, waiting time, and possible overnight costs.

For door-to-door comparison, calculate:

`total travel time = access + check-in/security/wait + main journey + transfer + exit + final connection`

`total transport cost = main fare + access + local transfers + baggage/seat fees + tolls + reasonable contingency`

Keep estimates labeled and show the basis for quantities.

## 8. Convert research into the itinerary

For each travel block, state:

1. Exact start and end point.
2. Recommended mode and route summary.
3. Departure target, expected arrival, and buffer.
4. Transfers, walking burden, station exit or terminal when verified.
5. Estimated cost and what it includes.
6. Source link, query timestamp, and verification status.
7. A nearby or same-corridor fallback when a service is disrupted.

Keep this full transport chain in the internal plan and any detailed travel-plan report as a “交通查询与接驳” table, including origin access when known, outbound and return intercity legs when in scope, airport/station transfers, destination arrival, and consequential daily local legs. The default traveler-facing chat answer summarizes only the legs that affect the immediate decision. Keep unknown rows or cells in the full record marked “待查询/未核实”; never omit them because live prices are unavailable. Show listed transport subtotal, excluded fees, and its relation to the overall trip budget without double counting.

Refresh live traffic shortly before departure. Refresh railway availability on 12306 before making a purchase decision, and never reuse an earlier trip's remaining-ticket result.

## 9. Stop conditions and fallbacks

After two failed attempts on the same source and query, change the access method, simplify the query, or move to another permitted source. Do not loop on login, CAPTCHA, or blocked pages.

Fallbacks must respect source boundaries:

- Map page unavailable: try another public map route page for an estimate.
- Ctrip/Trip.com unavailable: use airline/operator sources or Tongcheng for non-rail products.
- Tongcheng unavailable: use Ctrip/Trip.com or the official non-rail operator.
- 12306 unavailable: report that railway data could not be verified; do not use any third-party railway source.

Label inaccessible or stale data instead of manufacturing a value.

