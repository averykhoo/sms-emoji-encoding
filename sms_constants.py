# the charset supported by the SMS appliance
# note that this is not the full ASCII printable charset (eg. "`" is missing)
# nor is this the full GSM charset (eg. "€" is missing)
# the appliance incorrectly handles the remaining GSM chars (eg: "`" -> "?"; "£" -> "?£"; "å" -> "?¥"; "€" -> "???")
SMS_CHARSET = set('0123456789'  # all string.digits
                  'abcdefghijklmnopqrstuvwxyz'  # all string.ascii_lowercase
                  'ABCDEFGHIJKLMNOPQRSTUVWXYZ'  # all string.ascii_uppercase
                  '!"#$%&\'()*+,-./:;<=>?@[\\]^_{|}~'  # all punctuation, except "`"
                  ' \n\r\f'  # only space, LF, CR, FF (form feed)
                  )

# special chars used in re-encoding unicode
REPLACEMENT_CHARACTER_BE = '\uFFFD'
REPLACEMENT_CHARACTER_LE = '\uFDFF'
BOM_BE = '\uFEFF'  # aka ZWNBSP, although that specific use has been deprecated for this char
BOM_LE = '\uFFFE'

# these won't be supported by the re-encoder
UNSUPPORTED_CHARS = {
    # the sms appliance fails to send any page with a null
    '\0',  # null

    # bidi control characters are technically supported
    # but i don't understand them well enough to implement them correctly in the encoder
    # they'll need to be re-set between pages, as each page is parsed separately by the phone
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
