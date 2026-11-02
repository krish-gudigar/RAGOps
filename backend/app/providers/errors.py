"""Errors raised by providers. The messages are written for the person using the app."""


class ProviderError(Exception):
    """A model provider could not produce an answer (not running, model missing, timeout...)."""