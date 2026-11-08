import io
import threading
import warnings
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError


MODEL_FOLDER = Path(__file__).resolve().parent / "models"
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 16_000_000
CONFIDENCE_THRESHOLD = 0.35
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
cv2.setNumThreads(2)


def read_image(data):
    if not data or len(data) > MAX_FILE_BYTES:
        raise ValueError("Choose an image smaller than 8 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError("Use a JPG, PNG or WebP image.")
                if image.width * image.height > MAX_PIXELS:
                    raise ValueError("Choose an image with no more than 16 million pixels.")
                if getattr(image, "n_frames", 1) > 1:
                    raise ValueError("Choose a still image instead of an animation.")
                image.load()
                result = ImageOps.exif_transpose(image).convert("RGB")
                result.thumbnail((1600, 1600))
                return result
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as error:
        raise ValueError("This file could not be read as a safe image. Try another image.") from error


class ObjectDetector:
    def __init__(self, model_folder=MODEL_FOLDER):
        self.model_folder = Path(model_folder)
        self.model = None
        self.labels = []
        self.lock = threading.Lock()

    def _load(self):
        weights = self.model_folder / "yolov4-tiny.weights"
        config = self.model_folder / "yolov4-tiny.cfg"
        names = self.model_folder / "coco.names"
        if not all(path.is_file() for path in (weights, config, names)):
            raise RuntimeError("The local model files are missing. Restore the models folder.")
        self.labels = names.read_text(encoding="utf-8").splitlines()
        self.model = cv2.dnn.DetectionModel(str(weights), str(config))
        self.model.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.model.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        self.model.setInputParams(scale=1 / 255.0, size=(416, 416), swapRB=True, crop=False)

    def detect(self, image):
        frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        # The network keeps working buffers, so concurrent requests share one lock.
        with self.lock:
            if self.model is None:
                self._load()
            class_ids, confidences, boxes = self.model.detect(
                frame, confThreshold=CONFIDENCE_THRESHOLD, nmsThreshold=0.4
            )
        detections = []
        height, width = frame.shape[:2]
        for class_id, confidence, box in zip(class_ids, confidences, boxes):
            x, y, box_width, box_height = (int(value) for value in box)
            left, top = max(0, x), max(0, y)
            right, bottom = min(width - 1, x + box_width), min(height - 1, y + box_height)
            if right <= left or bottom <= top:
                continue
            detections.append({
                "label": self.labels[int(class_id)],
                "confidence": round(float(confidence), 6),
                "box": [left, top, right - left, bottom - top],
            })
        detections.sort(key=lambda item: item["confidence"], reverse=True)
        for item in detections:
            x, y, box_width, box_height = item["box"]
            label = f"{item['label']} {item['confidence']:.0%}"
            cv2.rectangle(frame, (x, y), (x + box_width, y + box_height), (65, 132, 57), 2)
            text_y = max(22, y - 8)
            cv2.putText(frame, label, (x, text_y), cv2.FONT_HERSHEY_SIMPLEX, .65,
                        (255, 255, 255), 4, cv2.LINE_AA)
            cv2.putText(frame, label, (x, text_y), cv2.FONT_HERSHEY_SIMPLEX, .65,
                        (34, 72, 29), 1, cv2.LINE_AA)
        annotated = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        return detections, annotated
