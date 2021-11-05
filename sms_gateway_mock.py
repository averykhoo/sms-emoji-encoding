import struct
from urllib.parse import quote
from urllib.parse import unquote

from sms_message_encoder import coerce_text


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
    """
    # (1) and (2): decode url query parameter
    text = unquote(url_encoded_query_parameter)

    # (3): replace characters greater than U+FFFF with U+FFFD
    replaced_text = ''.join(char if ord(char) <= 0xFFFF else '\uFFFD' for char in text)

    # (4): split into pages of 63 characters
    pages = [replaced_text[i:i + 63] for i in range(0, len(replaced_text), 63)]

    # (5): encode each page as UCS-2 (big endian)
    encoded_pages = [struct.pack(f'>{len(page)}H', *(ord(char) for char in page)) for page in pages]
    return encoded_pages


def mobile_phone_render(*pages):
    """
    mocks a mobile phone that:
    1. accepts a list of pages (as bytes)
    2. decodes each page as UTF-16
    3. concatenates the pages
    4. prints the concatenated text
    """
    # (2): decode each page as UTF-16, defaulting to big endian unless specified
    decoded_pages = [page.decode('utf-16-le') if page.startswith(b'\xFF\xFE') else page.decode('utf-16-be')
                     for page in pages if page]

    # (3): concatenate the pages
    text = ''.join(decoded_pages)

    # (4): print the concatenated text
    return text


if __name__ == '__main__':
    print(mobile_phone_render(*sms_api_endpoint('%E2%9C%94test%F0%9F%92%A9')))
    print(mobile_phone_render(*sms_api_endpoint('%E2%80%9C%E2%80%9D%E2%80%9C%E2%80%9D')))
    print(mobile_phone_render(*sms_api_endpoint('%E2%80%9C%E2%80%9D%E2%80%9C%E2%80%9D%E2%80%9C%E2%80%9D')))
    print(mobile_phone_render(*sms_api_endpoint(quote(coerce_text('✔test💩')))))
    print(mobile_phone_render(*sms_api_endpoint(quote(coerce_text('“”‘’')))))
