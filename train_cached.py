"""Train + eval the v2 student on whatever teacher games are ALREADY in the gen cache.

Use this if you stop full_student_v2.py mid-generation: it loads the partial cache, trains the
net, and reports teacher + student winrate vs the heuristic. (full_student_v2 only trains after
ALL games are generated; this lets you cash in partial data.)

Usage: python train_cached.py [cache.pkl] [epochs]
   e.g. python train_cached.py artifacts/full_v2_gen_400_6000.pkl 60
"""
import os

_THREADS = str(min(10, os.cpu_count() or 4))
for _v in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ.setdefault(_v, _THREADS)

import pickle
import sys

import full_encoder as fe
from full_distill import train
from full_student_v2 import eval_student

if __name__ == '__main__':
    import torch
    torch.set_num_threads(min(10, os.cpu_count() or 4))
    cache = sys.argv[1] if len(sys.argv) > 1 else 'artifacts/full_v2_gen_400_6000.pkl'
    EP = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    ck = pickle.load(open(cache, 'rb'))
    data, w, n = ck['data'], ck['w'], ck['n']
    print(f"cached: {n} teacher games, {len(data)} decisions | TEACHER seat-win {w}/{n}={w/n:.1%}", flush=True)
    print(f"training {EP} epochs on the partial data...", flush=True)
    net = fe.make_net()
    train(net, data, EP)
    os.makedirs('artifacts', exist_ok=True)
    torch.save(net.state_dict(), 'artifacts/full_student_v2.pt')
    sw, hw = eval_student(net, 400)
    print(f"\n  STUDENT v2: {sw:.1%}  | HEURISTIC {hw:.1%}  | edge {sw-hw:+.1%}")
    print(f"  TEACHER@(partial {n} games): {w/n:.1%}")
