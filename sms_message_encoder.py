import itertools
import string
import struct
import warnings
from functools import lru_cache
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

import grapheme
import unicodedata
from unidecode import unidecode

from sms_constants import BOM_BE
from sms_constants import BOM_LE
from sms_constants import REPLACEMENT_CHARACTER_BE
from sms_constants import REPLACEMENT_CHARACTER_LE
from sms_constants import UNSUPPORTED_CHARS


def coerce_plaintext(text: str) -> str:
    """
    This coerces unicode text to SMS-charset plaintext.
    Unprintable chars (eg. null) are dropped.
    All whitespace except CR and LF are normalized to just plain space (' ').

    >>> coerce_plaintext('\\ufeff')
    '?'
    >>> coerce_plaintext('\\ufeff' * 100)
    '????????????????????????????????????????????????????????????????????????????????????????????????????'
    >>> coerce_plaintext('\\ufffe')
    '?'
    >>> coerce_plaintext('✔')  # basic emoji < U+FFFF
    '?'
    >>> coerce_plaintext('✔️')  # compound emoji, each codepoint < U+FFFF
    '?'
    >>> coerce_plaintext('💩')  # emoji > U+FFFF
    '?'
    >>> coerce_plaintext('Åéïôu')  # characters with diacritics (non-compound; len=5)
    'Aeiou'
    >>> coerce_plaintext('Åéïôu')  # characters with diacritics (compound; len=9)
    'Aeiou'
    >>> coerce_plaintext('1234567890\\0')  # note that nulls must be double-escaped for doctests
    '1234567890'
    >>> coerce_plaintext('a' * 100 + '💩')
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa?'
    >>> coerce_plaintext('邱𣿭聖')
    'Qiu ?Sheng '
    """

    @lru_cache(maxsize=0xFFFF)
    def coerce_plaintext_grapheme(chars: str) -> str:
        if len(chars) == 0:
            return ''
        if set(chars).intersection(UNSUPPORTED_CHARS):
            return ''
        unprintable = ''.join(chr(i) for i in range(256) if chr(i) not in string.printable)
        out = unidecode(chars).translate(str.maketrans('`\b\f\v\t', "'    ", unprintable))
        return out or '?'

    return ''.join(map(coerce_plaintext_grapheme, grapheme.graphemes(text)))


