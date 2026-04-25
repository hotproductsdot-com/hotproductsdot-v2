#!/usr/bin/env bash
# FLUX + CUDA PyTorch venv on the Linux filesystem (WSL).
# Avoids broken/incomplete installs when the venv lives on /mnt/c or /mnt/e (NTFS).

set -euo pipefail

VENV_DIR="${FLUX_VENV:-$HOME/venvs/hotproductsdot-flux}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== FLUX venv: $VENV_DIR ==="
mkdir -p "$(dirname "$VENV_DIR")"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "Creating venv..."
  python3 -m venv "$VENV_DIR"
fi

# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip

echo "Installing PyTorch (CUDA 11.8 wheels)..."
python -m pip install torch torchvision torchaudio \
  --index-url https://download.pytorch.org/whl/cu118

echo "Installing diffusers stack..."
python -m pip install \
  diffusers transformers accelerate safetensors bitsandbytes huggingface-hub \
  Pillow requests python-dotenv anthropic

echo "Verifying..."
python -c "import torch; assert torch.cuda.is_available(), 'CUDA not visible to PyTorch'; print('torch', torch.__version__); print('cuda', torch.cuda.get_device_name(0))"
PYTHONPATH="$REPO_ROOT" python -c "import instagram.image_gen_local_flux; print('flux module ok')"

echo ""
echo "Done. From WSL, run:"
echo "  source $VENV_DIR/bin/activate"
echo "  cd $REPO_ROOT"
echo "  python3 post_daily.py --dry-run --use-local-flux"
