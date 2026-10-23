"""Token estimation.

Uses tiktoken when it works; otherwise falls back to a rough
approximation (about 4 characters per token). The result is an
ESTIMATE, used for context scoring and cost calculation, not an
exact count for any specific model.
"""

from functools import lru_cache

CHARS_PER_TOKEN = 4  # rough rule of thumb for English text


@lru_cache(maxsize=1)
def _get_encoder():
    """Load the tiktoken encoder once. Returns None if unavailable."""
    try:
        import tiktoken

        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        # tiktoken not installed, or its data could not be downloaded
        return None


def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in `text`. Empty text returns 0."""
    if not text:
        return 0

    encoder = _get_encoder()
    if encoder is not None:
        try:
            return len(encoder.encode(text))
        except Exception:
            pass  # fall through to the approximation

    return max(1, len(text) // CHARS_PER_TOKEN)