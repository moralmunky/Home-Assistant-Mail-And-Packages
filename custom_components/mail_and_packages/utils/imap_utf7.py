"""IMAP modified UTF-7 encoding and decoding utilities."""

import binascii
from urllib.parse import quote, unquote

_ATOM_SPECIALS = frozenset('(){%*"\\] ')


def encode_imap_utf7(s: str) -> str:
    """Encode a string into IMAP modified UTF-7."""
    res = []
    unicode_buffer = []

    def flush_unicode():
        if unicode_buffer:
            u_str = "".join(unicode_buffer)
            encoded_bytes = u_str.encode("utf-16be")
            b64 = (
                binascii.b2a_base64(encoded_bytes)
                .decode("ascii")
                .rstrip("\n=")
                .replace("/", ",")
            )
            res.append(f"&{b64}-")
            unicode_buffer.clear()

    for char in s:
        ord_c = ord(char)
        if 0x20 <= ord_c <= 0x7E:
            if char == "&":
                flush_unicode()
                res.append("&-")
            else:
                if unicode_buffer:
                    flush_unicode()
                res.append(char)
        else:
            unicode_buffer.append(char)

    flush_unicode()
    return "".join(res)


def decode_imap_utf7(s: str) -> str:
    """Decode a string from IMAP modified UTF-7."""
    res = []
    i = 0
    n = len(s)
    while i < n:
        char = s[i]
        if char == "&":
            end = s.find("-", i + 1)
            if end == -1:
                res.append("&")
                i += 1
            elif end == i + 1:
                res.append("&")
                i += 2
            else:
                b64_part = s[i + 1 : end]
                b64_part = b64_part.replace(",", "/")
                pad = len(b64_part) % 4
                if pad:
                    b64_part += "=" * (4 - pad)
                try:
                    decoded_bytes = binascii.a2b_base64(b64_part)
                    res.append(decoded_bytes.decode("utf-16be"))
                except (binascii.Error, UnicodeDecodeError, ValueError):
                    res.append(s[i : end + 1])
                i = end + 1
        else:
            res.append(char)
            i += 1

    return "".join(res)


def _is_imap_atom(s: str) -> bool:
    """Check if the string is a valid IMAP atom."""
    return bool(s) and all(0x20 < ord(c) < 0x7F and c not in _ATOM_SPECIALS for c in s)


def quote_folder(folder: str) -> str:
    """Ensure folder name is properly quoted for IMAP commands."""
    if folder.startswith('"') and folder.endswith('"'):
        return folder
    return folder if _is_imap_atom(folder) else f'"{folder}"'


def encode_folder_ref(folder: str) -> str:
    """Percent-encode a folder name for use in a composite ``folder/uid`` ID.

    Multi-folder searches tag each UID with its source folder as
    ``folder/uid``. Those composite IDs are space-joined and re-split on
    whitespace at several call sites, and split on ``/`` to recover the
    folder — so the folder component must contain neither whitespace nor
    ``/``. A folder named ``# - Projects`` would otherwise shatter into
    ``#``, ``-``, ``Projects/55`` when the joined ID list is ``.split()``.
    ``quote(..., safe="")`` escapes both (and ``%`` itself, keeping the
    round-trip lossless for any folder name).
    """
    return quote(folder, safe="")


def decode_folder_ref(folder: str) -> str:
    """Decode the percent-encoded folder component of a composite ID.

    Takes the already-split folder component (everything before the final
    ``/`` of a ``folder/uid`` ID), not the full composite ID.
    """
    return unquote(folder)
