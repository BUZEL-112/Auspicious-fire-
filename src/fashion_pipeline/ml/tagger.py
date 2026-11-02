from typing import Dict, List, Optional
import torch
from fashion_pipeline.schemas.job import FacetedTag


# Garment categories where neckline and sleeve_length are irrelevant and must be suppressed
LOWER_BODY_AND_ACCESSORIES = {
    "pants",
    "jeans",
    "shorts",
    "skirt",
    "shoes",
    "sneakers",
    "boots",
    "sandals",
    "bag",
    "hat",
    "scarf",
}


def grouped_softmax_tagging(
    image_embeddings: torch.Tensor,
    cached_text_embeddings: Dict[str, torch.Tensor],
    vocabulary: Dict[str, List[str]],
    temperature: float = 100.0,
) -> List[Dict[str, FacetedTag]]:
    """
    Performs batched Stage 1 Tagging using Grouped Softmax.

    - image_embeddings: Tensor of shape (N, D), already L2-normalized.
    - cached_text_embeddings: Dict mapping facet name -> Tensor of shape (C_facet, D), L2-normalized.
    - vocabulary: Dict mapping facet name -> List of class names of length C_facet.
    - temperature: Scaling temperature (e.g. 100.0 from FashionCLIP logit_scale).

    Returns:
        List of dicts (length N), where each dict maps facet -> FacetedTag(label, confidence).
    """
    N = image_embeddings.shape[0]
    batch_results: List[Dict[str, FacetedTag]] = [{} for _ in range(N)]

    for facet, text_weights in cached_text_embeddings.items():
        # text_weights: (C, D)
        # logits: (N, C) = (N, D) @ (D, C) * temperature
        logits = torch.matmul(image_embeddings, text_weights.t()) * (temperature / 100.0)
        probs = torch.softmax(logits, dim=-1)  # (N, C)

        best_probs, best_indices = torch.max(probs, dim=-1)  # (N,), (N,)

        for i in range(N):
            idx = int(best_indices[i].item())
            confidence = float(best_probs[i].item())
            label = vocabulary[facet][idx]
            batch_results[i][facet] = FacetedTag(label=label, confidence=confidence)

    # Conditional Suppression Rules
    for i in range(N):
        apply_conditional_rules(batch_results[i])

    return batch_results


def apply_conditional_rules(tags: Dict[str, FacetedTag], segformer_class_name: Optional[str] = None) -> None:
    """
    Applies domain rules:
    - Suppressing 'sleeve' and 'neckline' tags if SegFormer or category facet identifies
      the piece as pants, shoes, bag, skirt, etc.
    """
    category = tags.get("category")
    cat_label = category.label.lower() if category else ""
    seg_label = segformer_class_name.lower() if segformer_class_name else ""

    is_suppressed = False
    for lower_type in LOWER_BODY_AND_ACCESSORIES:
        if lower_type in cat_label or lower_type in seg_label:
            is_suppressed = True
            break

    if is_suppressed:
        tags.pop("sleeve", None)
        tags.pop("neckline", None)
