# FitFindr

FitFindr is a small agent-style fashion assistant that takes a natural language thrift query, finds matching listings, suggests an outfit based on wardrobe context, and generates a social caption (fit card).

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Add your Groq key in `.env`:

```env
GROQ_API_KEY=your_key_here
```

3. Run tests:

```bash
python -m pytest tests/
```

4. Run app:

```bash
python app.py
```

## Tool Inventory

### 1) `search_listings(description: str, size: str | None = None, max_price: float | None = None) -> list[dict]`

- Purpose: Retrieve and rank listing matches from `data/listings.json`.
- Inputs:
	- `description` (`str`): query text matched against `title`, `description`, and `style_tags`.
	- `size` (`str | None`): optional size filter (case-insensitive; supports composite matching like `M` in `S/M`).
	- `max_price` (`float | None`): optional inclusive price cap.
- Output:
	- `list[dict]` where each listing dict includes:
		- `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`.
	- Sorted by relevance score (keyword overlap), tie-broken by lower price.
	- Empty list when no matches.

### 2) `suggest_outfit(new_item: dict, wardrobe: dict) -> str`

- Purpose: Generate a styling suggestion using the selected listing and the user wardrobe.
- Inputs:
	- `new_item` (`dict`): selected listing dict.
	- `wardrobe` (`dict`): wardrobe object with `items` list (`id`, `name`, `category`, `colors`, `style_tags`, optional `notes`).
- Output:
	- `str` containing a concise outfit suggestion.
	- Uses Groq `llama-3.3-70b-versatile`.
	- For empty wardrobe, still returns a suggestion and prepends an explicit note.

### 3) `create_fit_card(outfit: str, new_item: dict) -> str`

- Purpose: Turn outfit suggestion + listing context into a short social caption.
- Inputs:
	- `outfit` (`str`): outfit suggestion from `suggest_outfit`.
	- `new_item` (`dict`): selected listing dict.
- Output:
	- `str` caption (1-2 sentence style in implementation).
	- Uses Groq `llama-3.3-70b-versatile` with higher temperature for variation.
	- Returns a descriptive error string if `outfit` is empty.

## Planning Loop

`run_agent(query, wardrobe)` follows this branch-aware sequence:

1. Initialize session state.
2. Parse query into `description`, optional `size`, optional `max_price`.
3. Call `search_listings(...)` and store in session.
4. If results are empty: set `session["error"]`, return early, stop tool chain.
5. Otherwise select top result as `session["selected_item"]`.
6. Call `suggest_outfit(selected_item, wardrobe)` and store in `session["outfit_suggestion"]`.
7. Call `create_fit_card(outfit_suggestion, selected_item)` and store in `session["fit_card"]`.
8. Return session.

The loop is conditional, not unconditional: downstream tools are skipped on no-results.

## State Management

The app uses a single per-request `session` dict as source of truth.

- `query`: original user request.
- `parsed`: extracted `description`, `size`, `max_price`.
- `results` and `search_results`: listing results from `search_listings`.
- `selected_item`: chosen top listing dict.
- `wardrobe`: wardrobe passed into run.
- `outfit_suggestion`: output from `suggest_outfit`.
- `fit_card`: output from `create_fit_card`.
- `error`: early-return error message for branch failures.

State is passed directly between tool calls (no re-prompting and no hardcoded intermediate values).

## Error Handling

### `search_listings` no-results branch

- Behavior: return empty list.
- Agent response: set `session["error"]` with actionable guidance and return early.
- Concrete test example:
	- Query: `designer ballgown size XXS under $5`
	- Observed: `session["error"]` populated, `session["fit_card"] is None`, `suggest_outfit` call count = 0.

### `suggest_outfit` empty wardrobe

- Behavior: does not crash; still returns guidance string.
- Response format: prepends `(No wardrobe on file — here's a general styling suggestion.) ...`.
- Concrete test example:
	- Tested in `tests/test_tools.py` with `wardrobe={"items": []}` and mocked LLM client.
	- Observed: non-empty string with required prefix.

### `create_fit_card` empty outfit input

- Behavior: returns exact error string, skips LLM call.
- Concrete test example:
	- Input: `create_fit_card("", listing_dict)`
	- Output: `Unable to generate a fit card — no outfit suggestion was provided.`

## Spec Reflection

What matched the plan:

- Tool interfaces and failure behavior are implemented as described in `planning.md`.
- The planning loop branches correctly on search failure and does not run all tools unconditionally.
- Session state carries exact objects/values through the pipeline.

What was adjusted during implementation:

- Query parsing in `run_agent` is regex-based for `size` and `under $X` patterns.
- Session stores both `results` (spec name) and `search_results` (starter compatibility).
- `create_fit_card` output length is currently 1-2 sentences in practice, though starter text said 2-4.

## AI Usage

### Instance 1: Planning loop implementation in `agent.py`

- AI input provided:
	- `planning.md` Planning Loop section.
	- `planning.md` State Management section.
	- Architecture flow (session outfit flow diagram reference).
- AI output produced:
	- Initial `run_agent()` implementation with query parsing and tool orchestration.
- What I changed/overrode before using:
	- Added explicit `session["results"]` assignment to match documented spec keys.
	- Kept `search_results` for compatibility with starter session structure.
	- Verified no-results branch returns early and skips `suggest_outfit`.

### Instance 2: Tool implementations in `tools.py`

- AI input provided:
	- Tool 1/2/3 spec blocks from `planning.md` (purpose, inputs, outputs, failure modes).
	- Requirement to use `load_listings()` and Groq `llama-3.3-70b-versatile`.
- AI output produced:
	- Implementations for `search_listings`, `suggest_outfit`, `create_fit_card`.
- What I changed/overrode before using:
	- Added robust no-results/empty-input guards.
	- Confirmed `create_fit_card` uses higher temperature and tested repeated calls for output variation.
	- Added pytest coverage with mocked Groq client for deterministic tests.

## Testing Summary

- Command run: `python -m pytest tests/`
- Result: all tests passed.
- Additional runtime checks:
	- `python agent.py` happy path and no-results path.
	- Instrumented verification showed exact state handoff (`selected_item` and `outfit_suggestion`) between tool calls.
