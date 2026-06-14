"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()

    def _tokenize(text: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", text.lower()))

    def _size_matches(listing_size: str, requested_size: str) -> bool:
        listing_norm = listing_size.strip().lower()
        requested_norm = requested_size.strip().lower()

        if listing_norm == requested_norm:
            return True

        # Allow exact token matches in composite sizes, e.g. "M" matches "S/M".
        listing_tokens = re.split(r"[^a-z0-9]+", listing_norm)
        return requested_norm in {token for token in listing_tokens if token}

    query_terms = _tokenize(description or "")
    scored_matches: list[tuple[int, dict]] = []

    for listing in listings:
        if max_price is not None and float(listing.get("price", 0.0)) > max_price:
            continue

        if size is not None and not _size_matches(str(listing.get("size", "")), size):
            continue

        searchable_text = " ".join(
            [
                str(listing.get("title", "")),
                str(listing.get("description", "")),
                " ".join(str(tag) for tag in listing.get("style_tags", [])),
            ]
        )
        listing_terms = _tokenize(searchable_text)
        score = len(query_terms & listing_terms)

        if score > 0:
            scored_matches.append((score, listing))

    scored_matches.sort(key=lambda pair: (-pair[0], float(pair[1].get("price", 0.0))))
    return [listing for _, listing in scored_matches]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    client = _get_groq_client()

    title = str(new_item.get("title", "this item"))
    category = str(new_item.get("category", "item"))
    colors = ", ".join(str(c) for c in new_item.get("colors", [])) or "unspecified"
    style_tags = ", ".join(str(t) for t in new_item.get("style_tags", [])) or "unspecified"

    wardrobe_items = []
    if isinstance(wardrobe, dict):
        raw_items = wardrobe.get("items", [])
        if isinstance(raw_items, list):
            wardrobe_items = raw_items

    is_empty_wardrobe = len(wardrobe_items) == 0

    if is_empty_wardrobe:
        user_prompt = (
            "The user has no wardrobe items saved yet. "
            "Give a practical 2-3 sentence styling suggestion for the thrifted item below. "
            "Be specific about silhouette, shoes, and one styling detail.\n\n"
            f"Item title: {title}\n"
            f"Category: {category}\n"
            f"Colors: {colors}\n"
            f"Style tags: {style_tags}\n"
        )
    else:
        formatted_wardrobe = []
        for item in wardrobe_items:
            name = str(item.get("name", "Unnamed item"))
            item_category = str(item.get("category", "unknown"))
            item_colors = ", ".join(str(c) for c in item.get("colors", [])) or "unspecified"
            item_tags = ", ".join(str(t) for t in item.get("style_tags", [])) or "unspecified"
            notes = item.get("notes")
            notes_text = f"; notes: {notes}" if notes else ""
            formatted_wardrobe.append(
                f"- {name} ({item_category}; colors: {item_colors}; tags: {item_tags}{notes_text})"
            )

        user_prompt = (
            "Create a 2-3 sentence outfit suggestion that uses the new thrifted item "
            "and references specific named wardrobe pieces from the list. "
            "Keep tone friendly and style-forward, and include one actionable styling tip.\n\n"
            f"New item title: {title}\n"
            f"New item category: {category}\n"
            f"New item colors: {colors}\n"
            f"New item style tags: {style_tags}\n\n"
            "Wardrobe items:\n"
            + "\n".join(formatted_wardrobe)
        )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a personal stylist. Provide concise, specific outfit advice. "
                        "Return plain text only."
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
        )
        suggestion = (response.choices[0].message.content or "").strip()
    except Exception:
        suggestion = (
            f"Try styling {title} with relaxed bottoms and clean sneakers for a balanced look. "
            "Add one layer and keep accessories minimal for a cohesive finish."
        )

    if not suggestion:
        suggestion = (
            f"Try styling {title} with relaxed bottoms and clean sneakers for a balanced look. "
            "Add one layer and keep accessories minimal for a cohesive finish."
        )

    if is_empty_wardrobe:
        return f"(No wardrobe on file — here's a general styling suggestion.) {suggestion}"

    return suggestion


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    if not outfit or not outfit.strip():
        return "Unable to generate a fit card — no outfit suggestion was provided."

    client = _get_groq_client()

    title = str(new_item.get("title", "this thrift find"))
    price = new_item.get("price")
    price_text = f"${float(price):.2f}" if price is not None else "an unknown price"
    platform = str(new_item.get("platform", "a resale app"))

    user_prompt = (
        "Write one short social caption (1-2 sentences) for an outfit post. "
        "Sound casual and authentic, not promotional. "
        "Mention the item title once, the price once, and the platform once. "
        "Use the outfit vibe details naturally. Return plain text only.\n\n"
        f"Item title: {title}\n"
        f"Price: {price_text}\n"
        f"Platform: {platform}\n"
        f"Outfit suggestion: {outfit.strip()}\n"
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=1.0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write concise, stylish social captions for fashion outfits. "
                        "Keep it specific and natural."
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
        )
        caption = (response.choices[0].message.content or "").strip()
    except Exception:
        caption = (
            f"Thrifted {title} on {platform} for {price_text} and built the whole look around it. "
            "The fit came together perfectly with this vibe."
        )

    if not caption:
        caption = (
            f"Thrifted {title} on {platform} for {price_text} and built the whole look around it. "
            "The fit came together perfectly with this vibe."
        )

    return caption
