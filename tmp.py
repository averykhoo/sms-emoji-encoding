import itertools
import struct
import warnings
from functools import lru_cache
from pprint import pprint
from typing import Optional
from typing import Tuple

import grapheme
import unicodedata

# constants
REPLACEMENT_CHARACTER_BE = '\uFFFD'
REPLACEMENT_CHARACTER_LE = '\uFDFF'
BOM_BE = '\uFEFF'  # aka ZWNBSP, although that specific use has been deprecated for this char
BOM_LE = '\uFFFE'

UNSUPPORTED_CHARS = {
    '\0',  # null

    # BiDi control characters
    # https://developer.mozilla.org/en-US/docs/Web/Guide/Unicode_Bidrectional_Text_Algorithm
    '\u202A',  # Left-to-Right Embedding (LRE)
    '\u202B',  # Right-to-Left Embedding (RLE)
    '\u202D',  # Left-to-Right Override (LRO)
    '\u202E',  # Right-to-Left Override (RLO)
    '\u202C',  # Pop Directional Formatting (PDF)
    '\u2069',  # Pop Directional Isolate (PDI)
    '\u2066',  # Left-to-Right Isolate (LRI)
    '\u2067',  # Right-to-Left Isolate (LRI)
    '\u2068',  # First Strong Isolate (FSI)
    # https://en.wikipedia.org/wiki/Bidirectional_text
    '\u200E',  # LEFT-TO-RIGHT MARK (LRM)
    '\u200F',  # RIGHT-TO-LEFT MARK (RLM)
    '\u061C',  # ARABIC LETTER MARK (ALM)
    '\u200E',  # LEFT-TO-RIGHT MARK (LRM)
}


