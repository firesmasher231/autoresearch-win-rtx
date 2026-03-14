# Running Karpathy's autoresearch on an RTX 4070 Laptop (8GB VRAM, Windows)

This guide walks through getting autoresearch running on an NVIDIA GeForce RTX 4070 Laptop GPU with 8GB VRAM on Windows. This setup is not officially supported by the upstream repo (which targets H100s) or the Windows RTX fork (which requires 10GB+ for Ada GPUs and excludes laptops). But it absolutely works with the right modifications.

Your RTX 4070 Laptop is Ada Lovelace architecture (compute capability 8.9), supports BF16 and TF32, and has significantly better tensor core throughput than the GTX 1660 Ti that someone already got working with only 6GB. You have more headroom than you might think.

---

## Prerequisites

- Windows 10/11 with an NVIDIA RTX 4070 Laptop GPU (8GB VRAM)
- NVIDIA drivers installed (you have 32.0.15.5597, which is fine)
- Python 3.10+ installed
- Git installed
- PowerShell (comes with Windows)

---

## Step 1: Install uv (package manager)

Open PowerShell and run:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Close and reopen PowerShell so `uv` is on your PATH.

---

## Step 2: Clone the repo and install dependencies

```powershell
git clone https://github.com/karpathy/autoresearch.git
cd autoresearch
uv sync
```

---

## Step 3: Modify prepare.py for your hardware

The upstream `prepare.py` has constants tuned for H100. You need to change three things. Open `prepare.py` in your editor and make these changes:

### 3a. Lower MAX_SEQ_LEN

Find:

```python
MAX_SEQ_LEN = 2048
```

Change to:

```python
MAX_SEQ_LEN = 512
```

This is the single biggest VRAM saver. The 1660 Ti guide used 512 and it worked well. With your faster GPU you could try 768 later, but start here.

### 3b. Reduce EVAL_TOKENS

Find:

```python
EVAL_TOKENS = 40 * 524288
```

Change to:

```python
EVAL_TOKENS = 10 * 524288
```

This cuts validation evaluation time significantly. On an H100 the full eval is fine, but on your laptop it would eat into the 5-minute training budget.

### 3c. Switch to TinyStories dataset

The default dataset (climbmix-400b) is a massive web crawl. For a small model on limited VRAM, the TinyStories dataset gives much better results because it is narrower in scope, which means smaller models can actually learn meaningful patterns from it.

Find the data source configuration. You need to change `BASE_URL` and `MAX_SHARD` to point to TinyStories instead of climbmix:

```python
BASE_URL = "https://huggingface.co/datasets/karpathy/tinystories_gpt4_clean/resolve/main"
```

You will also need to update `MAX_SHARD` to match however many shards the TinyStories dataset has. Check the dataset page at `https://huggingface.co/datasets/karpathy/tinystories_gpt4_clean` to confirm the shard count, and update `VAL_SHARD` accordingly.

**Note:** If the TinyStories dataset uses a different shard naming convention or format, you may need to adjust the download logic. The Windows RTX fork (`jsegov/autoresearch-win-rtx`) already has TinyStories as the default, so you can reference its `prepare.py` for the exact configuration.

### 3d. Optionally reduce vocab_size

Find:

```python
VOCAB_SIZE = 8192
```

You can optionally lower this to 4096 or even 2048 for faster tokenizer training and smaller embedding tables. This is less critical than the other changes but helps with VRAM:

```python
VOCAB_SIZE = 4096
```

---

## Step 4: Run data preparation

```powershell
uv run prepare.py
```

This downloads the data shards and trains a BPE tokenizer. Should take a couple of minutes.

---

## Step 5: Modify train.py for your hardware

This is where the real tuning happens. Open `train.py` and make these changes:

### 5a. Replace Flash Attention with SDPA

The upstream code imports Flash Attention 3, which will not work on your Ada laptop GPU. Find the FA3 import block near the top of the file:

```python
from kernels import get_kernel
cap = torch.cuda.get_device_capability()
repo = "varunneal/flash-attention-3" if cap == (9, 0) else "kernels-community/flash-attn3"
fa3 = get_kernel(repo).flash_attn_interface
```

**Comment out or delete this entire block.** You will not be using FA3.

Then, everywhere in the code where `fa3.flash_attn_func(q, k, v, causal=True, window_size=window_size)` is called, replace it with:

```python
torch.nn.functional.scaled_dot_product_attention(
    q.transpose(1, 2),
    k.transpose(1, 2),
    v.transpose(1, 2),
    is_causal=True
).transpose(1, 2)
```

The transposes handle the shape difference between FA3's expected layout (batch, seq, heads, dim) and SDPA's expected layout (batch, heads, seq, dim).

