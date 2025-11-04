"""did:peer:2 implementation."""
from base64 import urlsafe_b64decode, urlsafe_b64encode
from base58 import b58encode
from dataclasses import dataclass
from enum import Enum
import json
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple
from hashlib import sha256


# Regex
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
PATTERN = re.compile(rf"^did:peer:2(\.[AEVID]z[{B58}]+|\.S[A-Za-z0-9_-]+)+$")
PEER3_PATTERN = re.compile(rf"^did:peer:3zQm[{B58}]{{44}}$")

# Multiformats
MULTIBASE_BASE58_BTC = "z"
MULTIHASH_SHA256 = b"\x12\x20"


class PurposeCode(Enum):
    """Purpose codes for did:peer:2."""

    assertion = "A"
    key_agreement = "E"
    authentication = "V"
    capability_invocation = "I"
    capability_delegation = "D"
    service = "S"

    @property
    def verification_relationship(self) -> str:
        """Convert the purpose code to a verification relationship."""
        return {
            "A": "assertionMethod",
            "E": "keyAgreement",
            "V": "authentication",
            "I": "capabilityInvocation",
            "D": "capabilityDelegation",
        }[self.value]

    @classmethod
    def key_purposes(cls):
        """Return a list of purpose codes that correspond to keys."""
        return (
            PurposeCode.assertion,
            PurposeCode.key_agreement,
            PurposeCode.authentication,
            PurposeCode.capability_invocation,
            PurposeCode.capability_delegation,
        )


class ServiceEncoder:
    """Encoder for did:peer:2 services."""

    common_string_abbreviations = {
        "type": "t",
        "DIDCommMessaging": "dm",
        "serviceEndpoint": "s",
        "routingKeys": "r",
        "accept": "a",
    }

    reverse_common_string_abbreviations = {
        v: k for k, v in common_string_abbreviations.items()
    }

    def _abbreviate_service(self, service: Dict[str, Any]) -> Dict[str, Any]:
        """Recursivley replace common strings with abbreviations.

        This method will replace keys in the service dictionary with their
        abbreviations as outlined in the Common String Abbreviations. The type of
        the service will also be abbreviated, if applicable.
        """
        service = {
            self.common_string_abbreviations.get(k, k): v for k, v in service.items()
        }
        if "t" in service:
            service["t"] = self.common_string_abbreviations.get(
                service["t"], service["t"]
            )

        for k, v in service.items():
            if isinstance(v, dict):
                service[k] = self._abbreviate_service(v)
            if isinstance(v, list):
                service[k] = [
                    self._abbreviate_service(e) if isinstance(e, dict) else e for e in v
                ]

        return service

    def _expand_service(self, service: Dict[str, Any]) -> Dict[str, Any]:
        """Reverse the abbreviations in a service dictionary.

        This method will perform the inverse of abbreviate_service, replacing
        abbreviations with their full string.
        """
        service = {
            self.reverse_common_string_abbreviations.get(k, k): v
            for k, v in service.items()
        }
        if "type" in service:
            service["type"] = self.reverse_common_string_abbreviations.get(
                service["type"], service["type"]
            )

        for k, v in service.items():
            if isinstance(v, dict):
                service[k] = self._expand_service(v)
            if isinstance(v, list):
                service[k] = [
                    self._expand_service(e) if isinstance(e, dict) else e for e in v
                ]

        return service

    def _bytes_to_b64(self, data: bytes) -> str:
        """Encode bytes to base64url, without padding."""
        return urlsafe_b64encode(data).decode("utf-8").rstrip("=")

    def _b64_to_bytes(self, data: str) -> bytes:
        """Decode unpadded base64url to bytes."""
        return urlsafe_b64decode(data + "=" * (-len(data) % 4))

    def encode_service(self, service: Dict[str, Any]) -> str:
        """Encode a service dictionary into a string."""
        return self._bytes_to_b64(
            json.dumps(self._abbreviate_service(service), separators=(",", ":")).encode(
                "utf-8"
            )
        )

    def decode_service(self, data: str) -> Dict[str, Any]:
        """Decode a service string into a dictionary."""
        return self._expand_service(json.loads(self._b64_to_bytes(data).decode("utf-8")))


MultikeyEncodedKey = str


