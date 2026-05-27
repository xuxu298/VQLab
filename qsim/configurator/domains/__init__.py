"""Configurator domain plugins. Importing this package registers all domains."""
from . import qkd, sensing, qchw, qrng  # noqa: F401  (import side effect: register_domain)
