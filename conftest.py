"""Offline release validation: never contact external websites or deliver email during tests."""
import ipaddress
import socket

import pytest


_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _is_loopback_address(address) -> bool:
    """Allow only local loopback sockets needed by the Windows asyncio runtime."""
    if not isinstance(address, tuple) or not address:
        return False

    host = str(address[0]).strip().lower()

    if host in _LOOPBACK_HOSTS:
        return True

    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def block_external_network(monkeypatch):
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create_connection = socket.create_connection

    def guarded_connect(self, address):
        if _is_loopback_address(address):
            return original_connect(self, address)
        raise OSError(
            "Offline scanner validation: external network disabled"
        )

    def guarded_connect_ex(self, address):
        if _is_loopback_address(address):
            return original_connect_ex(self, address)
        raise OSError(
            "Offline scanner validation: external network disabled"
        )

    def guarded_create_connection(address, *args, **kwargs):
        if _is_loopback_address(address):
            return original_create_connection(address, *args, **kwargs)
        raise OSError(
            "Offline scanner validation: external network disabled"
        )

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "create_connection", guarded_create_connection)

    # Prevent real email delivery during tests.
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    