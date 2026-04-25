# Local FLUX Image Generation Setup (GTX 1070)

**Cost:** FREE (after hardware) | **Speed:** 30-45 sec/image | **Quality:** 9.5/10 ⭐

> This guide helps you run FLUX.1 [schnell] locally on a GTX 1070 (8GB VRAM) for affiliate product photography.

---

## Prerequisites

- **GPU:** NVIDIA GTX 1070 (8GB VRAM minimum)
- **VRAM:** 8GB (GTX 1070, RTX 3060, RTX 4060)
- **System RAM:** 16GB+ recommended
- **Disk Space:** ~6GB for model download + inference cache
- **OS:** Linux, macOS (slower), or Windows (slower)
- **CUDA:** NVIDIA CUDA Toolkit 11.8+ installed (`nvidia-smi` should work)

---

## Installation (5-10 minutes)

### 1. Install PyTorch with CUDA support

```bash
# For CUDA 11.8 (recommended for GTX 1070)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Verify installation
python3 -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA available: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"None\"}')"
```

### 2. Install FLUX dependencies

```bash
cd /path/to/hotproductsdot-v2
pip install -r requirements-flux.txt
```

### 3. Pre-download the FLUX model (~5.5GB)

**First run will auto-download, but it's better to pre-download:**

```bash
python3 -c "
from instagram.image_gen_local_flux import _get_flux_pipeline
print('Downloading FLUX.1 [schnell]...')
_get_flux_pipeline()
print('✓ Model downloaded and cached')
"
```

This takes 5-10 minutes depending on internet speed. The model is cached in `~/.cache/huggingface/`.

---

## Usage

### Quick Test (dry-run, 1 image)

```bash
python3 post_daily.py --dry-run --use-local-flux
```

**Expected output:**
```
>> Generating 5 image variants with local FLUX.1 [schnell]...
   ⚠️  WARNING: GTX 1070 will be SLOW (30-45 sec per image, ~2-4 min total)
  [1/5] banner       ... ✓ (38.2s)
  [2/5] studio_dark  ... ✓ (35.1s)
  [3/5] lifestyle    ... ✓ (34.8s)
  [4/5] vibrant      ... ✓ (36.5s)
  [5/5] detail       ... ✓ (35.3s)
```

### Actual Posting

```bash
# Generate + post to Instagram
python3 post_daily.py --use-local-flux --platform instagram

# Generate + post to TikTok
python3 post_daily.py --use-local-flux --platform tiktok

# Generate + post to both
python3 post_daily.py --use-local-flux --platform all
```

---

## Performance Expectations

| GPU | Model | Speed | VRAM Used |
|-----|-------|-------|-----------|
| **GTX 1070** | FLUX schnell | 30-45 sec/image | 7.2-7.8 GB |
| GTX 3060 12GB | FLUX schnell | 20-35 sec/image | 8-9 GB |
| RTX 4070 | FLUX schnell | 8-15 sec/image | 8-10 GB |
| RTX 4090 | FLUX schnell | 3-8 sec/image | 10-12 GB |

**For 5 product images on GTX 1070:** ~2.5-4 minutes

### Memory Optimization Tips

If you get "out of memory" errors:

```python
# In image_gen_local_flux.py, modify _get_flux_pipeline():
pipeline.enable_attention_slicing()  # Already enabled
pipeline.enable_memory_efficient_attention()  # Add this

# Or use more aggressive settings:
import torch
torch.cuda.empty_cache()  # Clear GPU cache before generation
```

---

## Troubleshooting

### "CUDA out of memory"

**Solution:** Your GTX 1070 is struggling with 8GB. Try:

```bash
# Clear GPU cache
python3 -c "import torch; torch.cuda.empty_cache()"

# Run with smaller resolution (768x768 instead of 1024x1024)
# Edit image_gen_local_flux.py line 285: width=768, height=768
```

### "Module not found: image_gen_local_flux"

**Solution:** Make sure the file exists:

```bash
ls -la instagram/image_gen_local_flux.py
```

If missing, re-download or recreate it.

### GPU not detected ("CUDA available: False")

**Solution:** Install CUDA properly:

```bash
# Check if CUDA is installed
nvidia-smi

# If not, install CUDA Toolkit 11.8:
# https://developer.nvidia.com/cuda-11-8-0-download-archive

# Then reinstall PyTorch:
pip install --force-reinstall torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### Generation is extremely slow (>2 minutes per image)

**Possible causes:**
1. Using CPU instead of GPU (check `torch.cuda.is_available()`)
2. Model is on disk instead of VRAM (first generation is always slow)
3. System swap is active (disable if possible)

---

## Cost Comparison

| Method | Cost/100 images | Speed | Quality | Setup |
|--------|-----------------|-------|---------|-------|
| **Local FLUX (GTX 1070)** | $0 | 30-45s | 9.5/10 | 1 hour |
| FLUX via Replicate | $2.50 | 8-12s | 9.5/10 | 5 min |
| Stability AI | $13-18 | 5-15s | 8.5/10 | 10 min |
| ModelsLab | $10+ | 8-12s | 8/10 | Broken 💀 |

**Local FLUX wins for:** Monthly budgets >$30, privacy concerns, rate limits

---

## Next Steps

1. ✅ Install dependencies (`pip install -r requirements-flux.txt`)
2. ✅ Download model (`python3 -c "from instagram.image_gen_local_flux import _get_flux_pipeline; _get_flux_pipeline()"`)
3. ✅ Test dry run (`python3 post_daily.py --dry-run --use-local-flux`)
4. ✅ Post to social (`python3 post_daily.py --use-local-flux`)

---

## Questions?

If generation fails or is unusually slow:

1. Check `nvidia-smi` output (is GPU at 100% utilization?)
2. Review logs: `cat post.log` (if using `--log-file`)
3. Test model directly: `python3 instagram/image_gen_local_flux.py`

---

**Happy generating!** 🎨
