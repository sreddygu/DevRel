from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn
from transformers import AutoModel, AutoProcessor


class TextEmbeddingWrapper(nn.Module):
    def __init__(self, model: nn.Module) -> None:
        super().__init__()
        self.model = model

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)
        token_embeddings = outputs.last_hidden_state
        mask = attention_mask.unsqueeze(-1).to(token_embeddings.dtype)
        pooled = (token_embeddings * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1.0)
        return torch.nn.functional.normalize(pooled, p=2, dim=-1).float()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-id', default='google/embeddinggemma-2')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sequence-length', type=int, default=64)
    parser.add_argument('--text', default='A laptop is on the desk.')
    parser.add_argument('--offline', action='store_true')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    local_files_only = args.offline

    import truststore
    truststore.inject_into_ssl()

    processor = AutoProcessor.from_pretrained(args.model_id, local_files_only=local_files_only)
    model = AutoModel.from_pretrained(args.model_id, local_files_only=local_files_only)
    model.eval()
    wrapper = TextEmbeddingWrapper(model).eval()

    encoded = processor(
        text=[args.text],
        return_tensors='pt',
        padding='max_length',
        truncation=True,
        max_length=args.sequence_length,
    )
    input_ids = encoded['input_ids'].to(dtype=torch.int64)
    attention_mask = encoded['attention_mask'].to(dtype=torch.int64)

    with torch.no_grad():
        reference = wrapper(input_ids, attention_mask).cpu().numpy()

    torch.onnx.export(
        wrapper,
        (input_ids, attention_mask),
        str(args.output),
        input_names=['input_ids', 'attention_mask'],
        output_names=['embedding'],
        opset_version=18,
        do_constant_folding=True,
        dynamo=False,
    )

    manifest = {
        'model_id': args.model_id,
        'sequence_length': args.sequence_length,
        'input_names': ['input_ids', 'attention_mask'],
        'input_dtype': 'int64',
        'output_name': 'embedding',
        'output_dtype': 'float32',
        'embedding_dimension': int(reference.shape[-1]),
        'normalized': True,
        'reference_embedding': reference[0].tolist(),
    }
    manifest_path = args.output.with_suffix('.manifest.json')
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({'onnx': str(args.output), 'manifest': str(manifest_path), 'shape': list(reference.shape), 'norm': float(np.linalg.norm(reference[0]))}, indent=2))


if __name__ == '__main__':
    main()


