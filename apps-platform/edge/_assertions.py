"""Version 1 ES256 assertion issuance and verification-key publication."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Protocol, Sequence

import google_crc32c
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    Prehashed,
    decode_dss_signature,
    encode_dss_signature,
)

from contracts import validate_contract_instance

from ._identity import Clock, PlatformIdentity, TokenSource


ASSERTION_LIFETIME_SECONDS = 60
ASSERTION_CLOCK_SKEW_SECONDS = 30
JWKS_CACHE_SECONDS = 15 * 60
MAX_ASSERTION_BYTES = 4_096
MAX_JWKS_BYTES = 65_536
IDENTITY_CONTEXT_SCHEMA = (
    "urn:comfforts:app-platform:schema:verified-identity-context:v1"
)
KEY_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
KMS_VERSION_PATTERN = re.compile(
    r"projects/[^/]+/locations/us-west1/keyRings/[^/]+/cryptoKeys/[^/]+/"
    r"cryptoKeyVersions/[^/]+"
)


class AssertionUnavailable(RuntimeError):
    """Assertion signing or verification material is unavailable."""


@dataclass(frozen=True, slots=True)
class VerifiedIdentityContext:
    """The independently verifiable Version 1 claim payload."""

    contract_version: int
    issuer: str
    subject: str
    audience: str
    issued_at: int
    expires_at: int
    correlation_id: str


@dataclass(frozen=True, slots=True)
class KmsKeyVersion:
    """One public key identifier bound to an exact Cloud KMS key version."""

    key_id: str
    resource_name: str

    def __post_init__(self) -> None:
        if KEY_ID_PATTERN.fullmatch(self.key_id) is None:
            raise ValueError("invalid assertion key identifier")
        if KMS_VERSION_PATTERN.fullmatch(self.resource_name) is None:
            raise ValueError("invalid Cloud KMS key version")


class AssertionSigner(Protocol):
    @property
    def active_key_id(self) -> str: ...

    async def sign_digest(self, digest: bytes) -> bytes: ...


class VerificationKeySource(Protocol):
    async def verification_keys(self) -> tuple[dict[str, str], ...]: ...


def _encode_segment(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode_segment(value: str) -> bytes | None:
    if not value or re.fullmatch(r"[A-Za-z0-9_-]+", value) is None:
        return None
    padding = "=" * (-len(value) % 4)
    try:
        decoded = base64.b64decode(
            value + padding,
            altchars=b"-_",
            validate=True,
        )
    except (binascii.Error, ValueError, TypeError):
        return None
    return decoded if _encode_segment(decoded) == value else None


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _clock_value(clock: Clock) -> int:
    value = clock.now()
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= 253_402_300_739
    ):
        raise AssertionUnavailable("assertion clock unavailable")
    return value


def _raw_signature(der_signature: bytes) -> bytes:
    try:
        r_value, s_value = decode_dss_signature(der_signature)
        return r_value.to_bytes(32, "big") + s_value.to_bytes(32, "big")
    except (ValueError, OverflowError) as error:
        raise AssertionUnavailable("assertion signing unavailable") from error


def _der_signature(raw_signature: bytes) -> bytes:
    if len(raw_signature) != 64:
        raise ValueError("invalid ES256 signature")
    return encode_dss_signature(
        int.from_bytes(raw_signature[:32], "big"),
        int.from_bytes(raw_signature[32:], "big"),
    )


def _jwk_coordinate(value: int) -> str:
    return _encode_segment(value.to_bytes(32, "big"))


def public_jwk(
    key_id: str,
    public_key: ec.EllipticCurvePublicKey,
) -> dict[str, str]:
    """Project one P-256 public key into the bounded published JWK shape."""

    if KEY_ID_PATTERN.fullmatch(key_id) is None:
        raise ValueError("invalid assertion key identifier")
    if not isinstance(public_key.curve, ec.SECP256R1):
        raise ValueError("assertion key must use P-256")
    numbers = public_key.public_numbers()
    return {
        "alg": "ES256",
        "crv": "P-256",
        "kid": key_id,
        "kty": "EC",
        "use": "sig",
        "x": _jwk_coordinate(numbers.x),
        "y": _jwk_coordinate(numbers.y),
    }


def public_key_from_jwk(value: Mapping[str, Any]) -> ec.EllipticCurvePublicKey:
    """Parse one exact public ES256 JWK without accepting private material."""

    expected = {"alg", "crv", "kid", "kty", "use", "x", "y"}
    if set(value) != expected or any(not isinstance(item, str) for item in value.values()):
        raise ValueError("invalid public verification key")
    if (
        value["alg"] != "ES256"
        or value["crv"] != "P-256"
        or value["kty"] != "EC"
        or value["use"] != "sig"
        or KEY_ID_PATTERN.fullmatch(value["kid"]) is None
    ):
        raise ValueError("invalid public verification key")
    x_bytes = _decode_segment(value["x"])
    y_bytes = _decode_segment(value["y"])
    if x_bytes is None or y_bytes is None or len(x_bytes) != 32 or len(y_bytes) != 32:
        raise ValueError("invalid public verification key")
    return ec.EllipticCurvePublicNumbers(
        int.from_bytes(x_bytes, "big"),
        int.from_bytes(y_bytes, "big"),
        ec.SECP256R1(),
    ).public_key()


def _private_key_from_jwk(value: Mapping[str, Any]) -> ec.EllipticCurvePrivateKey:
    allowed = {"crv", "d", "kid", "kty", "x", "y"}
    if set(value) != allowed or any(not isinstance(item, str) for item in value.values()):
        raise ValueError("invalid synthetic private key")
    if value["crv"] != "P-256" or value["kty"] != "EC":
        raise ValueError("invalid synthetic private key")
    private_bytes = _decode_segment(value["d"])
    if private_bytes is None or len(private_bytes) != 32:
        raise ValueError("invalid synthetic private key")
    private_key = ec.derive_private_key(
        int.from_bytes(private_bytes, "big"),
        ec.SECP256R1(),
    )
    expected_public = public_jwk(value["kid"], private_key.public_key())
    if expected_public["x"] != value["x"] or expected_public["y"] != value["y"]:
        raise ValueError("invalid synthetic private key")
    return private_key


class InMemoryAssertionKeys:
    """Deterministic synthetic signer and verification-key source for tests."""

    def __init__(
        self,
        active_private_jwk: Mapping[str, Any],
        published_keys: Sequence[Mapping[str, Any]],
    ) -> None:
        key_id = active_private_jwk.get("kid")
        if not isinstance(key_id, str):
            raise ValueError("invalid synthetic private key")
        private_key = _private_key_from_jwk(active_private_jwk)
        public_keys: list[dict[str, str]] = []
        observed_ids: set[str] = set()
        for item in published_keys:
            candidate = dict(item)
            public_key_from_jwk(candidate)
            candidate_id = candidate["kid"]
            if candidate_id in observed_ids:
                raise ValueError("duplicate verification key identifier")
            observed_ids.add(candidate_id)
            public_keys.append(candidate)
        if key_id not in observed_ids:
            raise ValueError("active key must be published")
        if not 1 <= len(public_keys) <= 3:
            raise ValueError("invalid verification key overlap")
        expected_active_public = public_jwk(key_id, private_key.public_key())
        configured_active_public = next(
            item for item in public_keys if item["kid"] == key_id
        )
        if configured_active_public != expected_active_public:
            raise ValueError("active private and public keys do not match")
        self._active_key_id = key_id
        self._private_key = private_key
        self._public_keys = tuple(sorted(public_keys, key=lambda item: item["kid"]))
        self.available = True

    @property
    def active_key_id(self) -> str:
        return self._active_key_id

    async def sign_digest(self, digest: bytes) -> bytes:
        if not self.available or not isinstance(digest, bytes) or len(digest) != 32:
            raise AssertionUnavailable("assertion signing unavailable")
        signature = self._private_key.sign(
            digest,
            ec.ECDSA(
                Prehashed(hashes.SHA256()),
                deterministic_signing=True,
            ),
        )
        return _raw_signature(signature)

    async def verification_keys(self) -> tuple[dict[str, str], ...]:
        if not self.available:
            raise AssertionUnavailable("verification keys unavailable")
        return tuple(dict(item) for item in self._public_keys)


def _crc_value(value: Any) -> int:
    raw = getattr(value, "value", value)
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise AssertionUnavailable("Cloud KMS integrity verification failed")
    return raw


class CloudKmsAssertionKeys:
    """Cloud KMS ES256 signer and public-key source with integrity checks."""

    def __init__(
        self,
        client: Any,
        *,
        active_key: KmsKeyVersion,
        published_keys: Sequence[KmsKeyVersion],
    ) -> None:
        if not 1 <= len(published_keys) <= 3:
            raise ValueError("invalid verification key overlap")
        if len({item.key_id for item in published_keys}) != len(published_keys):
            raise ValueError("duplicate verification key identifier")
        if active_key not in published_keys:
            raise ValueError("active key must be published")
        self._client = client
        self._active_key = active_key
        self._published_keys = tuple(published_keys)

    @property
    def active_key_id(self) -> str:
        return self._active_key.key_id

    async def sign_digest(self, digest: bytes) -> bytes:
        if not isinstance(digest, bytes) or len(digest) != 32:
            raise AssertionUnavailable("assertion signing unavailable")
        try:
            response = await self._client.asymmetric_sign(
                request={
                    "name": self._active_key.resource_name,
                    "digest": {"sha256": digest},
                    "digest_crc32c": google_crc32c.value(digest),
                }
            )
            signature = bytes(response.signature)
            protection_name = getattr(
                response.protection_level,
                "name",
                str(response.protection_level),
            )
            if (
                response.name != self._active_key.resource_name
                or not response.verified_digest_crc32c
                or protection_name != "SOFTWARE"
                or _crc_value(response.signature_crc32c)
                != google_crc32c.value(signature)
            ):
                raise AssertionUnavailable("Cloud KMS integrity verification failed")
            return _raw_signature(signature)
        except AssertionUnavailable:
            raise
        except Exception as error:
            raise AssertionUnavailable("assertion signing unavailable") from error

    async def verification_keys(self) -> tuple[dict[str, str], ...]:
        keys: list[dict[str, str]] = []
        try:
            for key in self._published_keys:
                response = await self._client.get_public_key(
                    request={"name": key.resource_name}
                )
                pem = response.pem.encode("ascii")
                algorithm_name = getattr(response.algorithm, "name", str(response.algorithm))
                protection_name = getattr(
                    response.protection_level,
                    "name",
                    str(response.protection_level),
                )
                if (
                    response.name != key.resource_name
                    or algorithm_name != "EC_SIGN_P256_SHA256"
                    or protection_name != "SOFTWARE"
                    or _crc_value(response.pem_crc32c) != google_crc32c.value(pem)
                ):
                    raise AssertionUnavailable(
                        "Cloud KMS integrity verification failed"
                    )
                public_key = serialization.load_pem_public_key(pem)
                if not isinstance(public_key, ec.EllipticCurvePublicKey):
                    raise AssertionUnavailable("verification keys unavailable")
                keys.append(public_jwk(key.key_id, public_key))
        except AssertionUnavailable:
            raise
        except Exception as error:
            raise AssertionUnavailable("verification keys unavailable") from error
        return tuple(sorted(keys, key=lambda item: item["kid"]))


class AssertionIssuer:
    """Issue one minimized, application-bound Version 1 assertion."""

    def __init__(
        self,
        signer: AssertionSigner,
        clock: Clock,
        correlation_ids: TokenSource,
    ) -> None:
        self._signer = signer
        self._clock = clock
        self._correlation_ids = correlation_ids

    async def issue(
        self,
        identity: PlatformIdentity,
        audience: str,
        correlation_id: str | None = None,
    ) -> str:
        if not isinstance(identity, PlatformIdentity):
            raise AssertionUnavailable("identity assertion unavailable")
        issued_at = _clock_value(self._clock)
        context = VerifiedIdentityContext(
            contract_version=1,
            issuer=identity.issuer,
            subject=identity.subject,
            audience=audience,
            issued_at=issued_at,
            expires_at=issued_at + ASSERTION_LIFETIME_SECONDS,
            correlation_id=(
                correlation_id
                if correlation_id is not None
                else self._correlation_ids.token(24)
            ),
        )
        payload = asdict(context)
        if validate_contract_instance(payload, IDENTITY_CONTEXT_SCHEMA):
            raise AssertionUnavailable("identity assertion unavailable")
        header = {
            "alg": "ES256",
            "kid": self._signer.active_key_id,
            "typ": "JWT",
        }
        signing_input = (
            _encode_segment(_canonical_json(header))
            + "."
            + _encode_segment(_canonical_json(payload))
        )
        signature = await self._signer.sign_digest(
            hashlib.sha256(signing_input.encode("ascii")).digest()
        )
        if not isinstance(signature, bytes) or len(signature) != 64:
            raise AssertionUnavailable("identity assertion unavailable")
        assertion = signing_input + "." + _encode_segment(signature)
        if len(assertion.encode("ascii")) > MAX_ASSERTION_BYTES:
            raise AssertionUnavailable("identity assertion unavailable")
        return assertion


def verify_es256_signature(
    public_key: ec.EllipticCurvePublicKey,
    signing_input: bytes,
    raw_signature: bytes,
) -> bool:
    """Verify a raw JWS ES256 signature against one P-256 public key."""

    try:
        public_key.verify(
            _der_signature(raw_signature),
            hashlib.sha256(signing_input).digest(),
            ec.ECDSA(Prehashed(hashes.SHA256())),
        )
    except (InvalidSignature, ValueError):
        return False
    return True
