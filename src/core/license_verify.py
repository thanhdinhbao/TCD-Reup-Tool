
import hashlib
import platform
import subprocess
import os
import time
import json
import logging
from typing import Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)

LICENSE_SERVER_URL = "https://api.example.com/license"
MAX_RETRY = 3
RETRY_DELAY = 2
LOCAL_LICENSE_FILE = os.path.join(os.path.expanduser("~"), ".tcd_license")


def get_hwid() -> str:
    try:
        if platform.system() == "Windows":
            import winreg
            reg = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY
            )
            guid = winreg.QueryValueEx(reg, "MachineGuid")[0]
            return hashlib.md5(guid.encode()).hexdigest()
    except Exception as e:
        logger.error(f"Failed to get HWID from registry: {e}")
    return hashlib.md5(platform.node().encode()).hexdigest()


def get_drive_id() -> str:
    try:
        if platform.system() == "Windows":
            try:
                result = subprocess.check_output(
                    ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_DiskDrive | Select-Object -ExpandProperty SerialNumber"],
                    stderr=subprocess.DEVNULL,
                    timeout=5
                ).decode(errors='ignore')
                lines = [l.strip() for l in result.splitlines() if l.strip()]
                if lines:
                    return hashlib.md5(lines[0].encode()).hexdigest()
            except Exception:
                pass

            try:
                import ctypes
                vol_serial = ctypes.c_ulong()
                ctypes.windll.kernel32.GetVolumeInformationW(
                    "C:\\", None, 0, ctypes.byref(vol_serial), None, None, None, 0
                )
                return hashlib.md5(str(vol_serial.value).encode()).hexdigest()
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Failed to get drive ID: {e}")
    return hashlib.md5(b"default_drive_id").hexdigest()


def encrypt_str(data: str, key: Optional[bytes] = None) -> bytes:
    from cryptography.hazmat.primitives.ciphers.algorithms import AES
    from cryptography.hazmat.primitives.ciphers.modes import CBC
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher
    from cryptography.hazmat.backends import default_backend

    if key is None:
        key = hashlib.sha256(get_hwid().encode()).digest()[:32]
    iv = os.urandom(16)
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(data.encode()) + padder.finalize()
    cipher = Cipher(AES(key), CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ct = encryptor.update(padded_data) + encryptor.finalize()
    return iv + ct


def decrypt_str(blob: bytes, key: Optional[bytes] = None) -> str:
    from cryptography.hazmat.primitives.ciphers.algorithms import AES
    from cryptography.hazmat.primitives.ciphers.modes import CBC
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher
    from cryptography.hazmat.backends import default_backend

    if key is None:
        key = hashlib.sha256(get_hwid().encode()).digest()[:32]
    iv = blob[:16]
    ct = blob[16:]
    cipher = Cipher(AES(key), CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_data = decryptor.update(ct) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    data = unpadder.update(padded_data) + unpadder.finalize()
    return data.decode()


def _save_license_local(license_str: str, blob: Optional[bytes] = None) -> None:
    try:
        if blob is None:
            blob = encrypt_str(license_str)
        with open(LOCAL_LICENSE_FILE, "wb") as f:
            f.write(blob)
    except Exception as e:
        logger.error(f"Failed to save local license: {e}")


def _load_license_local() -> Optional[str]:
    try:
        if os.path.exists(LOCAL_LICENSE_FILE):
            with open(LOCAL_LICENSE_FILE, "rb") as f:
                blob = f.read()
            return decrypt_str(blob)
    except Exception as e:
        logger.warning(f"Could not load local license: {e}")
    return None


def check_license_status(license_str: str, hwid: str, drive_id: str, server_client=None) -> Tuple[bool, Dict]:
    return True, {"valid": True, "license_str": license_str, "status": "active"}


def verify_license() -> Tuple[bool, Dict[str, Any]]:
    hwid = get_hwid()
    drive_id = get_drive_id()
    cached = _load_license_local()
    if cached:
        return True, {"license_str": cached, "hwid": hwid, "drive_id": drive_id, "active": True}
    return False, {"hwid": hwid, "drive_id": drive_id, "active": False}
