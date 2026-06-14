from types import SimpleNamespace

import tools
from tools import create_fit_card, search_listings, suggest_outfit


def _fake_groq_client(response_text: str):
    class _FakeCompletions:
        @staticmethod
        def create(**kwargs):
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=response_text)
                    )
                ]
            )

    class _FakeChat:
        completions = _FakeCompletions()

    return SimpleNamespace(chat=_FakeChat())


def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_suggest_outfit_empty_wardrobe(monkeypatch):
    monkeypatch.setattr(
        tools,
        "_get_groq_client",
        lambda: _fake_groq_client("Keep it simple with straight jeans and clean sneakers."),
    )

    new_item = {
        "title": "Faded Band Tee",
        "category": "tops",
        "colors": ["black"],
        "style_tags": ["vintage", "graphic tee"],
    }
    wardrobe = {"items": []}

    result = suggest_outfit(new_item, wardrobe)
    assert isinstance(result, str)
    assert result
    assert result.startswith("(No wardrobe on file")


def test_create_fit_card_empty_outfit_returns_error_message():
    result = create_fit_card("   ", {"title": "Faded Band Tee", "price": 22, "platform": "depop"})
    assert result == "Unable to generate a fit card — no outfit suggestion was provided."


def test_create_fit_card_returns_caption(monkeypatch):
    monkeypatch.setattr(
        tools,
        "_get_groq_client",
        lambda: _fake_groq_client("thrifted this tee and built the whole fit around it."),
    )

    result = create_fit_card(
        "Pair this with wide-leg jeans and chunky sneakers.",
        {"title": "Faded Band Tee", "price": 22, "platform": "depop"},
    )

    assert isinstance(result, str)
    assert result.strip() != ""
