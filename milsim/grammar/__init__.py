from milsim.grammar.category import (
    GrammarError,
    Number, SG, PL,
    Person, P1ST, P2ND, P3RD,
    Case, NOM, OBL, POS,
    Tense, PRES, PAST,
    VerbForm, INF, PTCP1, PTCP2
)

from milsim.grammar.verb import Verb, ModalVerb, SemiregularVerb, RegularVerb
from milsim.grammar.noun import Noun, SemiregularNoun, RegularNoun

from milsim.grammar.syntax import NP, VP, Sentence

from milsim.grammar.np import (
    ProperNoun, ZeroArticle, Determiner, Possessive, Cardinal, Ordinal,
    Pronoun, Adjective, NotNP, InfinitivePhrase, Gerund
)
from milsim.grammar.vp import (
    AdverbPrefix, AdverbPostfix, VerbNTR, VerbNP, VerbNPPP, VerbVP, VerbVPPP
)
from milsim.grammar.sentence import (
    Declarative, YesNoInterrogative, Imperative, Compound
)

DET = NP[Noun]

def np_vp_pres(np : NP, vp : VP):
    s = Declarative(np = np, vp = vp, tense = PRES)
    return linearize(s)

def np_vp_past(np : NP, vp : VP):
    s = Declarative(np = np, vp = vp, tense = PAST)
    return linearize(s)

def wordspacing(tokens):
    if head := next(tokens, None):
        yield head.capitalize()
    else:
        return

    for token in tokens:
        if token not in {".", ",", ";", ":", "?", "!"}:
            yield " "

        yield token

def linearize(s : Sentence) -> str:
    return "".join(wordspacing(s.linearize()))

I_pr    = Pronoun(person = P1ST, number = SG, nom = "I",    obl = "me",   pos = "my")
mine_pr = Pronoun(person = P1ST, number = SG, nom = "mine", obl = "mine", pos = "mine's")
you_pr  = Pronoun(person = P2ND, number = SG, nom = "you",  obl = "you",  pos = "your")
he_pr   = Pronoun(person = P3RD, number = SG, nom = "he",   obl = "him",  pos = "his")
she_pr  = Pronoun(person = P3RD, number = SG, nom = "she",  obl = "her",  pos = "her")
it_pr   = Pronoun(person = P3RD, number = SG, nom = "it",   obl = "it",   pos = "its")
we_pr   = Pronoun(person = P1ST, number = PL, nom = "we",   obl = "us",   pos = "our")
they_pr = Pronoun(person = P3RD, number = PL, nom = "they", obl = "them", pos = "their")

song_n  = RegularNoun("song")
light_n = RegularNoun("light")

be_v = Verb(
    inf   = "be",   ving  = "being", ved   = "been",
    v1sg  = "am",   v2sg  = "are",   v3sg  = "is",
    v1pl  = "are",  v2pl  = "are",   v3pl  = "are",
    vp1sg = "was",  vp2sg = "were",  vp3sg = "was",
    vp1pl = "were", vp2pl = "were",  vp3pl = "were"
)

do_v   = SemiregularVerb(bare = "do", ving = "doing", ved = "done", v3sg = "does", vpast = "did")
have_v = SemiregularVerb(bare = "have", ving = "having", ved = "had", v3sg = "has", vpast = "had")
can_v  = ModalVerb(vpres = "can", vpast = "could")
will_v = ModalVerb(vpres = "will", vpast = "would")
go_v   = SemiregularVerb(bare = "go", ving = "going", ved = "gone", v3sg = "goes", vpast = "went")
give_v = SemiregularVerb(bare = "give", ving = "giving", ved = "given", v3sg = "gives", vpast = "gave")
sing_v = SemiregularVerb(bare = "sing", ving = "singing", ved = "sung", v3sg = "sings", vpast = "sang")
put_v  = SemiregularVerb(bare = "put", ving = "putting", ved = "put", v3sg = "puts", vpast = "put")
turn_v = RegularVerb("turn")

zero_sg   = ZeroArticle(SG)
zero_pl   = ZeroArticle(PL)
the_sg    = Determiner("the", SG)
the_pl    = Determiner("the", PL)
a_sg      = Determiner("a", SG)
an_sg     = Determiner("an", SG)
no_sg     = Determiner("no", SG)
no_pl     = Determiner("no", PL)
this_det  = Determiner("this", SG)
these_det = Determiner("these", PL)
that_det  = Determiner("that", SG)
those_det = Determiner("those", PL)
each_det  = Determiner("each", SG)
every_det = Determiner("every", SG)
any_sg    = Determiner("any", SG)
any_pl    = Determiner("any", PL)
some_sg   = Determiner("some", SG)
some_pl   = Determiner("some", PL)

bad_adj  = Adjective("bad")
good_adj = Adjective("good")

not_adv = AdverbPrefix("not")

be_vp    = VerbNP(be_v)
have_fvp = VerbVP(have_v.finite(), PTCP2)

def PerfectAspect(vp : VP) -> VP:
    return have_fvp(vp)

def ProgressiveAspect(vp : VP) -> VP:
    return be_vp(Gerund(vp))

def PassiveVoice(verb : Verb, agent = None) -> VP:
    if agent is None:
        vp = VerbVP(be_v, PTCP2)
        return vp(verb)
    else:
        vp = VerbVPPP(be_v, PTCP2, "by")
        return vp(verb, agent)