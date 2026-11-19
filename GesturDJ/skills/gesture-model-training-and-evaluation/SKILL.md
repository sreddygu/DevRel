# Gesture Model Training and Evaluation

Back to the [GesturDJ README](../../README.md).

## Steps

1. **Pick the approach.** Two trainers share the dataset layout:
   - [`train_gesture.py`](../../gesture_scripts/train_gesture.py) (scikit-learn SVM): quick baseline, prints a per-class
     report. **Cannot** be exported to ONNX.
   - [`train_gesture_pytorch.py`](../../gesture_scripts/train_gesture_pytorch.py) (1D conv net): the path to the board (ONNX).
     Use this whenever the model will run on a Ventuno Q.
2. **Train** with the dataset folder and an output folder (absolute paths).
   Keep the seed (default 0); the validation skill reproduces the same split from it.
3. **Read the result carefully.** Report held-out accuracy **and** the number of
   held-out samples. With 30 samples one sample is 3.3 points. The PyTorch split
   is shuffled but not stratified, so check every label is in the held-out set
   when the dataset is small.
4. **Decide:** `deploy` (go to model-export-and-deployment), `collect more data`
   (say which gestures are weak), or `change approach`.

## Record with the model

Training date, seed, held-out fraction, package versions (the requirements files
are unpinned, so versions drift), and the dataset report. Without them the
validation step cannot be reproduced.

## Measured (synthetic data, PC)

sklearn baseline 0.70; PyTorch 1.00 on 30 held-out samples. Synthetic data is
easy, so this shows the code path works, not that real gestures are recognized.

Complete when the model files exist, held-out accuracy and count are reported, and
a decision is written. This skill does not export or deploy.
