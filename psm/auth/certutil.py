import subprocess
from pathlib import Path
from typing import Tuple

try:  # Optional dependency
    from cryptography import x509  # type: ignore
    from cryptography.x509.oid import NameOID  # type: ignore
    from cryptography.hazmat.primitives import hashes, serialization  # type: ignore
    from cryptography.hazmat.primitives.asymmetric import rsa  # type: ignore
    CRYPTO_AVAILABLE = True
except Exception:  # pragma: no cover
    x509 = NameOID = hashes = serialization = rsa = None  # type: ignore
    CRYPTO_AVAILABLE = False


def ensure_self_signed(cert_path: str | Path, key_path: str | Path) -> Tuple[str, str]:
    """Ensure a self-signed localhost certificate exists.

    Prefers the 'cryptography' library if available. Falls back to invoking
    openssl if present on PATH. Raises RuntimeError if generation fails.
    """
    cert_path = Path(cert_path)
    key_path = Path(key_path)
    if cert_path.exists() and key_path.exists():
        return str(cert_path), str(key_path)
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    if CRYPTO_AVAILABLE:  # type: ignore
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)  # type: ignore
        subject = issuer = x509.Name([  # type: ignore
            x509.NameAttribute(NameOID.COMMON_NAME, u"localhost")  # type: ignore
        ])
        cert = (
            x509.CertificateBuilder()  # type: ignore
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())  # type: ignore
            .not_valid_before(__import__('datetime').datetime.utcnow())
            .not_valid_after(__import__('datetime').datetime.utcnow() + __import__('datetime').timedelta(days=365))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(u"localhost")]), critical=False)  # type: ignore
            .sign(key, hashes.SHA256())  # type: ignore
        )
        with open(key_path, 'wb') as kf:
            kf.write(key.private_bytes(  # type: ignore
                encoding=serialization.Encoding.PEM,  # type: ignore
                format=serialization.PrivateFormat.TraditionalOpenSSL,  # type: ignore
                encryption_algorithm=serialization.NoEncryption()  # type: ignore
            ))
        with open(cert_path, 'wb') as cf:
            cf.write(cert.public_bytes(serialization.Encoding.PEM))  # type: ignore
        return str(cert_path), str(key_path)
    # Fallback: openssl
    openssl = 'openssl'
    try:
        proc = subprocess.run(
            [openssl, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', str(key_path), '-out', str(cert_path), '-days', '365', '-subj', '/CN=localhost'],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as e:  # pragma: no cover
        err = (e.stderr or '').strip()
        raise RuntimeError(f"Failed to generate certificate via openssl (exit {e.returncode}). Stderr: {err}") from e
    except FileNotFoundError as e:  # pragma: no cover
        raise RuntimeError("OpenSSL not found on PATH and 'cryptography' unavailable; install 'cryptography' or provide cert/key manually.") from e
    return str(cert_path), str(key_path)

__all__ = ["ensure_self_signed"]
