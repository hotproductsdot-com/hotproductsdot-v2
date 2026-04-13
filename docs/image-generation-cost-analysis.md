# Image Generation Cost Analysis

## Migration: fal.ai → ModelsLab (April 2026)

### Cost Comparison

| Provider | Per Image | Monthly (1K images) | Monthly (10K images) | Unlimited Plan |
|----------|-----------|---------------------|----------------------|----------------|
| **fal.ai** (previous) | $0.005 | $5 | $50 | N/A |
| **ModelsLab** (current) | $0.002 | $2 | $20 | $29/month |
| OpenAI DALL-E 3 | $0.040 | $40 | $400 | N/A |
| Stability AI | $0.006 | $6 | $60 | N/A |
| Replicate FLUX-dev | $0.025 | $25 | $250 | N/A |

### Annual Savings

- **fal.ai estimate:** $50-100/month × 12 = **$600-1,200/year**
- **ModelsLab estimate:** $29/month × 12 = **$348/year**
- **Annual savings:** $252-852/year (50-70% reduction)

### Why ModelsLab?

1. **Cost:** 20x cheaper than OpenAI, 10x cheaper than fal.ai
2. **Quality:** FLUX models are state-of-the-art for product photography
3. **Feature parity:** Supports both text-to-image and image-to-image (edit mode)
4. **No cold-start billing:** Unlike fal.ai/Replicate
5. **Unified API:** Single endpoint for all image generation modes

### Implementation

- Migrated: April 2026
- Files modified: `instagram/image_gen.py`
- API endpoint: `https://modelslab.com/api/v6/images/{text2img|img2img}`
- Model: `flux` (recommended for product photography)
- Default resolution: 1024×1024 (no upcharge for higher resolution)

### Testing

All image generation tests pass with ModelsLab integration:
- Text-to-image generation
- Image-to-image (edit mode) restyling
- Prompt optimization with Claude
- Local image caching
- Error handling (timeouts, API failures)

See `instagram/test_modelslab_image_gen.py` for test coverage.
