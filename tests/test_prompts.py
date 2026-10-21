import hashlib
from pathlib import Path

from src.bench import load_prompts

PROMPTS = Path(__file__).resolve().parent.parent / "prompts" / "gsm8k_10.jsonl"

# Hash dicatat di prompts/README.md; berubah = workload berubah = experiment ID baru.
EXPECTED_SHA256 = "d05b6593b2ce489ffa966ae901cc7032377b44ddb8ab0430a7ec70bd662f252d"


def test_canonical_prompts_load():
    prompts = load_prompts(PROMPTS)
    assert [p["id"] for p in prompts] == [f"gsm8k-{i:03d}" for i in range(1, 11)]
    assert all(p["prompt"].strip() for p in prompts)


def test_canonical_prompts_unchanged():
    assert hashlib.sha256(PROMPTS.read_bytes()).hexdigest() == EXPECTED_SHA256
