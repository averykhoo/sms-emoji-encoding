import struct
from typing import Optional
from typing import Tuple

import grapheme

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


def coerce_grapheme(chars: str,
                    handle_unsupported: str = 'replace',
                    ) -> Tuple[Optional[str], Optional[str]]:
    """
    coerce a single grapheme from unicode to USC-2 masqueraded as UTF-16, that can be encoded as UTF-8
    graphemes containing unsupported characters are handled according to the handle_unsupported parameter
    returns both UTF-16-BE and UTF-16-LE representations

    :param chars: a single unicode character
    :param handle_unsupported: 'replace', 'ignore', 'error', 'pass'
    """
    assert len(chars) > 0
    assert handle_unsupported.casefold() in {'replace', 'ignore', 'error', 'pass'}

    # don't allow any unsupported characters
    if set(chars).intersection(UNSUPPORTED_CHARS):
        if handle_unsupported.casefold() == 'replace':
            return '\uFFFD', '\uFDFF'
        if handle_unsupported.casefold() == 'ignore':
            return '', ''
        if handle_unsupported.casefold() == 'error':
            return None, None

    # encode as UTF-16-BE
    grapheme_bytes_be = chars.encode('utf-16-be')
    assert len(grapheme_bytes_be) % 2 == 0
    n_chars = int(len(grapheme_bytes_be) // 2)

    # decode as UCS-2
    try:
        encoded_be = ''.join(map(chr, struct.unpack(f'>{n_chars}H', grapheme_bytes_be)))
        assert len(encoded_be) > 0
        encoded_be.encode('utf8')
    except UnicodeEncodeError:
        encoded_be = None

    # decode as UCS-2-LE (kind of, basically swap the endianness)
    try:
        encoded_le = ''.join(map(chr, struct.unpack(f'<{n_chars}H', grapheme_bytes_be)))
        assert len(encoded_le) > 0
        encoded_le.encode('utf8')
    except UnicodeEncodeError:
        encoded_le = None

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
                ) -> str:
    """
    coerce text from unicode to USC-2 masqueraded as UTF-16, that can be encoded as UTF-8
    works in pages of exactly 63 unicode chars
    pages may be either in UTF-16-BE or UTF-16-LE with BOM

    the algo contains a strange mix of greedy and beam search because global optimization is too much effort
    also this produces more intuitively understandable results than global optimization
    """
    assert max_pages > 0
    _graphemes = list(grapheme.graphemes(text))

    # re-encode and count encoding failures
    graphemes_be, graphemes_le = zip(*map(coerce_grapheme, _graphemes))
    errors_be = [g is None for g in graphemes_be]
    errors_le = [g is None for g in graphemes_le]
    graphemes_be = [g or '\uFFFD' for g in graphemes_be]
    graphemes_le = [g or '\uFDFF' for g in graphemes_le]

    # try single page encoding, which allows for 70 chars
    single_page_be = ''.join(graphemes_be)
    single_page_le = '\uFFFE' + ''.join(graphemes_le)

    # big endian text must not start with U+FFFE, otherwise it will decode wrongly
    if single_page_be[0] == '\uFFFE':
        single_page_be = '\uFEFF' + single_page_be

    # count errors for big endian
    single_page_error_be = 0
    message_length = int(single_page_be.startswith('\uFEFF\uFFFE'))
    for error, fragment in zip(errors_be, graphemes_be):
        if message_length + len(fragment) > 70:
            single_page_error_be += len(fragment) * truncated_text_error_multiplier
            continue
        message_length += len(fragment)
        single_page_error_be += error

    # count errors for little endian
    single_page_error_le = 0
    message_length = 1  # U+FFFE
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
    for _ in range(max_pages):
        new_states = []

        # big-endian
        for start_idx, n_errors, pages in states:
            page = []
            total_len = 0
            for idx in range(start_idx, len(_graphemes)):
                # if this char caused an encoding error, save before adding it
                if errors_be[idx]:
                    new_states.append((idx, n_errors, [*pages, ''.join(page)]))
                    n_errors += 1
                    print(n_errors, idx)

                # append this grapheme to the page
                page.append(graphemes_be[idx])
                total_len += len(graphemes_be[idx])

                # we can't allow a U+FFFE to be at the start
                if page[0][0] == '\uFFFE':
                    page = ['\uFEFF'] + page
                    total_len += 1

                # we're at the end of the text, save because we're gonna exit
                if idx + 1 >= len(graphemes_be):
                    new_states.append((idx + 1, n_errors, [*pages, ''.join(page)]))
                    break

                # next char is too big to fit in page, save and exit
                elif len(graphemes_be[idx + 1]) + total_len > 63:
                    new_states.append((idx + 1, n_errors, [*pages, ''.join(page)]))
                    break
            else:
                # end of text
                new_states.append((start_idx, n_errors, pages))

        # little-endian
        for start_idx, n_errors, pages in states:
            page = ['\uFFFE']
            total_len = 1
            for idx in range(start_idx, len(_graphemes)):
                # if this char caused an encoding error, save before adding it
                if errors_le[idx]:
                    new_states.append((idx, n_errors, [*pages, ''.join(page)]))
                    n_errors += 1

                # append this grapheme to the page
                page.append(graphemes_le[idx])
                total_len += len(graphemes_le[idx])

                # we're at the end of the text, save because we're gonna exit
                if idx + 1 >= len(graphemes_le):
                    new_states.append((idx + 1, n_errors, [*pages, ''.join(page)]))
                    break

                # next char is too big to fit in page, save and exit
                elif len(graphemes_le[idx + 1]) + total_len > 63:
                    new_states.append((idx + 1, n_errors, [*pages, ''.join(page)]))
                    break
            else:
                # end of text
                new_states.append((start_idx, n_errors, pages))

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
        truncated_text_errors = max(0, start_idx - (63 * max_pages)) * truncated_text_error_multiplier
        errors_and_pages.append((n_errors + truncated_text_errors, pages))
    errors_and_pages.append((single_page_error_be, [single_page_be]))
    errors_and_pages.append((single_page_error_le, [single_page_le]))
    min_error, best_pages = min(errors_and_pages, key=lambda x: x[0])
    print(min_error, best_pages)
    print(list(map(len, best_pages)))
    out = []
    for page in best_pages[:-1]:
        if page[0] == '\uFFFE':
            out.append(right_pad_page(page, '\uFFFE'))
        else:
            out.append(right_pad_page(page, '\uFEFF'))
    out.append(best_pages[-1])
    print(list(map(len, out)), out)
    return ''.join(best_pages)


if __name__ == '__main__':
    print(repr(coerce_text('1234567890' * 5 + '💩qwe😊asd✔')))
