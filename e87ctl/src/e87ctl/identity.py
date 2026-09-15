from __future__ import annotations

import base64
import hashlib
import re
from typing import NewType

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

InstallationId = NewType("InstallationId", str)

_INSTALLATION_ID_DOMAIN = b"e87canbus-installation-v1\0"
_INSTALLATION_ID_PATTERN = re.compile(r"[a-z2-7]{52}")


def derive_installation_id(public_key: ec.EllipticCurvePublicKey) -> InstallationId:
    if not isinstance(public_key.curve, ec.SECP256R1):
        raise ValueError("the installation authority must use P-256")
    subject_public_key = public_key.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    digest = hashlib.sha256(_INSTALLATION_ID_DOMAIN + subject_public_key).digest()
    return InstallationId(base64.b32encode(digest).decode("ascii").rstrip("=").lower())


def parse_installation_id(value: str) -> InstallationId:
    if _INSTALLATION_ID_PATTERN.fullmatch(value) is None:
        raise ValueError("invalid installation ID")
    return InstallationId(value)
