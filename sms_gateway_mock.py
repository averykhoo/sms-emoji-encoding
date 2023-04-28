import struct
from urllib.parse import unquote

from sms_constants import BOM_BE
from sms_constants import BOM_LE


def sms_api_endpoint(url_encoded_query_parameter):
    """
    mocks a (strictly speaking not REST, but HTTP) API that:
    1. accepts percent-encoded unicode text as a URL query parameter
    2. decodes the query parameter as UTF-8
    3. replaces any character greater than U+FFFF with U+FFFD
    4. splits the unicode text into pages of 63 characters (the max SMS length)
    5. encodes each page as UCS-2 (big endian)
    6. sends each page separately (metadata defines the ordering)
    in this case, it will return a list of pages

    >>> # double-escape quotes because of how doctest parses input
    >>> sms_api_endpoint('%E2%9C%94%F0%9F%92%A9')  # urllib.parse.quote('✔💩')
    [b"'\\x14\\xff\\xfd"]
    >>> sms_api_endpoint('%E2%80%9C%E2%80%9D%C3%A5%E2%80%98%E2%80%99')  # urllib.parse.quote('“”å‘’')
    [b' \\x1c \\x1d\\x00\\xe5 \\x18 \\x19']
    >>> sms_api_endpoint('%E9%82%B1%F0%A3%BF%AD%E8%81%96')  # urllib.parse.quote('邱𣿭聖')
    [b'\\x90\\xb1\\xff\\xfd\\x80V']
    """
    # (1) and (2): decode url query parameter, replacing unpaired surrogates with U+FFFD
    text = unquote(url_encoded_query_parameter, encoding='utf-8', errors='replace')
    assert len(text) > 0  # sending empty messages not supported; instead, you can send just a BOM '\uFEFF'
    assert '\0' not in text  # sending null not supported

    # (3): replace characters greater than U+FFFF with U+FFFD
    replaced_text = ''.join(char if ord(char) <= 0xFFFF else '\uFFFD' for char in text)

    # (4): split into pages of 63 characters (except for a single page)
    if len(replaced_text) > 70:
        # pages = [replaced_text[i:i + 63] for i in range(0, len(replaced_text), 63)]
        pages = []
        cursor = 0
        while cursor < len(replaced_text):
            if replaced_text[cursor] == BOM_BE or replaced_text[cursor] == BOM_LE:
                pages.append(replaced_text[cursor:cursor + 67])
                cursor += 67
            else:
                pages.append(replaced_text[cursor:cursor + 63])
                cursor += 63

        # pages = [replaced_text[i:i + 63] for i in range(0, len(replaced_text), 63)]
    else:
        pages = [replaced_text]

    # (5): encode each page as UCS-2 (big endian)
    encoded_pages = [struct.pack(f'>{len(page)}H', *(ord(char) for char in page)) for page in pages]
    return encoded_pages


def mobile_phone_render(*pages, rstrip=True):
    """
    mocks a mobile phone that:
    1. accepts a list of pages (as bytes)
    2. decodes each page as UTF-16
    3. concatenates the pages
    4. prints the concatenated text

    >>> # double-escape quotes because of how doctest parses input
    >>> # note that it cannot correctly handle chars > U+FFFF
    >>> mobile_phone_render(b"'\\x14\\xff\\xfd")  # *sms_api_endpoint(urllib.parse.quote('✔💩'))
    '✔�'
    >>> mobile_phone_render(b' \\x1c \\x1d\\x00\\xe5 \\x18 \\x19')  # *sms_api_endpoint(urllib.parse.quote('“”å‘’'))
    '“”å‘’'
    >>> mobile_phone_render(b'\\x90\\xb1\\xff\\xfd\\x80V')  # *sms_api_endpoint(urllib.parse.quote('邱𣿭聖'))
    '邱�聖'
    """
    # (2): decode each page as UTF-16, defaulting to big endian unless specified
    decoded_pages = []
    for page in pages:
        if page.startswith(b'\xFE\xFF'):
            decoded_pages.append(page[2:].decode('utf-16-be'))
        elif page.startswith(b'\xFF\xFE'):
            decoded_pages.append(page[2:].decode('utf-16-le'))
        else:
            decoded_pages.append(page.decode('utf-16-be'))

    if rstrip:
        decoded_pages = [page.rstrip('\uFEFF') for page in decoded_pages]

    # (3): concatenate the pages
    text = ''.join(decoded_pages)

    # (4): print the concatenated text
    return text
