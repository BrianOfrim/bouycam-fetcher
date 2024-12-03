"""Test the Beaufort model"""

import os
from functools import partial
import logging
import datetime

from datasets import load_dataset
import evaluate
import torch
from transformers import AutoImageProcessor, DefaultDataCollator
from torch.utils.data import DataLoader
from tqdm import tqdm

from seesea.model.beaufort import preprocess_batch_beaufort

LOGGER = logging.getLogger(__name__)


def main(args):
    """Run tests on the Beaufort model"""

    # Load model and processor
    model = torch.load(os.path.join(args.model_dir, "model.pt"))
    image_processor = AutoImageProcessor.from_pretrained(os.path.join(args.model_dir))

    # Setup dataset
    map_fn = partial(preprocess_batch_beaufort, image_processor)
    dataset = load_dataset("webdataset", data_dir=args.dataset, split=args.split, streaming=True)
    dataset = dataset.map(map_fn, batched=True).select_columns(["labels", "pixel_values"])

    # Setup dataloader
    collator = DefaultDataCollator()
    loader = DataLoader(dataset, collate_fn=collator, batch_size=args.batch_size)

    # Set device
    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")

    model = model.to(device)

    # Run test
    test_start_time = datetime.datetime.now(tz=datetime.timezone.utc)

    accuracy = evaluate.load("accuracy")

    model.eval()
    for batch in tqdm(loader, desc="Testing", disable=LOGGER.level > logging.INFO):
        batch = {k: v.to(device) for k, v in batch.items()}
        with torch.no_grad():
            outputs = model(**batch)

        logits = outputs.logits
        predictions = torch.argmax(logits, dim=-1)
        accuracy.add_batch(predictions=predictions, references=batch["labels"])

    test_end_time = datetime.datetime.now(tz=datetime.timezone.utc)
    LOGGER.info("Test duration: %s", test_end_time - test_start_time)
    LOGGER.info("Accuracy: %s", accuracy.compute())


def get_args_parser():
    import argparse

    parser = argparse.ArgumentParser(description="Test the SeeSea multihead model")
    parser.add_argument("--model-dir", help="Directory containing the trained model", required=True)
    parser.add_argument("--dataset", help="Directory containing the test dataset", required=True)
    parser.add_argument("--output", help="Directory to save test results", required=True)
    parser.add_argument("--split", help="Dataset split to use", default="test")
    parser.add_argument("--batch-size", type=int, help="Batch size for testing", default=32)
    parser.add_argument("--log", type=str, help="Log level", default="INFO")
    return parser


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = get_args_parser()
    args = parser.parse_args()
    main(args)
