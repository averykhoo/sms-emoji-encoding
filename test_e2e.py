import string
from urllib.parse import quote

from sms_gateway_mock import mobile_phone_render
from sms_gateway_mock import sms_api_endpoint
from sms_message_encoder import coerce_text


def end_to_end_text_equality(text: str, max_pages: int = 5) -> bool:
    """
    end to end test of encoding, gateway processing, and parsing
    this should return true for most input strings

    :param text: text the test against
    :param max_pages: number of sms pages
    """
    output = mobile_phone_render(*sms_api_endpoint(quote(coerce_text(text, max_pages=max_pages))))
    if text == output:
        return True

    print('expected:', text)
    print('received:', output)
    return False


def test_end_to_end():
    test_strings = [
        string.printable * 3,
        string.digits * 10,  # 10 * 10 chars
        string.ascii_letters * 5,  # 26 * 2 * 5 chars
        string.whitespace * 10,

        # edge cases
        '\uFEFF\uFEFF.',
        '\uFEFF\uFFFE.',
        '\uFFFE\uFEFF.',
        '\uFFFE\uFFFE.',
        ('\uFEFF' * 61 + '.') * 3,  # 61 + 1 + leading BOM = 63 per page
        ('\uFFFE' * 61 + '.') * 3,  # 61 + 1 + leading BOM = 63 per page

        # emoji sentences
        '❌️-😢-🔚-😀-✨✨✨',  # Don't cry because it's over, smile because it happened
        # '📚️📚️📚️📚️ ⏳😀⌛️😭',  # So many books, so little time. -> not possible, requires U+DCDA
        '🐝🔀🙏👁️👁️➡️🌎',  # Be the change that you wish to see in the world
        '❌🎶🎵🎶❌ ⬇️⬇️⬇️⬇️⬇️ ❌🆒❌🆒❌',  # Without music, life would be a mistake
        '✋🤬⬆️😈',  # I solemnly swear I'm up to no good
        '☝️⏲️😠 ⬇️⬇️⬇️⬇️⬇️⬇️ ❌6⃣0⃣⏲️😄❌ ⬇️⬇️⬇️⬇️⬇️⬇️ 😢😭😢😭😢😭',
        # For every minute you are angry you lose sixty seconds of happiness

        # pangrams
        'The quick brown fox jumps over a lazy dog.',
        'Jackdaws love my big sphinx of quartz.',

        # phonetic pangrams
        'Are those shy Eurasian footwear, cowboy chaps, or jolly earthmoving headgear?',
        'The beige hue on the waters of the loch impressed all, including the French queen,'
        ' before she heard that symphony again, just as young Arthur wanted.',

        # non-english test sentences for Chinese, since it's not possible to have a pangram
        '視野無限廣，窗外有藍天',
        '微風迎客，軟語伴茶',
        'Innovation in China 中国智造，慧及全球 0123456789',
        '他很不耐烦，总是在我说到一半的时候就打断我。',

        # non-english pangrams (skip RTL languages since BiDi is not supported)
        'Zəfər, jaketini də papağını da götür, bu axşam hava çox soyuq olacaq.',  # Azeri
        'Жълтата дюля беше щастлива, че пухът, който цъфна, замръзна като гьон.',  # Bulgarian
        '«Dóna amor que seràs feliç!». Això, il·lús company geniüt, ja és un lluït rètol blavís d’onze kWh.',  # Catalan
        'ᎠᏍᎦᏯᎡᎦᎢᎾᎨᎢᎣᏍᏓᎤᎩᏍᏗᎥᎴᏓᎯᎲᎢᏔᎵᏕᎦᏟᏗᏖᎸᎳᏗᏗᎧᎵᎢᏘᎴᎩ '
        'ᏙᏱᏗᏜᏫᏗᏣᏚᎦᏫᏛᏄᏓᎦᏝᏃᎠᎾᏗᎭᏞᎦᎯᎦᏘᏓᏠᎨᏏᏕᏡᎬᏢᏓᏥᏩᏝᎡᎢᎪᎢ '
        'ᎠᎦᏂᏗᎮᎢᎫᎩᎬᏩᎴᎢᎠᏆᏅᏛᎫᏊᎾᎥᎠᏁᏙᎲᏐᏈᎵᎤᎩᎸᏓᏭᎷᏤᎢᏏᏉᏯᏌᏊ '
        'ᎤᏂᏋᎢᏡᎬᎢᎰᏩᎬᏤᎵᏍᏗᏱᎩᎱᎱᎤᎩᎴᎢᏦᎢᎠᏂᏧᏣᏨᎦᏥᎪᎥᏌᏊᎤᎶᏒᎢᎢᏡᎬᎢ '
        'ᎹᎦᎺᎵᏥᎻᎼᏏᎽᏗᏩᏂᎦᏘᎾᎿᎠᏁᎬᎢᏅᎩᎾᏂᎡᎢᏌᎶᎵᏎᎷᎠᏑᏍᏗᏪᎩ '
        'ᎠᎴ ᏬᏗᏲᏭᎾᏓᏍᏓᏴᏁᎢᎤᎦᏅᏮᏰᎵᏳᏂᎨᎢ.',  # Cherokee
        'ཨ་ཡིག་དཀར་མཛེས་ལས་འཁྲུངས་ཤེས་བློའི་གཏེར༎ '
        'ཕས་རྒོལ་ཝ་སྐྱེས་ཟིལ་གནོན་གདོང་ལྔ་བཞིན༎ '
        'ཆགས་ཐོགས་ཀུན་བྲལ་མཚུངས་མེད་འཇམ་དབྱངསམཐུས༎ '
        'མཧཱ་མཁས་པའི་གཙོ་བོ་ཉིད་འགྱུར་ཅིག།',  # Dzongkha
        'Wieniläinen sioux’ta puhuva ökyzombie diggaa Åsan roquefort-tacoja.',  # Finnish
        'Falsches Üben von Xylophonmusik quält jeden größeren Zwerg',  # German
        'Ταχίστη αλώπηξ βαφής ψημένη γη, δρασκελίζει υπέρ νωθρού κυνός',  # Greek
        'Takhístè alôpèx vaphês psèménè gè, draskelízei ypér nòthroý kynós',  # Greek transliterated
        'ऋषियों को सताने वाले दुष्ट राक्षसों के राजा रावण का सर्वनाश करने वाले विष्णुवतार भगवान श्रीराम, '
        'अयोध्या के महाराज दशरथ के बड़े सपुत्र थे।',  # Hindi
        'Kæmi ný öxi hér, ykist þjófum nú bæði víl og ádrepa.',  # Icelandic
        'Nne, nna, wepụ he’l’ụjọ dum n’ime ọzụzụ ụmụ, vufesi obi nye Chukwu, ṅụrịanụ, gbakọọnụ kpaa, '
        'kwee ya ka o guzoshie ike; ọ ghaghị ito, nwapụta ezi agwa.',  # Igbo
        'あめ つち ほし そら'
        'やま かは みね たに'
        'くも きり むろ こけ'
        'ひと いぬ うへ すゑ'
        'ゆわ さる おふせよ'
        'えの𛀁を なれゐて',  # Japanese  (Ametsuchi no Uta, hiragana)
        'いろはにほへと ちりぬるを わかよたれそ つねならむ うゐのおくやま けふこえて あさきゆめみし ゑひもせす',  # Japanese
        '꧋ ꦲꦤꦕꦫꦏ꧈ ꦢꦠꦱꦮꦭ꧈ ꦥꦝꦗꦪꦚ꧈ ꦩꦒꦧꦛꦔ꧉',  # Javanese
        '    ',  # Klingon
        '키스의 고유조건은 입술끼리 만나야 하고 특별한 기술은 필요치 않다.',  # Korean
        'Glāžšķūņa rūķīši dzērumā čiepj Baha koncertflīģeļu vākus.',  # Latvian
        'Įlinkdama fechtuotojo špaga sublykčiojusi pragręžė apvalų arbūzą',  # Lithuanian
        'Мојот дружељубив коњ со тих галоп фаќа брз џиновски глушец по туѓо ѕитче.',  # Macedonian
        'അജവും ആനയും ഐരാവതവും ഗരുഡനും കഠോര സ്വരം പൊഴിക്കെ ഹാരവും '
        'ഒഢ്യാണവും ഫാലത്തില്‍ മഞ്ഞളും ഈറന്‍ കേശത്തില്‍ ഔഷധ എണ്ണയുമായി ഋതുമതിയും '
        'അനഘയും ഭൂനാഥയുമായ ഉമ ദുഃഖഛവിയോടെ ഇടതു പാദം ഏന്തി ങ്യേയാദൃശം '
        'നിര്‍ഝരിയിലെ ചിറ്റലകളെ ഓമനിക്കുമ്പോള്‍ ബാ‍ലയുടെ കണ്‍കളില്‍ നീര്‍ ഊര്‍ന്നു വിങ്ങി.',  # Malayalam
        'Щётканы фермд пийшин цувъя. Бөгж зогсч хэльюү.',  # Mongolian
        'သီဟိုဠ်မှ ဉာဏ်ကြီးရှင်သည် အာယုဝဍ္ဎနဆေးညွှန်းစာကို '
        'ဇလွန်ဈေးဘေးဗာဒံပင်ထက် အဓိဋ္ဌာန်လျက် ဂဃနဏဖတ်ခဲ့သည်။',  # Burmese
        'Широкая электрификация южных губерний даст мощный толчок подъёму сельского хозяйства.',  # Russian
        'कः खगौघाङचिच्छौजा झाञ्ज्ञोऽटौठीडडण्ढणः। तथोदधीन् पफर्बाभीर्मयोऽरिल्वाशिषां सहः।। ',  # Sanskrit
        'La niña, viéndose atrapada en el áspero baúl índigo y sintiendo asfixia, lloró de vergüenza;'
        ' mientras que la frustrada madre llamaba a su hija diciendo: “¿Dónde estás Waleska?”',  # Spanish
        'Jovencillo emponzoñado de whisky: ¡qué figurota exhibe!',  # Spanish
        'เป็นมนุษย์สุดประเสริฐเลิศคุณค่า '
        'กว่าบรรดาฝูงสัตว์เดรัจฉาน '
        'จงฝ่าฟันพัฒนาวิชาการ '
        'อย่าล้างผลาญฤๅเข่นฆ่าบีฑาใคร '
        'ไม่ถือโทษโกรธแช่งซัดฮึดฮัดด่า '
        'หัดอภัยเหมือนกีฬาอัชฌาสัย '
        'ปฏิบัติประพฤติกฎกำหนดใจ '
        'พูดจาให้จ๊ะๆ จ๋าๆ น่าฟังเอยฯ',  # Thai
        '༈ དཀར་མཛེས་ཨ་ཡིག་ལས་འཁྲུངས་ཡེ་ཤེས་གཏེར། །ཕས་རྒོལ་ཝ་སྐྱེས་ཟིལ་གནོན་གདོང་ལྔ་བཞིན། '
        '།ཆགས་ཐོགས་ཀུན་བྲལ་མཚུངས་མེད་འཇམ་བྱངས་མཐུས། །མ་ཧཱ་མཁས་པའི་གཙོ་བོ་ཉིད་གྱུར་ཅིག།',  # Tibetan
        'Pijamalı hasta yağız şoföre çabucak güvendi.',  # Turkish
        'Vakfın çoğu bu huysuz genci plajda görmüştü.',  # Turkish
        'Жебракують філософи при ґанку церкви в Гадячі, ще й шатро їхнє п’яне знаємо.',  # Ukrainian
        'Ìwò̩fà ń yò̩ séji tó gbojúmó̩, ó hàn pákànpò̩ gan-an nis̩é̩ rè̩ bó dò̩la.',  # Yoruba
        'Parciais fy jac codi baw hud llawn dŵr ger tŷ Mabon.',  # Welsh
    ]
    for test_string in test_strings:
        if not end_to_end_text_equality(test_string):
            print('failed')


if __name__ == '__main__':
    test_end_to_end()
