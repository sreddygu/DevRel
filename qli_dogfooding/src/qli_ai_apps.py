"""Run generic QLI model, inference, scoring, and AI-agent workflows.

The module delegates hardware-specific inference to commands supplied after
``--command`` and provides portable post-processing for JSON or text scores.
Chat workflows use a configurable OpenAI-compatible completions endpoint.

Place ``--command`` last because all following arguments belong to the external
runner. Model URLs, access tokens, and other credentials must not be stored in
this source file. Use approved tooling or environment-based authentication.

Examples::

    python3 qli_ai_apps.py top5 --scores scores.json --labels labels.txt
    python3 qli_ai_apps.py classify --image image.jpg --command runner {input}
"""

import argparse
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path
from urllib.request import Request, urlopen


WORKFLOWS = (
    "Download Model from AI Hub",
    "Run Image Classification",
    "Top 5 Predictions Viewer",
    "Dog vs Non Dog Detector",
    "Object Detection on Camera Image",
    "Compare Two AI Models",
    "Inference Timing Benchmark",
    "Confidence Score Analyzer",
    "AI Powered Device Q&A",
    "Camera Observation Agent",
)


def emit(workflow: str, result) -> None:
    """Print a workflow result as formatted JSON."""
    print(json.dumps({"workflow": workflow, "result": result}, indent=2))


