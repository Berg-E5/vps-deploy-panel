"""Audited socket checks used by HTTPS activation and read-only access.

Go's net.Listen("tcp", "0.0.0.0:port") may expose a dual-stack wildcard
socket which iproute2 ss renders as *:port or [::]:port. A strict comparison
against "0.0.0.0:port" would falsely fail. This function only identifies a
candidate wildcard listener; TLS is separately verified over IPv4 loopback
with certificate identity validation. A bare IPv6-only listener is insufficient.
"""

PUBLIC_SOCKET_CHECK = r"""# Accept exact wildcard forms emitted by iproute2 ss.
# This is only a *candidate*: the IPv4 curl TLS probe must also pass.
vpsdeploy_public_socket() {
    vpsdeploy_port="$1"
    case "$vpsdeploy_port" in ''|*[!0-9]*) return 1 ;; esac
    ss -Hltn "sport = :$vpsdeploy_port" | awk -v p="$vpsdeploy_port" '
        {
            addr=$4
            if (addr == "0.0.0.0:" p ||
                addr == "*:" p ||
                addr == "[::]:" p ||
                addr == ":::" p) found=1
        }
        END { exit(found ? 0 : 1) }
    '
}
"""
