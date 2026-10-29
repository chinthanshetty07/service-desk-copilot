import pytest

from app.guardrails import priority, redact


def test_redacts_emails_and_phone_numbers():
    text, count = redact("I'm ravi.k@acme.co.in, call +91 98450 12345 or 080-4123-4567")
    assert "acme" not in text and "98450" not in text and "4123" not in text
    assert text.count("[EMAIL]") == 1 and text.count("[PHONE]") == 2
    assert count == 3


def test_leaves_ordinary_numbers_alone():
    text, count = redact("Printer on floor 2, ticket 4521")
    assert count == 0 and text == "Printer on floor 2, ticket 4521"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("VPN is down for everyone in sales", "P1"),
        ("I clicked a link and entered my password", "P1"),
        ("my laptop was stolen", "P1"),
        ("I'm locked out of my account", "P2"),
        ("cannot log in, urgent", "P2"),
        ("please install Figma", "P3"),
    ],
)
def test_priority_rules(text, expected):
    assert priority(text) == expected
