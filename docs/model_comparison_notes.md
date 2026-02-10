# Model Comparison Notes

## Scope
- Comparison mode is single-image only.
- Batch comparison is intentionally disabled in v1.

## Workflow
- Switch mode to `Model comparison`.
- Pick `Model A` and optional `Model B`.
- Validate model compatibility for multispectral inputs before run.

## Reading Results
- Side-by-side: quick qualitative differences.
- Swipe: inspect edges and detail transitions.

## Output Behavior
- Comparison runs generate up to two outputs (Model A and Model B) for the selected input.
- If a model runtime is unavailable, the run falls back to built-in visual upscale logic and records warnings.
