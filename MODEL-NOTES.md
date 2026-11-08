# Model and runtime sources

## YOLOv4-tiny

- Model and configuration: https://github.com/AlexeyAB/darknet
- Weights: https://github.com/AlexeyAB/darknet/releases/download/yolov4/yolov4-tiny.weights
- Configuration: https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4-tiny.cfg
- Class names: https://raw.githubusercontent.com/pjreddie/darknet/master/data/coco.names
- Example image: https://raw.githubusercontent.com/pjreddie/darknet/master/data/dog.jpg
- The original license is preserved in models/DARKNET-LICENSE.txt.

The model is pretrained on 80 COCO object classes. No training is performed by this application. Inference runs through OpenCV DNN on the CPU with a 416x416 input, confidence threshold 0.35, and per-class NMS threshold 0.4. Confidence is not a calibrated probability of correctness.

models/manifest.json records SHA-256 checksums of the supplied weights, configuration and labels. The launcher verifies them before starting. These detect altered files relative to this package; they are not separate publisher signatures.

## Dependencies

Python 3.12 was used for local verification. The repository contains application source, sample data and model assets, not a Windows interpreter. Install dependencies from requirements.txt in the target environment. requirements-lock.txt records the exact package versions verified locally.
