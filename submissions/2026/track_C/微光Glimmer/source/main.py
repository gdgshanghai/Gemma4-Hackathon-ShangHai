import os

os.environ["CUDA_VISIBLE_DEVICES"] = "2,3"
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import click
import torch
from transformers import AutoProcessor, Gemma4ForConditionalGeneration


MODEL_DIR = "/home/huzi/Downloads/gemma-4-E4B-it"


@click.command()
@click.option(
    "--model-dir",
    default=MODEL_DIR,
    show_default=True,
    help="Local model directory.",
)
@click.option(
    "--prompt",
    default="Explain in one sentence what CUDA_VISIBLE_DEVICES does.",
    show_default=True,
    help="Prompt to send to the model.",
)
@click.option(
    "--max-new-tokens",
    default=128,
    show_default=True,
    type=click.IntRange(min=1),
)
@click.option(
    "--temperature",
    default=0.7,
    show_default=True,
    type=click.FloatRange(min=0),
)
@click.option(
    "--top-p",
    default=0.95,
    show_default=True,
    type=click.FloatRange(min=0, max=1),
)
def main(
    model_dir: str,
    prompt: str,
    max_new_tokens: int,
    temperature: float,
    top_p: float,
) -> None:
    """Run local Gemma 4 E4B IT inference on physical GPUs 2 and 3."""
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available. This script expects GPUs 2 and 3.")

    processor = AutoProcessor.from_pretrained(model_dir, local_files_only=True)
    model = Gemma4ForConditionalGeneration.from_pretrained(
        model_dir,
        dtype=torch.bfloat16,
        device_map="auto",
        max_memory={0: "22GiB", 1: "22GiB"},
        local_files_only=True,
    )
    model.eval()

    messages = [{"role": "user", "content": prompt}]
    prompt_text = processor.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    inputs = processor(text=[prompt_text], return_tensors="pt")

    first_device = next(model.parameters()).device
    inputs = {name: tensor.to(first_device) for name, tensor in inputs.items()}

    generation_kwargs = {
        "max_new_tokens": max_new_tokens,
        "do_sample": temperature > 0,
        "pad_token_id": processor.tokenizer.pad_token_id,
    }
    if temperature > 0:
        generation_kwargs.update(
            {
                "temperature": temperature,
                "top_p": top_p,
            }
        )

    with torch.inference_mode():
        output_ids = model.generate(**inputs, **generation_kwargs)

    prompt_len = inputs["input_ids"].shape[-1]
    generated_ids = output_ids[0, prompt_len:]
    answer = processor.tokenizer.decode(generated_ids, skip_special_tokens=True)
    click.echo(answer.strip())


if __name__ == "__main__":
    main()