@dataclass
class KeySpec:
    """Key specification for did:peer:2."""

    purpose: PurposeCode
    material: MultikeyEncodedKey

    @classmethod
    def assertion(cls, material: str) -> "KeySpec":
        """Create a key spec for assertion purposes."""
        return cls(PurposeCode.assertion, material)

    @classmethod
    def key_agreement(cls, material: str) -> "KeySpec":
        """Create a key spec for key agreement purposes."""
        return cls(PurposeCode.key_agreement, material)

    @classmethod
    def encryption(cls, material: str) -> "KeySpec":
        """Create a key spec for key agreement purposes."""
        return cls(PurposeCode.key_agreement, material)

    @classmethod
    def authentication(cls, material: str) -> "KeySpec":
        """Create a key spec for authentication purposes."""
        return cls(PurposeCode.authentication, material)

    @classmethod
    def verification(cls, material: str) -> "KeySpec":
        """Create a key spec for authentication purposes."""
        return cls(PurposeCode.authentication, material)

    @classmethod
    def capability_invocation(cls, material: str) -> "KeySpec":
        """Create a key spec for capability invocation purposes."""
        return cls(PurposeCode.capability_invocation, material)

    @classmethod
    def capability_delegation(cls, material: str) -> "KeySpec":
        """Create a key spec for capability delegation purposes."""
        return cls(PurposeCode.capability_delegation, material)


def generate(keys: Sequence[KeySpec], services: Sequence[Dict[str, Any]]):
    """Generate a did:peer:2 DID from keys and services.

    This method will generate a did:peer:2 DID from the provided keys and services.

    Key material in the keys parameter must be multibase encoded keys.
    """
    enocded_keys = "".join([f".{key.purpose.value}{key.material}" for key in keys])
    service_encoder = ServiceEncoder()
    encoded_services = "".join(
        [
            f".{PurposeCode.service.value}" + service_encoder.encode_service(service)
            for service in services
        ]
    )
    return f"did:peer:2{enocded_keys}{encoded_services}"


def _get_elements(did: str) -> Tuple[List[KeySpec], List[Dict[str, Any]]]:
    """Get the elements of a did:peer:2 DID."""
    elements = did.split(".")[1:]

    keys: List[KeySpec] = []
    service_encoder = ServiceEncoder()
    services: List[Dict[str, Any]] = []

    for element in elements:
        purpose = PurposeCode(element[0])
        value = element[1:]
        if purpose in PurposeCode.key_purposes():
            keys.append(KeySpec(purpose, value))
        else:
            assert purpose == PurposeCode.service
            services.append(service_encoder.decode_service(value))

    return keys, services


def _elements_to_document(did: str, keys: List[KeySpec], services: List[Dict[str, Any]]):
    """Construct a DID Document from the given did, keys, and services."""
    document = {}
    document["@context"] = [
        "https://www.w3.org/ns/did/v1",
        "https://w3id.org/security/multikey/v1",
    ]
    document["id"] = did

    for index, key in enumerate(keys, start=1):
        verification_method = {
            "type": "Multikey",
            "id": f"#key-{index}",
            "controller": did,
            "publicKeyMultibase": key.material,
        }
        document.setdefault("verificationMethod", []).append(verification_method)
        document.setdefault(key.purpose.verification_relationship, []).append(
            f"#key-{index}"
        )

    unidentified_index = 0
    for service in services:
        if "id" not in service:
            if unidentified_index == 0:
                service["id"] = "#service"
            else:
                service["id"] = f"#service-{unidentified_index}"
            unidentified_index += 1
        document.setdefault("service", []).append(service)

    return document


def resolve(did: str) -> Dict[str, Any]:
    """Resolve a did:peer:2 DID."""
    if not PATTERN.match(did):
        raise ValueError(f"Invalid did:peer:2: {did}")

    keys, services = _get_elements(did)
    document = _elements_to_document(did, keys, services)
    document["alsoKnownAs"] = [peer2to3(did)]

    return document


def peer2to3(did: str) -> str:
    """Derive a did:peer:3 DID from a did:peer:2 DID."""
    if not PATTERN.match(did):
        raise ValueError(f"Invalid did:peer:2: {did}")

    raw = MULTIHASH_SHA256 + sha256(did[10:].encode()).digest()
    return "did:peer:3" + MULTIBASE_BASE58_BTC + b58encode(raw).decode()


def resolve_peer3(peer2: str, peer3: Optional[str] = None) -> Dict[str, Any]:
    """Resolve a did:peer:3 document from a did:peer:2 DID."""
    if not PATTERN.match(peer2):
        raise ValueError(f"Invalid did:peer:2: {peer2}")

    if peer3 is None:
        peer3 = peer2to3(peer2)
    else:
        if not PEER3_PATTERN.match(peer3):
            raise ValueError(f"Invalid did:peer:3: {peer3}")

        computed = peer2to3(peer2)
        if computed != peer3:
            raise ValueError(
                f"did:peer:3 did does not match computed did: {peer3} != {computed}"
            )

    keys, services = _get_elements(peer2)
    document = _elements_to_document(peer3, keys, services)
    document["alsoKnownAs"] = [peer2]

    return document