from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from gesture_io import iter_dataset, save_labels
from gesture_pytorch_model import GestureConvNet, GesturePreprocessConfig, preprocess_series


@dataclass(frozen=True)
class TrainConfig:
    model_type: str
    resample_len: int
    mean: tuple[float, float, float]
    std: tuple[float, float, float]


def _set_seed(seed: int) -> None:
    np.random.seed(seed)
    torch.manual_seed(seed)


def _compute_norm(x: np.ndarray) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    # x: [N,3,T]
    mean = x.mean(axis=(0, 2))
    std = x.std(axis=(0, 2))
    return tuple(float(v) for v in mean), tuple(float(v) for v in std)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Train a gesture recognition model (PyTorch) and export a checkpoint.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--data_dir", required=True, help="Dataset root directory (label subfolders).")
    p.add_argument("--output_dir", required=True, help="Where to write artifacts.")
    p.add_argument("--resample_len", type=int, default=128, help="Resample each series to this length.")
    p.add_argument("--epochs", type=int, default=20, help="Training epochs.")
    p.add_argument("--batch_size", type=int, default=64, help="Batch size.")
    p.add_argument("--lr", type=float, default=1e-3, help="Learning rate.")
    p.add_argument("--test_size", type=float, default=0.2, help="Held-out split fraction.")
    p.add_argument("--seed", type=int, default=0, help="Random seed.")
    p.add_argument("--device", default="cpu", help="Training device (cpu, cuda).")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    _set_seed(int(args.seed))

    samples = iter_dataset(args.data_dir)
    labels = sorted({s.label for s in samples})
    label_to_id = {l: i for i, l in enumerate(labels)}

    # First pass: resample only (no normalization) so we can compute dataset stats.
    resampled = np.stack(
        [preprocess_series(s.series, GesturePreprocessConfig(resample_len=int(args.resample_len))) for s in samples],
        axis=0,
    ).astype(np.float32, copy=False)  # [N,3,T]

    # Split
    n = resampled.shape[0]
    idx = np.arange(n)
    rng = np.random.default_rng(int(args.seed))
    rng.shuffle(idx)

    test_n = max(1, int(round(float(args.test_size) * n)))
    test_idx = idx[:test_n]
    train_idx = idx[test_n:]
    if train_idx.size == 0:
        train_idx = test_idx
        test_idx = idx[:0]

    x_train_raw = resampled[train_idx]
    mean, std = _compute_norm(x_train_raw)
    cfg = GesturePreprocessConfig(resample_len=int(args.resample_len), mean=mean, std=std)

    x = np.stack([preprocess_series(s.series, cfg) for s in samples], axis=0).astype(np.float32, copy=False)
    y = np.array([label_to_id[s.label] for s in samples], dtype=np.int64)

    x_train, y_train = x[train_idx], y[train_idx]
    x_test, y_test = x[test_idx], y[test_idx]

    device = torch.device(str(args.device))
    model: nn.Module = GestureConvNet(num_classes=len(labels)).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=float(args.lr))
    loss_fn = nn.CrossEntropyLoss()

    train_ds = TensorDataset(torch.from_numpy(x_train), torch.from_numpy(y_train))
    train_loader = DataLoader(train_ds, batch_size=int(args.batch_size), shuffle=True, drop_last=False)

    model.train()
    for epoch in range(int(args.epochs)):
        total_loss = 0.0
        correct = 0
        seen = 0
        for xb, yb in train_loader:
            xb = xb.to(device=device, dtype=torch.float32)
            yb = yb.to(device=device, dtype=torch.long)

            opt.zero_grad(set_to_none=True)
            logits = model(xb)
            loss = loss_fn(logits, yb)
            loss.backward()
            opt.step()

            total_loss += float(loss.detach().cpu().item()) * int(yb.shape[0])
            pred = torch.argmax(logits.detach(), dim=1)
            correct += int((pred == yb).sum().cpu().item())
            seen += int(yb.shape[0])

        avg_loss = total_loss / max(1, seen)
        acc = correct / max(1, seen)
        print(f"epoch={epoch+1:02d} loss={avg_loss:.4f} train_acc={acc:.3f}")

    if x_test.shape[0] > 0:
        model.eval()
        with torch.no_grad():
            xb = torch.from_numpy(x_test).to(device=device, dtype=torch.float32)
            logits = model(xb)
            pred = torch.argmax(logits, dim=1).cpu().numpy().astype(np.int64)
        test_acc = float((pred == y_test).mean())
        print(f"test_acc={test_acc:.3f} ({x_test.shape[0]} samples)")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ckpt = {
        "model_type": "GestureConvNet",
        "state_dict": model.cpu().state_dict(),
        "num_classes": int(len(labels)),
        "train_cfg": asdict(
            TrainConfig(
                model_type="GestureConvNet",
                resample_len=int(args.resample_len),
                mean=mean,
                std=std,
            )
        ),
    }

    pt_path = out_dir / "gesture_model.pt"
    torch.save(ckpt, pt_path)
    save_labels(labels, out_dir / "gesture_labels.json")
    (out_dir / "gesture_config.json").write_text(
        json.dumps(
            {
                "model_type": "GestureConvNet",
                "resample_len": int(args.resample_len),
                "mean": list(mean),
                "std": list(std),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Wrote: {pt_path}")
    print(f"Wrote: {out_dir / 'gesture_labels.json'}")
    print(f"Wrote: {out_dir / 'gesture_config.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

