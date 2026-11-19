from __future__ import annotations

import argparse
import csv
import shutil
import zipfile
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


URL_CANDIDATES = [
    # UCR / Eamonn Keogh mirror (commonly used for time-series datasets)
    "https://www.cs.ucr.edu/~eamonn/time_series_data_2018/UWaveGestureLibraryAll.zip",
    # Alternate mirrors that sometimes host UCR downloads
    "http://www.timeseriesclassification.com/Downloads/UWaveGestureLibraryAll.zip",
    "https://www.timeseriesclassification.com/Downloads/UWaveGestureLibraryAll.zip",
]


def _is_zip(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            sig = f.read(4)
        return sig == b"PK\x03\x04"
    except OSError:
        return False


def _download(url: str, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=60) as r, dst.open("wb") as f:
        shutil.copyfileobj(r, f)


def _download_any(urls: list[str], dst: Path) -> str:
    last_err: Exception | None = None
    for url in urls:
        try:
            if dst.exists():
                dst.unlink()
            print(f"Downloading {url} -> {dst}")
            _download(url, dst)
            if _is_zip(dst):
                return url
            # Not a zip; show a hint for debugging
            text = dst.read_bytes()[:200]
            try:
                hint = text.decode("utf-8", errors="replace").strip()
            except Exception:
                hint = repr(text)
            print(f"Not a zip file. First bytes: {hint}")
        except (URLError, OSError) as e:
            last_err = e
            print(f"Download failed: {e}")

    raise RuntimeError(f"All download URLs failed. Last error: {last_err}")


def _extract(zip_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(out_dir)


def _find_train_test_files(extracted_root: Path) -> tuple[Path, Path]:
    train = sorted(extracted_root.rglob("*_TRAIN.tsv"))
    test = sorted(extracted_root.rglob("*_TEST.tsv"))
    if not train or not test:
        raise FileNotFoundError("Could not find *_TRAIN.tsv and *_TEST.tsv under extracted zip")
    return train[0], test[0]


def _write_sample_csv(path: Path, series: list[tuple[float, float, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ax", "ay", "az"])
        w.writerows(series)


def _convert_tsv(tsv_path: Path, out_dir: Path, *, split_name: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with tsv_path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            label = str(int(float(parts[0])))
            values = [float(x) for x in parts[1:] if x != ""]
            if len(values) % 3 != 0:
                raise ValueError(
                    "Expected 3-axis concatenated series (len divisible by 3). "
                    f"Got {len(values)} values in {tsv_path}."
                )
            t = len(values) // 3
            xs = values[:t]
            ys = values[t : 2 * t]
            zs = values[2 * t :]
            series = list(zip(xs, ys, zs))
            sample_path = out_dir / f"gesture_{label}" / f"{split_name}_{idx:05d}.csv"
            _write_sample_csv(sample_path, series)


def main() -> int:
    p = argparse.ArgumentParser(description="Download and prepare a small gesture dataset (uWave/UCR).")
    p.add_argument(
        "--url",
        action="append",
        default=None,
        help="Zip URL to download (can be passed multiple times).",
    )
    p.add_argument(
        "--zip_path",
        default=None,
        help="Use an existing local zip instead of downloading.",
    )
    p.add_argument(
        "--data_dir",
        default="gesture_data/uwave",
        help="Output dataset directory (label subfolders).",
    )
    p.add_argument(
        "--cache_dir",
        default="gesture_data/_cache",
        help="Where to store the downloaded zip + extracted files.",
    )
    args = p.parse_args()

    project_root = Path(__file__).resolve().parent
    data_dir = (project_root / args.data_dir).resolve()
    cache_dir = (project_root / args.cache_dir).resolve()

    zip_path = cache_dir / "UWaveGestureLibraryAll.zip"
    extract_dir = cache_dir / "UWaveGestureLibraryAll_extracted"

    if data_dir.exists() and any(data_dir.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty data_dir: {data_dir}")

    if args.zip_path:
        zip_path = Path(args.zip_path).resolve()
        if not zip_path.exists():
            raise FileNotFoundError(zip_path)
        if not _is_zip(zip_path):
            raise ValueError(f"Not a zip file: {zip_path}")
        print(f"Using local zip: {zip_path}")
    else:
        urls = args.url if args.url else URL_CANDIDATES
        used = _download_any(urls, zip_path)
        print(f"Downloaded from: {used}")

    # (re)extract
    if extract_dir.exists():
        shutil.rmtree(extract_dir, ignore_errors=True)
    print(f"Extracting {zip_path} -> {extract_dir}")
    _extract(zip_path, extract_dir)

    train_tsv, test_tsv = _find_train_test_files(extract_dir)
    print(f"Found train: {train_tsv}")
    print(f"Found test : {test_tsv}")

    print(f"Writing dataset to: {data_dir}")
    _convert_tsv(train_tsv, data_dir, split_name="train")
    _convert_tsv(test_tsv, data_dir, split_name="test")

    print("\nNext:")
    print(f"  python train_gesture.py --data_dir {data_dir} --output_dir outputs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
