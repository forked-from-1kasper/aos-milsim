from milsim.grammar.syntax import HasEmit

# https://github.com/GrammaticalFramework/gf-rgl/blob/master/src/english/ResEng.gf
class AnToken(HasEmit):
    @staticmethod
    def emit(rem):
        word = next(rem)

        if word.startswith(("eu", "Eu", "uni", "up")):
            yield "a"
        elif word.startswith("un"):
            yield "an"
        elif word.startswith(("a", "e", "i", "o", "A", "E", "I", "O")):
            yield "an"
        elif word.startswith(("SMS", "sms")):
            yield "an"
        else:
            yield "a"

        yield word

def possessify(w):
    if w is None:
        return

    if w[-1] == 's':
        return w + "'"
    else:
        return w + "'s"

# https://github.com/GrammaticalFramework/gf-rgl/blob/master/src/english/ParadigmsEng.gf
def pluralize(w):
    if w.endswith(("io", "oo")):
        return w + "s"
    elif w.endswith(("s", "z", "x", "sh", "ch", "o")):
        return w + "es"
    elif w.endswith(("ay", "oy", "uy", "ey")):
        return w + "s"
    elif w.endswith("y"):
        return w.removesuffix("y") + "ies"
    else:
        return w + "s"

ascii_vowels = {'a', 'e', 'i', 'o', 'u'}

# https://github.com/GrammaticalFramework/gf-rgl/blob/master/src/english/ParadigmsEng.gf
def dupfin(w):
    if w[-3] in {'a', 'e', 'o'} and w[-2] in ascii_vowels:
        return w
    elif w[-2] in ascii_vowels and w[-1] in {'b', 'd', 'g', 'm', 'n', 'p', 'r', 't'}:
        return w + w[-1]
    else:
        return w

def ingize(w):
    if w.endswith("ee"):
        return w + "ing"
    elif w.endswith("ie"):
        return w.removesuffix("ie") + "ying"
    elif w.endswith("e"):
        return w.removesuffix("e") + "ing"
    elif w.endswith("er"):
        return w + "ing"
    else:
        return dupfin(w) + "ing"

def regularize(cry):
    cries = pluralize(cry) # ???

    if cries.endswith("es"):
        cried = cries.removesuffix("s") + "d"
    elif cries.endswith("ers"):
        cried = cries.removesuffix("s") + "ed"
    else:
        cried = dupfin(cry) + "ed"

    crying = ingize(cry)

    return cries, crying, cried

def cardinal(k : int) -> str:
    return str(k)

def indicator(k : int) -> str:
    if k < 0: raise GrammarError

    if 11 <= k % 100 <= 13:
        return "th"

    match k % 10:
        case 1: return "st"
        case 2: return "nd"
        case 3: return "rd"

    return "th"

def ordinal(k : int) -> str:
    return str(k) + indicator(k)
