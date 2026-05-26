"""Configurator domain plugins. Importing this package registers all domains."""
from . import qkd, sensing, qchw  # noqa: F401  (import side effect: register_domain)