def run_command(command: list[str], timeout: int = 300) -> dict:
    """Run an external model command with timeout and structured error handling."""
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return {
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
    except FileNotFoundError:
        return {"command": command, "returncode": 127, "stdout": "", "stderr": "command not found"}
    except subprocess.TimeoutExpired:
        return {"command": command, "returncode": 124, "stdout": "", "stderr": "command timed out"}


def read_labels(path: Path | None) -> list[str]:
    """Read optional newline-separated class labels from a UTF-8 text file."""
    if not path:
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_scores(path: Path, labels_path: Path | None = None) -> list[dict]:
    """Parse and rank scores from supported JSON or whitespace-delimited formats."""
    text = path.read_text(encoding="utf-8").strip()
    labels = read_labels(labels_path)
    entries = []
    if path.suffix.lower() == ".json":
        data = json.loads(text)
        if isinstance(data, dict):
            data = data.get("scores", data.get("predictions", data))
        if isinstance(data, dict):
            entries = [
                {"index": index, "label": str(label), "score": float(score)}
                for index, (label, score) in enumerate(data.items())
            ]
        elif isinstance(data, list):
            for index, item in enumerate(data):
                if isinstance(item, dict):
                    entries.append(
                        {
                            "index": index,
                            "label": str(item.get("label", labels[index] if index < len(labels) else index)),
                            "score": float(item.get("score", item.get("confidence", 0.0))),
                        }
                    )
                else:
                    entries.append(
                        {
                            "index": index,
                            "label": labels[index] if index < len(labels) else str(index),
                            "score": float(item),
                        }
                    )
    else:
        for index, line in enumerate(text.splitlines()):
            parts = line.replace(",", " ").split()
            if not parts:
                continue
            try:
                score = float(parts[-1])
            except ValueError:
                continue
            label = " ".join(parts[:-1]) or (labels[index] if index < len(labels) else str(index))
            entries.append({"index": index, "label": label, "score": score})
    return sorted(entries, key=lambda item: item["score"], reverse=True)


def append_input(command: list[str], input_path: Path | None) -> list[str]:
    """Replace ``{input}`` placeholders or append the input path to a command."""
    expanded = []
    replaced = False
    for value in command:
        if input_path and "{input}" in value:
            expanded.append(value.replace("{input}", str(input_path)))
            replaced = True
        else:
            expanded.append(value)
    if input_path and not replaced:
        expanded.append(str(input_path))
    return expanded


def handle_download(args: argparse.Namespace) -> None:
    """Download a model artifact and optionally verify its SHA-256 digest."""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    request = Request(args.url, headers={"User-Agent": "qli-device-apps/1.0"})
    digest = hashlib.sha256()
    with urlopen(request, timeout=args.timeout) as response, args.output.open("wb") as stream:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            stream.write(chunk)
    actual_hash = digest.hexdigest()
    if args.sha256 and actual_hash.lower() != args.sha256.lower():
        args.output.unlink(missing_ok=True)
        raise SystemExit(f"SHA-256 mismatch: expected {args.sha256}, got {actual_hash}")
    emit("Download Model from AI Hub", {"output": str(args.output), "sha256": actual_hash})


def handle_classification(args: argparse.Namespace) -> None:
    """Run a user-supplied image-classification command."""
    command = append_input(args.command, args.image)
    emit("Run Image Classification", run_command(command, args.timeout))


def handle_top5(args: argparse.Namespace) -> None:
    """Display the five highest-scoring labels from an inference result."""
    emit("Top 5 Predictions Viewer", read_scores(args.scores, args.labels)[:5])


def handle_dog(args: argparse.Namespace) -> None:
    """Compare dog-related labels or ImageNet dog indices against non-dog scores."""
    scores = read_scores(args.scores, args.labels)
    dog_terms = [term.lower() for term in args.dog_terms]
    dog_entries = [
        item
        for item in scores
        if any(term in item["label"].lower() for term in dog_terms)
        or args.dog_index_start <= item["index"] <= args.dog_index_end
    ]
    dog_score = max((item["score"] for item in dog_entries), default=float("-inf"))
    non_dog_score = max(
        (item["score"] for item in scores if item not in dog_entries),
        default=float("-inf"),
    )
    emit(
        "Dog vs Non Dog Detector",
        {
            "decision": "DOG" if dog_score >= non_dog_score else "NON_DOG",
            "dog_score": dog_score,
            "non_dog_score": non_dog_score,
            "top_dog_matches": dog_entries[:5],
        },
    )


def handle_object_detection(args: argparse.Namespace) -> None:
    """Run a user-supplied object-detection command for an image."""
    command = append_input(args.command, args.image)
    emit("Object Detection on Camera Image", run_command(command, args.timeout))


def score_map(path: Path, labels: Path | None) -> dict[str, float]:
    """Convert parsed score entries into a label-to-score mapping."""
    return {item["label"]: item["score"] for item in read_scores(path, labels)}


def handle_compare(args: argparse.Namespace) -> None:
    """Compare two model score sets and report their largest differences."""
    first = score_map(args.first, args.labels)
    second = score_map(args.second, args.labels)
    common = sorted(set(first) & set(second))
    differences = sorted(
        (
            {
                "label": label,
                "first": first[label],
                "second": second[label],
                "absolute_difference": abs(first[label] - second[label]),
            }
            for label in common
        ),
        key=lambda item: item["absolute_difference"],
        reverse=True,
    )
    emit(
        "Compare Two AI Models",
        {
            "first_top": max(first, key=first.get) if first else None,
            "second_top": max(second, key=second.get) if second else None,
            "common_labels": len(common),
            "largest_differences": differences[: args.limit],
        },
    )


def handle_benchmark(args: argparse.Namespace) -> None:
    """Benchmark repeated execution of an external inference command."""
    timings = []
    runs = []
    for _ in range(args.warmup):
        run_command(args.command, args.timeout)
    for _ in range(args.iterations):
        started = time.perf_counter()
        result = run_command(args.command, args.timeout)
        elapsed_ms = (time.perf_counter() - started) * 1000
        timings.append(elapsed_ms)
        runs.append(result)
        if result["returncode"] != 0:
            break
    emit(
        "Inference Timing Benchmark",
        {
            "iterations_completed": len(timings),
            "mean_ms": sum(timings) / len(timings) if timings else None,
            "median_ms": median(timings),
            "min_ms": min(timings) if timings else None,
            "max_ms": max(timings) if timings else None,
            "last_run": runs[-1] if runs else None,
        },
    )


def softmax(values: list[float]) -> list[float]:
    """Convert arbitrary logits into numerically stable probabilities."""
    if not values:
        return []
    maximum = max(values)
    exponents = [math.exp(value - maximum) for value in values]
    total = sum(exponents)
    return [value / total for value in exponents]


def median(values: list[float]) -> float | None:
    """Return the median without depending on the optional statistics module."""
    if not values:
        return None
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2


def handle_confidence(args: argparse.Namespace) -> None:
    """Report ranked probabilities, top-two margin, and prediction entropy."""
    entries = read_scores(args.scores, args.labels)
    values = [item["score"] for item in entries]
    probabilities = values if args.normalized else softmax(values)
    ranked = sorted(
        (
            {"label": item["label"], "score": item["score"], "probability": probability}
            for item, probability in zip(entries, probabilities)
        ),
        key=lambda item: item["probability"],
        reverse=True,
    )
    margin = ranked[0]["probability"] - ranked[1]["probability"] if len(ranked) > 1 else None
    entropy = -sum(value * math.log(value) for value in probabilities if value > 0)
    emit(
        "Confidence Score Analyzer",
        {"top": ranked[: args.limit], "top_two_margin": margin, "entropy": entropy},
    )


def post_chat(endpoint: str, model: str, prompt: str, timeout: int) -> str:
    """Submit a prompt to an OpenAI-compatible chat-completions endpoint."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 512,
    }
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"].strip()


def handle_qna(args: argparse.Namespace) -> None:
    """Answer a device question using only the optional supplied context file."""
    context = args.context.read_text(encoding="utf-8", errors="replace") if args.context else ""
    prompt = (
        "Answer the device question using only the supplied context. State when evidence is missing.\n\n"
        f"Context:\n{context}\n\nQuestion: {args.question}"
    )
    emit(
        "AI Powered Device Q&A",
        {"answer": post_chat(args.endpoint, args.model, prompt, args.timeout)},
    )


def handle_camera_agent(args: argparse.Namespace) -> None:
    """Run a camera-observation command and optionally summarize it with a model."""
    command = append_input(args.command, args.image)
    observation = run_command(command, args.timeout)
    standard_error = observation["stderr"] or "(none)"
    prompt = (
        "Summarize this camera observation output, distinguish observations from uncertainty, "
        "and suggest one safe next action. A successful detector may report that nothing is in "
        "view; do not describe that as a camera or software error.\n\n"
        f"Detector return code: {observation['returncode']}\n"
        f"Observation output:\n{observation['stdout']}\n"
        f"Standard error:\n{standard_error}"
    )
    answer = None
    if observation["returncode"] == 0 and args.endpoint:
        answer = post_chat(args.endpoint, args.model, prompt, args.timeout)
    emit("Camera Observation Agent", {"observation": observation, "analysis": answer})


def add_runner_arguments(parser: argparse.ArgumentParser, require_image: bool = True) -> None:
    """Add common external-runner, timeout, and optional image arguments."""
    if require_image:
        parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--command", nargs=argparse.REMAINDER, required=True)


def add_score_arguments(parser: argparse.ArgumentParser) -> None:
    """Add common score-file and optional label-file arguments."""
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--labels", type=Path)


def build_parser() -> argparse.ArgumentParser:
    """Construct the AI and model workflow command-line parser."""
    parser = argparse.ArgumentParser(description="Generic QLI AI and model application workflows.")
    parser.add_argument("--list-workflows", action="store_true")
    subparsers = parser.add_subparsers(dest="app")

    download = subparsers.add_parser("download-model", help=WORKFLOWS[0])
    download.add_argument("--url", required=True)
    download.add_argument("--output", type=Path, required=True)
    download.add_argument("--sha256")
    download.add_argument("--timeout", type=int, default=300)
    download.set_defaults(handler=handle_download)

    classify = subparsers.add_parser("classify", help=WORKFLOWS[1])
    add_runner_arguments(classify)
    classify.set_defaults(handler=handle_classification)

    top5 = subparsers.add_parser("top5", help=WORKFLOWS[2])
    add_score_arguments(top5)
    top5.set_defaults(handler=handle_top5)

    dog = subparsers.add_parser("dog-detector", help=WORKFLOWS[3])
    add_score_arguments(dog)
    dog.add_argument("--dog-terms", nargs="+", default=["dog", "terrier", "retriever", "hound", "poodle"])
    dog.add_argument("--dog-index-start", type=int, default=151)
    dog.add_argument("--dog-index-end", type=int, default=268)
    dog.set_defaults(handler=handle_dog)

    objects = subparsers.add_parser("object-detect", help=WORKFLOWS[4])
    add_runner_arguments(objects)
    objects.set_defaults(handler=handle_object_detection)

    compare = subparsers.add_parser("compare-models", help=WORKFLOWS[5])
    compare.add_argument("--first", type=Path, required=True)
    compare.add_argument("--second", type=Path, required=True)
    compare.add_argument("--labels", type=Path)
    compare.add_argument("--limit", type=int, default=10)
    compare.set_defaults(handler=handle_compare)

    benchmark = subparsers.add_parser("benchmark", help=WORKFLOWS[6])
    benchmark.add_argument("--iterations", type=int, default=10)
    benchmark.add_argument("--warmup", type=int, default=1)
    benchmark.add_argument("--timeout", type=int, default=300)
    benchmark.add_argument("--command", nargs=argparse.REMAINDER, required=True)
    benchmark.set_defaults(handler=handle_benchmark)

    confidence = subparsers.add_parser("confidence", help=WORKFLOWS[7])
    add_score_arguments(confidence)
    confidence.add_argument("--normalized", action="store_true")
    confidence.add_argument("--limit", type=int, default=5)
    confidence.set_defaults(handler=handle_confidence)

    qna = subparsers.add_parser("device-qna", help=WORKFLOWS[8])
    qna.add_argument("--endpoint", default="http://127.0.0.1:8080/v1/chat/completions")
    qna.add_argument("--model", default="local-model")
    qna.add_argument("--context", type=Path)
    qna.add_argument("--question", required=True)
    qna.add_argument("--timeout", type=int, default=300)
    qna.set_defaults(handler=handle_qna)

    camera = subparsers.add_parser("camera-agent", help=WORKFLOWS[9])
    add_runner_arguments(camera)
    camera.add_argument("--endpoint")
    camera.add_argument("--model", default="local-model")
    camera.set_defaults(handler=handle_camera_agent)

    return parser


def main() -> None:
    """Dispatch the selected AI workflow or print workflow discovery output."""
    parser = build_parser()
    args = parser.parse_args()
    if args.list_workflows:
        print("\n".join(WORKFLOWS))
        return
    if not hasattr(args, "handler"):
        parser.print_help()
        raise SystemExit(2)
    args.handler(args)


if __name__ == "__main__":
    main()
