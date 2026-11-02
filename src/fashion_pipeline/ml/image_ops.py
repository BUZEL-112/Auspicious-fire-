import io
from typing import Tuple
import cv2
import numpy as np
from PIL import Image
import torch
import torchvision.transforms as T


# FashionCLIP standard normalization
FASHION_CLIP_TRANSFORM = T.Compose([
    T.Resize((224, 224), interpolation=T.InterpolationMode.BICUBIC),
    T.ToTensor(),
    T.Normalize(
        mean=[0.48145466, 0.4578275, 0.40821073],
        std=[0.26862954, 0.26130258, 0.27577711]
    ),
])


def decode_image_bytes(image_bytes: bytes) -> np.ndarray:
    """Decodes raw image bytes into a RGB NumPy array in RAM without local disk I/O."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not decode image bytes into valid image")
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def encode_image_png(image_rgb: np.ndarray) -> bytes:
    """Encodes a RGB NumPy array into PNG bytes."""
    bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
    success, buffer = cv2.imencode(".png", bgr)
    if not success:
        raise ValueError("Failed to encode image into PNG format")
    return buffer.tobytes()


def isolate_and_crop_mask(
    image_rgb: np.ndarray,
    binary_mask: np.ndarray,
) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
    """
    Given an RGB image and a binary 2D mask (uint8 0 or 255):
    - Finds the bounding box (x, y, w, h) of the mask.
    - Replaces all non-mask pixels inside the bounding box with solid white (255, 255, 255).
    - Returns the isolated garment crop (RGB) and the bbox coordinates (x_min, y_min, x_max, y_max).
    """
    coords = cv2.findNonZero(binary_mask)
    if coords is None:
        raise ValueError("Binary mask contains zero active pixels")

    x, y, w, h = cv2.boundingRect(coords)

    # Crop image and mask to bounding box
    crop_img = image_rgb[y : y + h, x : x + w].copy()
    crop_mask = binary_mask[y : y + h, x : x + w]

    # Replace all non-mask pixels with solid white (255, 255, 255)
    # so neighboring garments or background do not bleed into the crop
    background_condition = crop_mask == 0
    crop_img[background_condition] = [255, 255, 255]

    return crop_img, (x, y, x + w, y + h)


def prepare_stage1_tensor(image_rgb: np.ndarray) -> torch.Tensor:
    """Transforms a single RGB image into a normalized PyTorch tensor of shape (3, 224, 224)."""
    pil_img = Image.fromarray(image_rgb)
    return FASHION_CLIP_TRANSFORM(pil_img)
