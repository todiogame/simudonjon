# RL Training Bootstrap

Use a fresh environment for RL work. The historical `venv` in this repo may point at a missing interpreter.

```powershell
py -3.10 -m venv .venv-train
.\.venv-train\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install --upgrade setuptools wheel pytest numpy pandas tqdm
pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
python rl_train.py env
```

`rl_train.py env` should report `cuda_available=True` on the RTX 3070. If CUDA is still unavailable, `rl_train.py` automatically falls back to CPU.

## Commands

Smoke check:

```powershell
python rl_train.py smoke
python rl_train.py smoke-checkpoint
```

Benchmark rollout throughput:

```powershell
python rl_train.py benchmark --episodes 128
```

Run the progressive trainer:

```powershell
python rl_train.py train --run-dir artifacts/rl --num-workers 8
```

Resume from the latest checkpoint:

```powershell
python rl_train.py train --resume artifacts/rl/checkpoints/progressive_latest.pt
```

Print the policy comparison table:

```powershell
python rl_train.py report --checkpoint artifacts/rl/checkpoints/progressive_best.pt --episodes 1000 --num-workers 8
```

Artifacts are written under the chosen run directory:

- `metrics.csv`
- `metrics.jsonl`
- `checkpoints/progressive_latest.pt`
- `checkpoints/progressive_best.pt`
- `checkpoints/progressive_success.pt` when the default-policy gate is reached
