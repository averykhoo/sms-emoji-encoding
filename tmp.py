import struct
from typing import Tuple

import grapheme


def coerce_grapheme(chars: str) -> Tuple[str, str]:
    """
    coerce a single grapheme from unicode to USC-2 masqueraded as UTF-16, that can be encoded as UTF-8
    returns both UTF-16-BE and UTF-16-LE representations
    """
    assert len(chars) > 0
    grapheme_bytes_be = chars.encode('utf-16-be')
    assert len(grapheme_bytes_be) % 2 == 0
    n_chars = int(len(grapheme_bytes_be) // 2)

    try:
        encoded_be = ''.join(map(chr, struct.unpack(f'>{n_chars}H', grapheme_bytes_be)))
        assert len(encoded_be) > 0
        encoded_be.encode('utf8')
    except UnicodeEncodeError:
        encoded_be = None

    try:
        encoded_le = ''.join(map(chr, struct.unpack(f'<{n_chars}H', grapheme_bytes_be)))
        assert len(encoded_le) > 0
        encoded_le.encode('utf8')
    except UnicodeEncodeError:
        encoded_le = None

    return encoded_be, encoded_le


def coerce_text(text: str, max_pages=5) -> str:
    """
    coerce text from unicode to USC-2 masqueraded as UTF-16, that can be encoded as UTF-8
    works in pages of exactly 63 unicode chars
    pages may be either in UTF-16-BE or UTF-16-LE with BOM
    """
    _graphemes = grapheme.graphemes(text)

    # re-encode and count encoding failures
    graphemes_be, graphemes_le = zip(*map(coerce_grapheme, _graphemes))
    error_be = [g is None for g in graphemes_be]
    error_le = [g is None for g in graphemes_le]
    graphemes_be = [g or '\uFFFD' for g in graphemes_be]
    graphemes_le = [g or '\uFDFF' for g in graphemes_le]


if __name__ == '__main__':
    print(list())