**Important:** This replacement drops sliding window attention support. The `window_size` parameter from FA3 has no direct equivalent in SDPA. This is fine because you are also going to change the window pattern to all global attention (see below).

### 5b. Reduce model depth (DEPTH)

Find the DEPTH constant (default is 8). This controls how many transformer layers the model has, and many other parameters are derived from it:

```python
DEPTH = 8
```

Change to:

```python
DEPTH = 4
```

This roughly halves the model size and VRAM usage. The 1660 Ti guide also used n_layer=4.

### 5c. Set WINDOW_PATTERN to global-only

Find:

```python
window_pattern = "SSSL"
```

Change to:

```python
window_pattern = "L"
```

The "SSSL" pattern uses alternating sliding window and global attention, which relies on the FA3 window_size parameter you just removed. "L" means all layers use global (long-range) attention, which works with SDPA.

### 5d. Reduce TOTAL_BATCH_SIZE

Find TOTAL_BATCH_SIZE (likely a large number like 2\*\*19 or similar). Change it to:

```python
TOTAL_BATCH_SIZE = 2**15  # 32768
```

You can go lower (2\*_14 = 16384) if you still hit OOM. The key constraint is that TOTAL_BATCH_SIZE must be a power of 2 and must be evenly divisible by (DEVICE_BATCH_SIZE _ MAX_SEQ_LEN).

### 5e. Set DEVICE_BATCH_SIZE

Find DEVICE_BATCH_SIZE. The upstream default is high (64 or 128). Set it to:

```python
DEVICE_BATCH_SIZE = 16
```

If you get OOM errors, drop to 8. The 1660 Ti guide used 8 with only 6GB, so 16 should work for your 8GB card since your GPU is much more efficient. The number of tokens per forward/backward pass is `DEVICE_BATCH_SIZE * MAX_SEQ_LEN`, so with batch=16 and seq=512 that is 8192 tokens per microbatch.

### 5f. Disable torch.compile

Find:

```python
model = torch.compile(model)
```

Comment it out:

```python
# model = torch.compile(model)
```

`torch.compile` on Windows with CUDA has historically been flaky, and it also uses extra VRAM for the compilation cache. Eager mode is slower per step but more reliable, and since the agent gets a fixed 5-minute budget, it will simply run fewer steps rather than crash.

---

## Step 6: Test a single run

Before going autonomous, verify everything works:

```powershell
$env:TORCH_DYNAMO_DISABLE="1"
$env:PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"
uv run train.py
```

The environment variables disable Dynamo (backup for the torch.compile comment-out) and enable expandable CUDA memory segments which reduce fragmentation on VRAM-constrained GPUs.

**What to expect:**

- The run should take about 5 minutes of training time, plus some startup overhead
- Peak VRAM should be somewhere in the 3-6 GB range (the 1660 Ti guide reported 1.7GB with even smaller settings, so you have room)
- You should see a final summary with `val_bpb` and other metrics
- If you get an OOM error, reduce DEVICE_BATCH_SIZE to 8

Record the baseline `val_bpb` number. This is what the agent will try to beat.

---

## Step 7: Set up git for the experiment loop

The autoresearch loop uses git to track experiments:

```powershell
git add -A
git commit -m "laptop baseline config"
git checkout -b autoresearch/laptop-mar13
```

Create `results.tsv` with just the header:

```powershell
echo "commit`tval_bpb`tmemory_gb`tstatus`tdescription" > results.tsv
```

(Use actual tab characters, or create the file in your editor with tab-separated columns: commit, val_bpb, memory_gb, status, description)

---

## Step 8: Update program.md for your setup

Open `program.md` and add constraints so the agent does not break your carefully tuned settings. Add something like this at the top or in the constraints section:

```markdown
## Hardware Constraints (DO NOT VIOLATE)

This machine is a Windows laptop with an RTX 4070 Laptop GPU (8GB VRAM).
The following settings are hard constraints to prevent OOM crashes:

- DO NOT use Flash Attention (fa3). Use torch.nn.functional.scaled_dot_product_attention only.
- DO NOT enable torch.compile. Always run in eager mode.
- DO NOT increase DEVICE_BATCH_SIZE above 16 (start at 16, go lower if OOM).
- DO NOT increase MAX_SEQ_LEN above 512 (this is set in prepare.py and cannot be changed).
- Keep DEPTH at 4 or below unless you also reduce embedding dimensions proportionally.
- Keep WINDOW_PATTERN as "L" (global attention only, no sliding window).
- Keep TOTAL_BATCH_SIZE as a power of 2, minimum 2\*\*14.
- Always run with: TORCH_DYNAMO_DISABLE=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

If a run OOMs, reduce batch size or model size. Do not try to fix OOM by other means.

## Run command
```

