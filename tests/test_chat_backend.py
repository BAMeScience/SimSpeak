import pytest

from simspeak.chat_backend import send_message


def test_chat_returns_string():
    response = send_message(
        "Calculate silicon using PBE",
        history=[],
    )

    assert isinstance(response, str)
    assert len(response) > 0


def test_chat_contains_user_request():
    message = "Calculate silicon using GPAW"

    response = send_message(
        message,
        history=[],
    )

    assert message in response


def test_chat_rejects_empty_message():
    with pytest.raises(ValueError):
        send_message("", history=[])


def test_chat_rejects_whitespace_message():
    with pytest.raises(ValueError):
        send_message("   ", history=[])


def test_chat_accepts_history():
    history = [
        {
            "role": "user",
            "content": "Calculate silicon",
        },
        {
            "role": "assistant",
            "content": "Request received",
        },
    ]

    response = send_message("Change the cutoff to 500 eV", history=history)

    assert isinstance(response, str)
    assert "500 eV" in response
