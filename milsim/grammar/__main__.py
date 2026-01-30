# Copyright © 2026 rzrn

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from milsim.grammar import (
    Declarative, YesNoInterrogative, Imperative, Compound, VerbNTR, InfinitivePhrase, Possessive, Cardinal, Ordinal,
    PassiveVoice, PerfectAspect, ProgressiveAspect, RegularNoun, CompoundNoun, SemiregularVerb, RegularVerb,
    linearize, VerbVP, VerbNP, VerbNPPP, this_pr, that_pr, zero_sg, zero_pl, an_sg, the_sg, the_pl, not_adv, good_adj,
    I_pr, you_pr, he_pr, she_pr, it_pr, light_n, song_n, be_v, do_v, can_v, turn_v, give_v, sing_v,
    PRES, PAST, SG, INF, PTCP2
)

# Some useful examples & tests of this formal grammar.
# To run these use `python -m milsim.grammar`.

################################
player_n = RegularNoun("player")

be_vp = VerbNP(be_v)

np1 = I_pr
vp1 = be_vp(good_adj(an_sg(player_n)))

s1 = Declarative(np = np1, vp = vp1, tense = PRES)
print("1)", linearize(s1))

##########################################
turn_off_vp = VerbNP(turn_v, ptcl = "off")

np2 = you_pr
vp2 = turn_off_vp(the_pl(light_n))

s2 = Declarative(np = np2, vp = vp2, tense = PAST)
print("2)", linearize(s2))

#####################################
do_fvp = VerbVP(do_v.finite(), PTCP2)

np3 = the_sg(player_n)
vp3 = do_fvp(vp2) # As an auxiliary verb “do” exists only in finite forms.

s3 = YesNoInterrogative(np = np3, vp = vp3, tense = PAST)
print("3)", linearize(s3))

############################
like_v = RegularVerb("like")
like_vp = VerbNP(like_v)

play_v = RegularVerb("play")

np4 = I_pr
vp4 = like_vp(InfinitivePhrase(VerbNTR(play_v)))

s4 = Declarative(np = np4, vp = vp4, tense = PAST)
print("4)", linearize(s4))

############################
hand_n = RegularNoun("hand")

bandage_v = RegularVerb("bandage")
bandage_vp = VerbNP(bandage_v)

player_poss_np = Possessive(the_pl(player_n), SG)
vp5 = bandage_vp(player_poss_np(hand_n))

s5 = Imperative(vp = vp5)
print("5)", linearize(s5))

###################################
give_to_vp = VerbNPPP(give_v, "to")

s6 = Declarative(np = I_pr, vp = give_to_vp(it_pr, he_pr), tense = PAST)
print("6)", linearize(s6))

############################
s7 = Compound(s1, s4, "and")
print("7)",linearize(s7))

#####################
np8 = the_pl(light_n)
vp8 = PassiveVoice(VerbNTR(turn_v, ptcl = "off"))

s8 = Declarative(np = np8, vp = vp8, tense = PAST)
print("8)", linearize(s8))

########################################
vp9 = ProgressiveAspect(VerbNTR(play_v))

s9 = Declarative(np = I_pr, vp = vp9, tense = PRES)
print("9)", linearize(s9))

##########################
toy_n = RegularNoun("toy")

vp10 = ProgressiveAspect(PassiveVoice(VerbNTR(play_v, ptcl = "with")))

s10 = Declarative(np = zero_pl(toy_n), vp = vp10, tense = PAST)
print("10)", linearize(s10))

#########################
sing_vp = VerbNTR(sing_v)

vp11 = ProgressiveAspect(PassiveVoice(sing_vp, agent = she_pr))

s11 = Declarative(np = an_sg(song_n), vp = vp11, tense = PRES)
print("11)", linearize(s11))

###########################
can_vp = VerbVP(can_v, INF)

vp12 = can_vp(not_adv(VerbNTR(play_v)))

s12 = Declarative(np = he_pr, vp = vp12, tense = PRES)
print("12)", linearize(s12))

#############################
np13 = Cardinal(32, player_n)
vp13 = ProgressiveAspect(VerbNTR(play_v))

s13 = Declarative(np = np13, vp = vp13, tense = PRES)
print("13)", linearize(s13))

##########################
die_v = RegularVerb("die")

np14 = Ordinal(1, the_sg(player_n))
vp14 = VerbNTR(die_v)

s14 = Declarative(np = np14, vp = vp14, tense = PAST)
print("14)", linearize(s14))

###################################################################################################
eat_v = SemiregularVerb(bare = "eat", ving = "eating", ved = "eaten", v3sg = "eats", vpast = "ate")

eat_vp = VerbNTR(eat_v)

# `ProgressiveAspect(PerfectAspect(eat_vp))` will throw an exception.
vps15 = [eat_vp, ProgressiveAspect(eat_vp), PerfectAspect(eat_vp), PerfectAspect(ProgressiveAspect(eat_vp))]

from itertools import product
for k, (tense, vp) in enumerate(product([PRES, PAST], vps15), start = 1):
    s = Declarative(np = I_pr, vp = vp, tense = tense)
    print("15.{}) {}".format(k, linearize(s)))

##############################
apple_n = RegularNoun("apple")
banana_n = RegularNoun("banana")

s16_1 = Declarative(np = this_pr, vp = be_vp(an_sg(apple_n)), tense = PRES)
s16_2 = Declarative(np = that_pr, vp = be_vp(an_sg(banana_n)), tense = PRES)

s16 = Compound(s16_1, s16_2, "and")
print("16)", linearize(s16))

##############################
cream_n = RegularNoun("cream")

ice_cream_n = CompoundNoun("ice", cream_n)
s17 = Declarative(np = I_pr, vp = like_vp(zero_sg(ice_cream_n)), tense = PRES)
print("17)", linearize(s17))