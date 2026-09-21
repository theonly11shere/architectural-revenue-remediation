"""Offline validation: allow numeric loopback for asyncio, block remote services."""
import ipaddress
import socket
import pytest


def _is_loopback(address):
    """Accept literal loopback IPs only; never resolve a hostname to allow it."""
    if not isinstance(address, tuple) or not address or not isinstance(address[0], str):
        return False
    try:
        return ipaddress.ip_address(address[0]).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def block_external_network(monkeypatch):
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create_connection = socket.create_connection

    def require_loopback(address):
        if not _is_loopback(address):
            raise OSError('Offline scanner validation: external network disabled')

    def guarded_connect(sock, address):
        require_loopback(address)
        return original_connect(sock, address)

    def guarded_connect_ex(sock, address):
        require_loopback(address)
        return original_connect_ex(sock, address)

    def guarded_create_connection(address, *args, **kwargs):
        require_loopback(address)
        return original_create_connection(address, *args, **kwargs)

    # On Windows, asyncio's socketpair uses a loopback TCP connection.
    monkeypatch.setattr(socket.socket, 'connect', guarded_connect)
    monkeypatch.setattr(socket.socket, 'connect_ex', guarded_connect_ex)
    monkeypatch.setattr(socket, 'create_connection', guarded_create_connection)
    monkeypatch.delenv('RESEND_API_KEY', raising=False)
