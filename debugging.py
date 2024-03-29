from urllib.parse import quote

from sms_gateway_mock import mobile_phone_render
from sms_gateway_mock import sms_api_endpoint
from sms_message_encoder import coerce_text

outputs = {
    '[rapid] 2023-01-05 14:52:13\n🆘 123456789 123456789 123456789 123456789 123456789 123456789 123456789 123456789 123456789 123456789 0':
        '[rapid] 2023-01-05 14:52:13\n🆘 123456789 123456789 123456789 1㈀㌀㐀㔀6789 123456789 123456789 123456789 123456789 123456789 123456789 0',

    '[rapid] 2023-01-05 14:52:18\n🆘🆘 123456789 123456789 123456789 123456789 123456789 123456789 123456789 123456789 123456789 123456789 0':
        '[rapid] 2023-01-05 14:52:18\n🆘🆘 123456789 123456789 123456789 ㄀㈀㌀456789 123456789 123456789 123456789 123456789 123456789 123456789 0',

    '[rapid] 2023-01-05 14:52:21\n🆘🆘🆘 123456789 123456789 123456789 123456789 123456789 123456789 123456789 123456789 123456789 123456789 0':
        '[rapid] 2023-01-05 14:52:21\n🆘🆘🆘 123456789 123456789 1234567㠀㤀 ㄀23456789 123456789 123456789 123456789 123456789 123456789 123456789 0',

    '[rapid] 2023-01-05 14:53:57\n🆘 123456789 123456789 123456789 1🆘23456789 123456789 123456789 123456789 123456789 123456789 123456789 0':
        '[rapid] 2023-01-05 14:53:57\n🆘 123456789 123456789 123456789 1﻿🆘2㌀㐀㔀㘀㜀㠀㤀 ㄀㈀㌀㐀㔀㘀㜀㠀㤀 ㄀㈀㌀㐀㔀㘀㜀㠀㤀 ㄀㈀㌀㐀㔀㘀㜀㠀㤀 ㄀㈀㌀㐀㔀㘀㜀㠀㤀 ㄀㈀㌀㐀㔀㘀㜀㠀㤀 ㄀23456789 0',

    '[rapid] 2023-01-05 14:54:08\n🆘 123456789 123456789 123456789 12345🆘6789 123456789 123456789 123456789 123456789 123456789 123456789 0':
        '[rapid] 2023-01-05 14:54:08\n🆘 123456789 123456789 123456789 1﻿234㔀㳘飝㘀㜀㠀㤀 ㄀㈀㌀㐀㔀㘀㜀㠀㤀 ㄀㈀㌀㐀㔀㘀㜀㠀㤀 ㄀㈀㌀㐀㔀㘀㜀㠀㤀 ㄀㈀㌀㐀㔀㘀㜀㠀㤀 ㄀㈀㌀㐀㔀㘀㜀㠀㤀 ㄀23456789 0',

    '[rapid] 2023-01-05 11:00:00\n🆘 1 checks are down\nKeycloak: 11/12 checks are up (1 down)\nRAPID: 12/12 checks are up\nScoold: 1/1 checks are up':
        '[rapid] 2023-01-05 11:00:00\n🆘 1 checks are down\nKeycloak: 11/㄀㈀ 挀hecks are up (1 down)\nRAPID: 12/12 checks are up\nScoold: 1/1 checks are up',

    '[rapid] 2023-01-05 14:52:13\n✅ 123456789 123456789 123456789 123456789 123456789 123456789 123456789 123456789 123456789 123456789 0':
        '[rapid] 2023-01-05 14:52:13\n✅ 123456789 123456789 123456789 123456789 123456789 123456789 123456789 123456789 123456789 123456789 0',
}
if __name__ == '__main__':

    for expected, actual in outputs.items():
        print('-' * 100)
        print('expected: ', repr(expected))
        print('-' * 100)
        print('coerced:  ', repr(coerce_text(expected)))
        print('-' * 100)
        # print(repr(quote(coerce_text(expected))))
        # print('-' * 100)
        print('pages:    ', repr(sms_api_endpoint(quote(coerce_text(expected)))))
        print('-' * 100)
        rendered = mobile_phone_render(*sms_api_endpoint(quote(coerce_text(expected)))).replace('\u2000', ' ')
        print('rendered: ', repr(rendered))
        print('=' * 100)
        print('actual:   ', repr(actual))
        print('=' * 100)

        # this was to test that the bug was correctly simulated
        # assert rendered == actual

        # this is to test that the bug was fixed
        assert rendered == expected
        print()
        print()
        print()