@lru_cache(maxsize=0xFFFF)
def coerce_grapheme(chars: str,
                    handle_unsupported: str = 'replace',
                    ) -> Tuple[Optional[str], Optional[str]]:
    """
    coerce a single grapheme from unicode to USC-2 masqueraded as UTF-16, that can be encoded as UTF-8
    graphemes containing unsupported characters are handled according to the handle_unsupported parameter
    returns both UTF-16-BE and UTF-16-LE representations

    chars that are almost certainly broken both ways:
    [chr(x) for x in range(0xFFFF) if 0xD8 <= x & 0xFF < 0xE0 and 0xD8 <= x >> 8 < 0xE0]
    fortunately these mostly encode items in unassigned planes and private use planes

    todo: optionally handle unencodable diacritics by dropping, maybe as a "try harder" step when both fail

    :param chars: a single unicode character
    :param handle_unsupported: 'replace', 'ignore', 'error', 'pass'
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

    # unicode normalization of chars
    normalized_chars = set()
    normalized_chars.add(chars)
    for normalization_form in ('NFC', 'NFKC', 'NFD', 'NFKD'):
        normalized_chars.add(unicodedata.normalize(normalization_form, chars))
    if len(normalized_chars) > 1:
        print('normalized_chars', normalized_chars)

    # encode as UTF-16-BE
    all_grapheme_bytes_be = sorted([chars.encode('utf-16-be') for chars in normalized_chars], key=len)
    assert all(len(grapheme_bytes_be) % 2 == 0 for grapheme_bytes_be in all_grapheme_bytes_be)
    all_n_chars = [int(len(grapheme_bytes_be) // 2) for grapheme_bytes_be in all_grapheme_bytes_be]

    # decode as UCS-2
    def decode_ucs2(endianness: str) -> Optional[str]:
        """
        decode as UCS-2 with some specific endianness
        :param endianness: ">" for big, "<" for little
        :return:
        """
        assert endianness in {'>', '<'}
        for grapheme_bytes_be, n_chars in zip(all_grapheme_bytes_be, all_n_chars):
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

    # no point returning errors on both sides, increases time and space complexity the greedy algorithm
    if encoded_be is None and encoded_le is None:
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
    coerce text from unicode to USC-2 masqueraded as UTF-16, that can be encoded as UTF-8
    works in pages of exactly 63 unicode chars
    pages may be either in UTF-16-BE or UTF-16-LE with BOM

    the algo contains a strange mix of greedy and beam search because global optimization is too much effort
    also this produces results that are slightly more intuitively understandable than global optimization
    """
    assert max_pages > 0
    _graphemes = list(grapheme.graphemes(text))

    # re-encode and count encoding failures
    graphemes_be, graphemes_le = zip(*map(coerce_grapheme, _graphemes, itertools.repeat(handle_unsupported)))
    errors_be = [g is None for g in graphemes_be]
    errors_le = [g is None for g in graphemes_le]
    graphemes_be = [REPLACEMENT_CHARACTER_BE if g is None else g for g in graphemes_be]
    graphemes_le = [REPLACEMENT_CHARACTER_LE if g is None else g for g in graphemes_le]

    # try single page encoding, which allows for 70 chars
    single_page_be = ''.join(graphemes_be)
    single_page_le = BOM_LE + ''.join(graphemes_le)

    # big endian text must not start with BOM_LE, otherwise it will decode wrongly
    if single_page_be[0] == BOM_LE:
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
        print('single page encoding be worked')
        return single_page_be
    if not any(errors_le) and len(single_page_le) <= 70:
        print('single page encoding le worked')
        return single_page_le

    # try multi-page encoding, which allows for 63 chars * max_pages
    states = [(0, 0, [])]  # idx, n_errors, pages
    for _page_idx in range(max_pages):
        new_states = []

        def append(_idx, _n_errors, _pages, _page):
            nonlocal new_states
            if any(_page):  # don't save empty pages
                new_states.append((_idx, _n_errors, [*_pages, ''.join(_page)]))

        # big-endian
        for start_idx, n_errors, pages in states:
            page = []
            total_len = 0
            for idx in range(start_idx, len(_graphemes)):
                # if this char caused an encoding error, save before adding it
                if errors_be[idx]:
                    append(idx, n_errors, pages, page)
                    n_errors += 1

                # append this grapheme to the page
                page.append(graphemes_be[idx])
                total_len += len(graphemes_be[idx])

                # we can't allow a BOM_LE to be the first char of a page
                if page[0][0] == BOM_LE:
                    page = [BOM_BE] + page
                    total_len += 1

                # we're at the end of the text, save because we're gonna exit
                if idx + 1 >= len(graphemes_be):
                    append(idx, n_errors, pages, page)
                    break

                # next char is too big to fit in page, save and exit
                elif len(graphemes_be[idx + 1]) + total_len > 63:
                    append(idx, n_errors, pages, page)
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
                    append(idx, n_errors, pages, page)
                    break

                # next char is too big to fit in page, save and exit
                elif len(graphemes_le[idx + 1]) + total_len > 63:
                    append(idx, n_errors, pages, page)
                    break
            else:
                # end of text
                if any(page):
                    new_states.append((start_idx, n_errors, pages))

        print(_page_idx, 'states', states)

        # filter to the best possible states so far
        best_new_states = dict()
        for start_idx, n_errors, pages in new_states:
            if start_idx > best_new_states.get(n_errors, (0, 0, []))[0]:
                best_new_states[n_errors] = (start_idx, n_errors, pages)

        # update the states
        states = list(best_new_states.values())
        print(states)

        # fast exit if we reached the end
        if all(start_idx + 1 >= len(_graphemes) for start_idx, _, _ in states):
            break

    # count lost text as encoding errors
    errors_and_pages = []
    for start_idx, n_errors, pages in states:
        truncated_text_errors = max(0, len(_graphemes) - start_idx) * truncated_text_error_multiplier
        errors_and_pages.append((n_errors + truncated_text_errors, pages))
    errors_and_pages.append((single_page_error_be, [single_page_be]))
    errors_and_pages.append((single_page_error_le, [single_page_le]))

    pprint(errors_and_pages)

    min_error, best_pages = min(errors_and_pages, key=lambda x: (x[0], len(x[1]), len(x[1][-1])))
    print(min_error, best_pages)
    print(list(map(len, best_pages)))
    out = []
    for page in best_pages[:-1]:
        if not page:
            raise RuntimeError('empty page')
        elif page[0] == BOM_LE:
            out.append(right_pad_page(page, BOM_LE))
        else:
            out.append(right_pad_page(page, BOM_BE))
    out.append(best_pages[-1])
    print(list(map(len, out)), out)
    return ''.join(out)


if __name__ == '__main__':
    print(repr(coerce_text('1234567890\0' * 5 + '💩qwe😊asd✔')))

    # todo: error condition
    print(repr(coerce_text('\0\0\0\0\0\0💩qwé😊ÅSD✔', handle_unsupported='error')))
