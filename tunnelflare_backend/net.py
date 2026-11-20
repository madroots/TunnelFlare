"""Networking helpers shared by code that talks HTTPS with the standard library."""

import os
import ssl

# Frozen builds carry the build host's OpenSSL, whose compiled-in CA paths may not
# exist on the user's machine. These are the common system bundles to fall back to.
_CA_BUNDLES = (
    "/etc/ssl/cert.pem",  # macOS, Alpine, Arch
    "/etc/ssl/certs/ca-certificates.crt",  # Debian, Ubuntu
    "/etc/pki/tls/certs/ca-bundle.crt",  # Fedora, RHEL
    "/etc/ssl/ca-bundle.pem",  # openSUSE
)


def ssl_context():
    """Default verifying SSL context, with a system CA bundle loaded when OpenSSL found none."""
    context = ssl.create_default_context()
    if not context.get_ca_certs():
        for bundle in _CA_BUNDLES:
            if os.path.isfile(bundle):
                context.load_verify_locations(cafile=bundle)
                break
    return context
