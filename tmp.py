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


def right_pad_page(text: str, char: str) -> str:
    """
    right pad text to 63 chars
    """
    assert len(text) <= 63
    return text + char * (63 - len(text))


def coerce_text(text: str, max_pages=5) -> str:
    """
    coerce text from unicode to USC-2 masqueraded as UTF-16, that can be encoded as UTF-8
    works in pages of exactly 63 unicode chars
    pages may be either in UTF-16-BE or UTF-16-LE with BOM

    the algo will be a strange mix of greedy and beam search because global optimization is too much effort
    """
    _graphemes = list(grapheme.graphemes(text))

    # re-encode and count encoding failures
    graphemes_be, graphemes_le = zip(*map(coerce_grapheme, _graphemes))
    error_be = [g is None for g in graphemes_be]
    error_le = [g is None for g in graphemes_le]
    graphemes_be = [g or '\uFFFD' for g in graphemes_be]
    graphemes_le = [g or '\uFDFF' for g in graphemes_le]

    # try single page encoding, which allows for 70 chars
    single_page_be = ''.join(graphemes_be)
    single_page_error_be = sum(error_be) + max(0, len(single_page_be) - 70)
    single_page_le = '\uFFFE' + ''.join(graphemes_le)
    single_page_error_le = sum(error_le) + max(0, len(single_page_le) - 70)

    # fast exit if this worked
    if single_page_error_be == 0:
        print('single page encoding be worked')
        return single_page_be
    if single_page_error_le == 0:
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
                if error_be[idx]:
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
                if error_le[idx]:
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
        errors_and_pages.append((n_errors + max(0, start_idx - 63 * max_pages), pages))
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