@lru_cache(maxsize=0xFFFF)
def coerce_grapheme(chars: str,
                    handle_unsupported: str = 'replace',
                    ) -> Tuple[Optional[str], Optional[str]]:
    """
    This helper function is fairly slow, but it's cached.
    Also, you'd expect to see a reasonably small number of unique graphemes.

    Coerces a single grapheme from unicode codepoints into UTF-16 encoded bytes,
     masqueraded a valid string of UCS-2 unicode codepoints,
     that can be safely represented (ie. encoded and decoded) as valid strict UTF-8 bytes.

    Graphemes containing unsupported characters are handled according to the HANDLE_UNSUPPORTED parameter.

    The following unicode codepoints are almost certainly broken both ways:
    `[chr(x) for x in range(0xFFFF) if 0xD8 <= (x & 0xFF) < 0xE0 and 0xD8 <= (x >> 8) < 0xE0]`
    Or equivalently: `[chr((x << 8) + y) for x in range(0xD8, 0xE0) for y in range(0xD8, 0xE0)]`
    Fortunately, these are surrogates that mostly encode items in unassigned planes and the private use planes.

    This attempts to encode all unicode normalized forms of the grapheme, returning the shortest correct encoding.

    :param chars: a single grapheme (zero or more unicode codepoints)
    :param handle_unsupported: 'replace', 'ignore', 'error', 'pass'
    :return: a tuple of UTF-16-BE and UTF-16-LE representations, or None for characters that can't be represented
    """
    assert len(chars) > 0
    assert handle_unsupported.casefold() in {'replace', 'ignore', 'error', 'pass'}

    # don't allow any unsupported characters
    if set(chars).intersection(UNSUPPORTED_CHARS):
        if handle_unsupported.casefold() == 'replace':
            return REPLACEMENT_CHARACTER_BE, REPLACEMENT_CHARACTER_LE
        if handle_unsupported.casefold() == 'ignore':
            return '', ''
        if handle_unsupported.casefold() == 'error':
            warnings.warn("while it's supported, you should never need to use this mode")
            return None, None

    # unicode normalization of chars, prefer original if possible
    normalized_chars = [chars]
    for normalization_form in ('NFC', 'NFKC', 'NFD', 'NFKD'):
        _chars = unicodedata.normalize(normalization_form, chars)
        if _chars != chars and _chars not in normalized_chars:
            normalized_chars.append(unicodedata.normalize(normalization_form, chars))
    # if len(normalized_chars) > 1:
    #     print('normalized_chars', normalized_chars)

    # encode as UTF-16-BE, prefer shorter encodings where possible (original preferred if equally short)
    all_grapheme_bytes_be = sorted([chars.encode('utf-16-be') for chars in normalized_chars], key=len)
    assert all(len(grapheme_bytes_be) % 2 == 0 for grapheme_bytes_be in all_grapheme_bytes_be)

    # decode as UCS-2
    def decode_ucs2(endianness: str) -> Optional[str]:
        """
        decode as UCS-2 with some specific endianness

        :param endianness: ">" for big, "<" for little
        """
        assert endianness in {'>', '<'}
        nonlocal all_grapheme_bytes_be

        for grapheme_bytes_be in all_grapheme_bytes_be:
            n_chars = int(len(grapheme_bytes_be) // 2)
            try:
                encoded = ''.join(map(chr, struct.unpack(f'{endianness}{n_chars}H', grapheme_bytes_be)))
                assert len(encoded) > 0
                encoded.encode('utf8')
                return encoded
            except UnicodeEncodeError:
                pass
        return None

    # decode as UCS-2 in both endiannesses
    encoded_be = decode_ucs2('>')
    encoded_le = decode_ucs2('<')

    # don't allow encodings that are too long
    if encoded_be is not None and len(encoded_be) >= 63:
        encoded_be = None
    if encoded_le is not None and len(encoded_le) >= 63:
        encoded_le = None

    # no point returning errors on both sides, increases time and space complexity the greedy algorithm
    if encoded_be is None and encoded_le is None:
        # todo: handle unencodable diacritics by dropping them, maybe as a "try harder" step since both failed anyway
        # but this should be a rare scenario, unless zalgo is somehow involved
        return REPLACEMENT_CHARACTER_BE, REPLACEMENT_CHARACTER_LE

    return encoded_be, encoded_le


def right_pad_page(text: str, char: str) -> str:
    """
    right pad text to 63 chars
    """
    assert len(text) <= 63
    return text + char * (63 - len(text))


def coerce_text(text: str,
                max_pages: int = 5,
                truncated_text_error_multiplier: int = 1,
                handle_unsupported: str = 'replace',
                ) -> str:
    """
    A best-effort attempt to re-encode text to preserve emoji above U+FFFF when sending SMSes.
    At a bare minimum, this will not cause text to appear worse than attempting to send it unprocessed.

    TL;DR:
    Coerces text from unicode to UTF-16, masqueraded as UCS-2, that can be encoded as UTF-8.
    Works in pages of exactly 63 unicode chars, unless it all fits in a single page of 70 chars.
    Each page may be either UTF-16-BE (optional BOM) or UTF-16-LE (mandatory BOM).

    Reasoning:
    The [SMS spec](https://en.wikipedia.org/wiki/GSM_03.38) only allows either (a variant of) ASCII or UCS-2.
    UCS-2 only allows you to encode the characters in the BMP (Basic Multilingual Plane), ie. chars <= U+FFFF.
    This means that, technically speaking, the SMS spec doesn't allow you to send U+1F4A9 PILE_OF_POO "💩".
    But, in practice, most modern phones can send and receive emoji.
    This is because UCS-2 has been deprecated, so phones use UTF-16 instead, which is 100% backwards compatible.

    Unfortunately, the SMS API strictly follows the SMS spec, and only allows you to send SMS messages in UCS-2.
    In theory however, we can still masquerade UTF-16 as UCS-2, using the following conversion:
    `'💩'.encode('utf-16-be').decode('ucs2')` -> '\uD83D\uDCA9' (not valid python code)

    But the API also seems to use a strict UTF-8 decoder that replaces unpaired surrogates with U+FFFD.
    Surrogates are how UTF-16 encodes chars > U+FFFF, so we really do need them to send emoji.
    But since phones correctly detect and decode UTF-16-LE with BOM, we can simply swap byte ordering as follows:
    `'\uFFFE' + '💩'.encode('utf-16-le').decode('ucs2')` -> '\uFFFE\u3DD8\uA9DC' (not valid python code)

    This still precludes codepoints that require surrogates that, when byte-swapped, are still surrogates.
    Fortunately, the majority of these unsupported codepoints are in unassigned or private-use planes.

    Another side-effect of byte-swapping is that plaintext messages will look strange in the SMS API logs.
    For example, 'test' will be encoded as '\uFFFE琀攀猀琀'.
    We can minimize this by preferring UTF-16-BE over UTF-16-LE, and only byte-swapping when necessary.
    UTF-16-BE also doesn't require a BOM, so it saves one character.

    The algo contains a strange mix of greedy and beam search because global optimization is too much effort.
    On top of being simpler, it produces results that are more intuitively understandable than global optimization.

    It is unknown whether a grapheme can break across pages when encoded "normally" in UTF-16-BE (without BOM).
    However, the mandatory BOM breaks graphemes that are split across pages encoded in UTF-16-LE with BOM.
    The current code does not allow graphemes to break across pages, since 30 codepoints is a reasonable limit.
    One use case for extremely long graphemes is zalgo-fied text, which is useless enough to ignore.
    Data would not be reasonably considered to be lost if diacritics are truncated from zalgo-fied text.

    >>> coerce_text('\\ufeff')
    '\ufeff\ufeff'
    >>> set(coerce_text('\\ufeff' * 100))
    {'\ufeff'}
    >>> len(coerce_text('\\ufeff' * 100))
    102
    >>> coerce_text('\\ufffe')
    '\ufeff\ufffe'
    >>> coerce_text('✔')  # basic emoji < U+FFFF
    '✔'
    >>> coerce_text('✔️')  # compound emoji, each codepoint < U+FFFF
    '✔️'
    >>> coerce_text('💩')  # emoji > U+FFFF
    '\\ufffe㷘\\ua9dc'
    >>> coerce_text('Åéïôu')  # characters with diacritics (non-compound; len=5)
    'Åéïôu'
    >>> coerce_text('Åéïôu')  # characters with diacritics (compound; len=9)
    'Åéïôu'
    >>> coerce_text('1234567890\\0')  # note that nulls muse be double-escaped for doctests
    '1234567890�'
    >>> coerce_text('a' * 80 + '💩')
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\ufffe愀愀愀愀愀愀愀愀愀愀愀愀愀愀愀愀愀㷘\ua9dc'
    >>> coerce_text(string.printable) == string.printable
    True
    >>> coerce_text('邱𣿭聖')
    '\ufffe놐俘\ueddf嚀'
    """
    assert max_pages > 0
    _graphemes = list(grapheme.graphemes(text))

    # re-encode and count encoding failures
    _graphemes_be, _graphemes_le = zip(*map(coerce_grapheme, _graphemes, itertools.repeat(handle_unsupported)))
    errors_be = [g is None for g in _graphemes_be]
    errors_le = [g is None for g in _graphemes_le]
    graphemes_be: List[str] = [REPLACEMENT_CHARACTER_BE if g is None else g for g in _graphemes_be]
    graphemes_le: List[str] = [REPLACEMENT_CHARACTER_LE if g is None else g for g in _graphemes_le]

    # try single page encoding, which allows for 70 chars
    single_page_be = ''.join(graphemes_be)
    single_page_le = BOM_LE + ''.join(graphemes_le)

    # big endian text must not start with U+FFFE, otherwise it will decode wrongly
    if single_page_be[0] == BOM_LE:
        single_page_be = BOM_BE + single_page_be
    # big endian text ignores the first U+FEFF, so we need to add it
    elif single_page_be[0] == BOM_BE:
        single_page_be = BOM_BE + single_page_be

    # count errors for big endian
    single_page_error_be = 0
    message_length = int(single_page_be.startswith(BOM_BE + BOM_LE))
    for error, fragment in zip(errors_be, graphemes_be):
        if message_length + len(fragment) > 70:
            single_page_error_be += len(fragment) * truncated_text_error_multiplier
            continue
        message_length += len(fragment)
        single_page_error_be += error

    # count errors for little endian
    single_page_error_le = 0
    message_length = 1  # BOM_LE
    for error, fragment in zip(errors_le, graphemes_le):
        if message_length + len(fragment) > 70:
            single_page_error_le += len(fragment) * truncated_text_error_multiplier
            continue
        message_length += len(fragment)
        single_page_error_le += error

    # fast exit if it worked
    # prefer big endian encoding because it is more likely to be readable, at least in the logs
    if not any(errors_be) and len(single_page_be) <= 70:
        # print('single page encoding be worked')
        return single_page_be
    if not any(errors_le) and len(single_page_le) <= 70:
        # print('single page encoding le worked')
        return single_page_le

    # try multi-page encoding, which allows for 63 chars * max_pages
    states: List[Tuple[int, int, List[str]]] = [(0, 0, [])]  # idx, n_errors, pages
    for _page_idx in range(max_pages):
        new_states = []

        def append(_idx, _n_errors, _pages, _page):
            nonlocal new_states
            page_text = ''.join(_page)

            # little endian: gotta strip the BOM
            if page_text and page_text[0] in {BOM_BE, BOM_LE}:
                if len(page_text) > 1:
                    new_states.append((_idx, _n_errors, [*_pages, ''.join(_page)]))
            elif len(page_text) > 0:
                new_states.append((_idx, _n_errors, [*_pages, ''.join(_page)]))

        # big-endian
        for start_idx, n_errors, pages in states:
            page: List[str] = []
            total_len = 0
            for idx in range(start_idx, len(_graphemes)):
                # if this char caused an encoding error, save before adding it
                if errors_be[idx]:
                    append(idx, n_errors, pages, page)
                    n_errors += 1

                # append this grapheme to the page
                # we can't allow a BOM_LE to be the first char of a page
                if len(page) == 0 and graphemes_be[idx][0] in {BOM_LE, BOM_BE}:
                    page.append(BOM_BE + graphemes_be[idx])
                    total_len += 1 + len(graphemes_be[idx])
                else:
                    page.append(graphemes_be[idx])
                    total_len += len(graphemes_be[idx])

                # we're at the end of the text, save because we're gonna exit
                if idx + 1 >= len(graphemes_be):
                    append(idx + 1, n_errors, pages, page)
                    break

                # next char is too big to fit in page, save and exit
                elif len(graphemes_be[idx + 1]) + total_len > 63:
                    append(idx + 1, n_errors, pages, page)
                    break
            else:
                # end of text
                if any(page):
                    new_states.append((start_idx, n_errors, pages))

        # little-endian
        for start_idx, n_errors, pages in states:
            page = [BOM_LE]
            total_len = 1
            for idx in range(start_idx, len(_graphemes)):
                # if this char caused an encoding error, save before adding it
                if errors_le[idx]:
                    append(idx, n_errors, pages, page)
                    n_errors += 1

                # append this grapheme to the page
                page.append(graphemes_le[idx])
                total_len += len(graphemes_le[idx])

                # we're at the end of the text, save because we're gonna exit
                if idx + 1 >= len(graphemes_le):
                    append(idx + 1, n_errors, pages, page)
                    break

                # next char is too big to fit in page, save and exit
                elif len(graphemes_le[idx + 1]) + total_len > 63:
                    append(idx + 1, n_errors, pages, page)
                    break
            else:
                # end of text
                if any(page):
                    new_states.append((start_idx, n_errors, pages))

        # print(_page_idx, 'states', states)

        # filter to the best possible states so far
        best_new_states: Dict[int, Tuple[int, int, List[str]]] = dict()
        for start_idx, n_errors, pages in new_states:
            if start_idx > best_new_states.get(n_errors, (0, 0, []))[0]:
                best_new_states[n_errors] = (start_idx, n_errors, pages)

        # update the states
        states = list(best_new_states.values())
        # print(states)

        # fast exit if we reached the end
        if all(start_idx >= len(_graphemes) for start_idx, _, _ in states):
            break

    # count lost text as encoding errors
    errors_and_pages: List[Tuple[int, List[str]]] = []
    for start_idx, n_errors, pages in states:
        truncated_text_errors = max(0, len(_graphemes) - start_idx) * truncated_text_error_multiplier
        errors_and_pages.append((n_errors + truncated_text_errors, pages))
    errors_and_pages.append((single_page_error_be, [single_page_be]))
    errors_and_pages.append((single_page_error_le, [single_page_le]))

    # from pprint import pprint
    # pprint(errors_and_pages)

    min_error, best_pages = min(errors_and_pages, key=lambda x: (x[0], len(x[1]), len(x[1][-1])))
    # print(min_error, best_pages)
    # print(list(map(len, best_pages)))
    out = []
    for best_page in best_pages[:-1]:
        if not best_page:
            raise RuntimeError('empty best_page')
        elif best_page[0] == BOM_LE:
            out.append(right_pad_page(best_page, BOM_LE))
        else:
            out.append(right_pad_page(best_page, BOM_BE))
    out.append(best_pages[-1])
    # print(list(map(len, out)), out)
    return ''.join(out)