$env:TORCH_DYNAMO_DISABLE="1"; $env:PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"; uv run train.py

```

```

---

## Step 9: Launch the agent

Open Claude Code, Cursor, Windsurf, or whatever coding agent you prefer in the autoresearch directory. Give it permissions to read/write files and run terminal commands, but nothing else. Then prompt:

```
Read program.md first.

Now start the autonomous research loop:

1. Edit ONLY train.py to try to improve val_bpb (lower is better).
2. Keep all hardware constraints from program.md.
3. Run: set TORCH_DYNAMO_DISABLE=1 and PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True, then uv run train.py
4. Redirect output: uv run train.py > run.log 2>&1
5. Read out val_bpb from run.log. If better, git commit. If worse or equal, git reset --hard.
6. Log every experiment to results.tsv.
7. NEVER STOP. Do not ask me if you should continue. Keep running experiments until I manually stop you.

Start with the baseline run first.
```

---

## Step 10: Go to sleep

The agent should now loop through experiments autonomously. Each experiment takes about 5-6 minutes including overhead, so you can expect roughly 10 experiments per hour, or about 70-80 overnight.

**Laptop-specific tips for overnight runs:**

- **Plug in your charger.** Do not run on battery.
- **Set your power plan to High Performance.** In Windows Settings > System > Power & battery, set the power mode to Best Performance.
- **Prevent sleep.** Go to Settings > System > Power & battery > Screen and sleep, and set "When plugged in, put my device to sleep after" to Never.
- **Keep airflow clear.** Your laptop GPU will thermal throttle if it cannot breathe. Use a laptop stand or at minimum make sure the vents are not blocked. The RTX 4070 Laptop's TGP can range from 35W to 115W depending on power configuration, and sustained training will push it.
- **Monitor temperature.** Your GPU is at 48C idle. Under sustained load it will likely sit around 75-85C, which is normal for a laptop. If it goes above 90C consistently, you may want to reduce DEVICE_BATCH_SIZE further to lighten the thermal load.
- **Close other GPU-intensive applications.** Browsers with hardware acceleration, games, etc. all eat into your 8GB VRAM budget.

---

## Troubleshooting

**OOM (Out of Memory) errors:**
Drop DEVICE_BATCH_SIZE to 8. If still OOM, try DEPTH=3 or reduce n_embd.

**torch.compile errors or Triton errors:**
Make sure torch.compile is commented out and TORCH_DYNAMO_DISABLE=1 is set. Triton does not have official Windows support.

**"No module named kernels" or FA3 import errors:**
You did not fully remove the Flash Attention import block. Delete the entire `from kernels import get_kernel` section and all references to `fa3`.

**Training is very slow (fewer than 100 steps in 5 min):**
This is expected for a small model on a laptop. The agent will adapt. Fewer steps per experiment means each experiment covers less of the loss landscape, but the 5-minute budget ensures fairness.

**Agent stops or asks for confirmation:**
Restart it with the same prompt. The program.md has a "NEVER STOP" instruction but some agents still pause. Claude Code tends to be better about this than Cursor in my experience.

**val_bpb starts very high (above 2.0):**
Normal for a small model on the first run. The 1660 Ti guide reported ~1.98 as a starting point with similar settings. The agent will bring it down over successive experiments.

---

## What the agent can safely experiment with

Even within these tight constraints, the agent has a lot of room to explore:

- Learning rate and schedule (warmup steps, decay shape, peak LR)
- Optimizer hyperparameters (Muon momentum, AdamW betas, weight decay)
- Embedding dimensions (n_embd) relative to depth
- Number of attention heads and KV heads
- Activation functions (SiLU, GeLU, ReLU variants)
- Normalization approaches (RMSNorm, LayerNorm, QKNorm)
- Positional encoding variants (RoPE parameters)
- Initialization schemes
- Gradient clipping thresholds
- Any architectural changes that fit within the VRAM budget

The fixed 5-minute budget means the agent will naturally discover the best model configuration for your specific GPU. A change that is theoretically better but too slow to converge in 5 minutes on your hardware will get discarded in favor of something that actually improves val_bpb within the time constraint.

---

## References

- [karpathy/autoresearch](https://github.com/karpathy/autoresearch) (upstream repo)
- [Issue #87: Running on GTX 1660 Ti 6GB](https://github.com/karpathy/autoresearch/issues/87) (the guide this is based on)
- [jsegov/autoresearch-win-rtx](https://github.com/jsegov/autoresearch-win-rtx) (Windows fork, good reference for TinyStories config)
- [Karpathy's small-compute recommendations](https://github.com/karpathy/autoresearch#platform-support) (README section on tuning for smaller hardware)
