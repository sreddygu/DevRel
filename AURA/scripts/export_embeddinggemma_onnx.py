"""Export EmbeddingGemma's text path with pooling and normalization included."""

from __future__ import annotations

import argparse
from pathlib import Path

import torch
import torch.nn.functional as F
import onnx
from transformers import AutoModel, AutoTokenizer


class TextEmbeddingWrapper(torch.nn.Module):
    """Expose the normalized sentence vector used by the host baseline."""

    def __init__(self, model: torch.nn.Module) -> None:
        super().__init__()
        self.model = model

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        outputs = self.model(
            input_ids=input_ids,
            attention_mask=None,
            return_dict=True,
        )
        token_embeddings = outputs.last_hidden_state
        mask = attention_mask.unsqueeze(-1).to(token_embeddings.dtype)
        pooled = (token_embeddings * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1.0)
        return F.normalize(pooled, p=2, dim=1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="google/embeddinggemma-2")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-length", type=int, default=512)
    return parser.parse_args()


def repair_duplicate_output_names(path: Path) -> None:
    """Rename an internal value that collides with the final graph output."""
    model = onnx.load(path)
    graph_outputs = {value.name for value in model.graph.output}
    for output_name in graph_outputs:
        positions = [
            (node_index, output_index)
            for node_index, node in enumerate(model.graph.node)
            for output_index, node_output in enumerate(node.output)
            if node_output == output_name
        ]
        for position_index, (node_index, output_index) in enumerate(positions[:-1]):
            replacement = f"{output_name}_internal_{node_index}_{output_index}"
            model.graph.node[node_index].output[output_index] = replacement
            next_node_index = positions[position_index + 1][0]
            for later_node in model.graph.node[node_index + 1 : next_node_index]:
                for input_index, input_name in enumerate(later_node.input):
                    if input_name == output_name:
                        later_node.input[input_index] = replacement
    onnx.save(model, path)


def main() -> None:
    args = parse_args()
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModel.from_pretrained(args.model, torch_dtype=torch.float32)
    model = model.float()
    model.eval()
    wrapper = TextEmbeddingWrapper(model).eval()
    encoded = tokenizer(
        ["export validation"],
        padding="max_length",
        truncation=True,
        max_length=args.max_length,
        return_tensors="pt",
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with torch.no_grad():
        wrapper(encoded["input_ids"], encoded["attention_mask"])
    torch.onnx.export(
        wrapper,
        (encoded["input_ids"], encoded["attention_mask"]),
        str(args.output),
        input_names=["input_ids", "attention_mask"],
        output_names=["embedding"],
        opset_version=18,
        do_constant_folding=True,
        external_data=True,
    )
    repair_duplicate_output_names(args.output)
    print(f"Exported normalized {args.max_length}-token text graph to {args.output}")


if __name__ == "__main__":
    main()
