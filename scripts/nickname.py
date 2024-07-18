from itertools import count

TSV = lambda it: map(lambda x: tuple(x.rstrip("\n").split('\t')), it)
ordinal = lambda k, v: (ord(k), v)

# https://github.com/anyascii/anyascii
with open("extra/anyascii.tsv", "r") as fin:
    anyascii = dict(map(lambda w: ordinal(*w), TSV(fin)))

deuce = lambda x: "Deuce" if len(x) <= 0 else x
valid = lambda c: 0x20 <= ord(c) <= 0x7E and c != '%' and c != '#'
clean = lambda x: deuce(''.join(filter(valid, x.translate(anyascii).strip())))

def candidates(name):
    yield name

    for i in count(1):
        yield name + str(i)

def apply_script(protocol, connection, config):
    class NicknameProtocol(protocol):
        def get_name(self, text):
            taken = set(player.name for player in self.players.values())

            for name in candidates(clean(text)):
                if name not in taken:
                    return name

    return NicknameProtocol, connection