from __future__ import annotations

import ssl

import certifi


def build_ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())
