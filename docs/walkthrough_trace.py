"""Prints every number used in claude/pipeline-walkthrough.md (base B1 of examples/prototype_set).
Run from the pipeline folder: python docs/walkthrough_trace.py"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); os.chdir(sys.path[0])

from ukustim import config
from ukustim.core import fretboard as fb, chunks as ch, versions as vs
from ukustim.core.inventory import Inventory
from ukustim.core.fingering import valid_assignments, positions_of
from ukustim.formats import loader
from ukustim.family.trained import Trained
from ukustim.analysis import separability as sep, models as md
print("STEP1 pitches:", [fb.pitch_name(p) for p in fb.available_pitches()])
print("positions for E4:", [p.label() for p in fb.positions_for_pitch(64)], "G4:", [p.label() for p in fb.positions_for_pitch(67)], "A4:",[p.label() for p in fb.positions_for_pitch(69)])
inv=Inventory()
print("STEP2 chunks:", len(inv.chunks), [ch.chunk_id(c) for c in inv.chunks])
for c in [(60,62,60),(60,64,67),(60,62,62)]:
    print("  reject", ch.chunk_id(c), ch.within_chunk_problems(c))
CDE=(60,62,64); DEF=(62,64,65); EFG=(64,65,67); FGA=(65,67,69); GAB=(67,69,71); EDC=(64,62,60); ABC=(69,71,72)
for a,b in [(CDE,DEF),(DEF,EFG),(CDE,GAB),(CDE,ABC),(EDC,GAB),(CDE,EFG),(EDC,DEF)]:
    print("  junction",ch.chunk_id(a),"|",ch.chunk_id(b),"->",ch.junction_cues(a,b) or "NONE")
print("  graph successors of C-D-E:", [ch.chunk_id(x) for x in inv.graph[CDE]])
print("  edges:", sum(len(v) for v in inv.graph.values()), " orders:", len(inv.tuples))
print("STEP3 compositions total", len(vs.compositions()), "aligned", vs.aligned_composition(), "M=", sorted(vs.musical_boundaries()))
for d in (1,2,3): print("  degree",d, len(vs.misaligned_compositions(d)), [vs.comp_to_str(c) for c in vs.misaligned_compositions(d)][:6])
comp=(3,2,3,2,2)
print("  B(3-2-3-2-2)=",sorted(vs.boundaries(comp)),"degree",vs.degree(comp),"forbidden (M xor B)=",sorted(vs.forbidden_crossings(comp)))
print("STEP4 fingering options per chunk:", {ch.chunk_id(c): len(inv.opts[c]) for c in [CDE,DEF,EFG,FGA]})
print("  options of E-F-G:", [o.label() for o in inv.opts[EFG]])
t=(CDE,DEF,EFG,FGA)
A=list(valid_assignments(t,comp,inv.opts))
import itertools
total=1
for c in t: total*=len(inv.opts[c])
print("  B1 order: raw fingering combos", total, "-> valid", len(A))
for a in A[:6]:
    pos=positions_of(t,a,inv.opts); print("    ", " ".join(p.label() for p in pos), "crossings at", sorted(vs.string_crossings(pos)))
# show a rejected one
for a in itertools.product(*[range(len(inv.opts[c])) for c in t]):
    pos=positions_of(t,a,inv.opts)
    v=vs.neutrality_violations(pos,comp)
    if v:
        print("  rejected example:", " ".join(p.label() for p in pos), "crossing at forbidden", sorted(v)); break
items,reg,notes=loader.load_set("examples/prototype_set")
by={i.item_id:i for i in items}
B1=by["B1"]
print("STEP5 B1:", " ".join(p.label() for p in B1.positions), "comp", B1.composition)
print("  motor chunks full:", [m for _,_,m in vs.motor_chunks(B1.positions,B1.composition)])
print("  motor chunks lh:", [m for _,_,m in vs.motor_chunks(B1.positions,B1.composition,'lh')])
print("  crossing:", vs.crossing_motor_ids(B1.positions,B1.composition))
for k in ["B1-alt","B1-shift","B1-tr","B1-p-mode-swap","B1-p-transposition","B1-p-accent","R-both","R-musical","R-motor","X1","N1"]:
    if k in by:
        i=by[k]; print(" ",k,i.variant_type,"|"," ".join(p.label() for p in i.positions) if i.played else " ".join(fb.pitch_name(p) for p in i.pitches), "| chunks",i.chunk_ids, "| vel", i.velocities if i.velocities else "")
print("  notes:", notes)
tr=Trained(items)
for k in ["B1","B1-alt","B1-shift","R-both","R-musical","R-motor","X1","N1"]:
    print("  props",k,tr.proportions(by[k]), tr.recombination_type(by[k]) if by[k].variant_type=="recombined" else "")
print("STEP6 E1 items:", [i.item_id for i in sep._subset(items, sep.E1_VARIANTS)])
print("E2 items:", [i.item_id for i in sep._subset(items, sep.E2_VARIANTS)])
rep=sep.report(items)
for p,r in rep["e1"]["pairs"].items(): print("  E1",p,round(r,3))
for p,r in rep["e2"]["pairs"].items(): print("  E2",p,round(r,3))
print("  scores", sep.scores(items))
# small RDM illustration on 4 items
sub=[by[x] for x in ["B1","B1-alt","B2","R-musical"]]
R=md.model_rdms(sub,["musical_chunk","motor_chunk_misal_lh"])
import numpy as np; np.set_printoptions(precision=2,suppress=True)
print("  musical_chunk RDM B1,B1-alt,B2,R-musical\n",R["musical_chunk"]); print("  motor_lh RDM\n",R["motor_chunk_misal_lh"])
# build spec v1.7: C-VIII collinearity and the descriptive M-IV / A-IV reports (walkthrough step 9)
c8 = rep["c8"]
print("C-VIII multiple R / VIF:", {c: (round(float(v["R"]), 2), round(float(v["vif"]), 2)) for c, v in c8["components"].items()})
d = rep["descriptive"]
print("M-IV:", {k: round(v, 2) for k, v in d["m4"].items()})
print("A-IV:", {k: round(v, 2) for k, v in d["a4"].items()}, d["a4_variance"])
