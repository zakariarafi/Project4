# Prompt Workload

`gsm8k_10.jsonl` berisi sepuluh prompt canonical untuk seluruh benchmark.
Isinya tidak boleh diubah setelah eksperimen dimulai; buat file/experiment ID
baru bila perlu.

## Format

Satu baris JSON per prompt:

| Field | Keterangan |
| --- | --- |
| `id` | ID stabil `gsm8k-001` … `gsm8k-010`; dipakai di setiap record hasil. |
| `source_index` | Indeks baris (mulai 0) pada `test.jsonl` sumber. |
| `prompt` | Teks `question` GSM8K, **verbatim** tanpa adaptasi. |
| `answer` | Jawaban numerik akhir (bagian setelah `####`). Tidak dipakai benchmark; disimpan untuk evaluasi kualitas P2. |

Runner hanya membaca `id` dan `prompt`. Chat template Qwen3 diterapkan oleh
`src/bench.py` (`enable_thinking=False`), bukan ditulis di file ini.

## Provenance

- Sumber: [openai/grade-school-math](https://github.com/openai/grade-school-math),
  `grade_school_math/data/test.jsonl` (split test, 1319 soal).
- Commit sumber: `3101c7d5072418e28b9008a6636bde82a006892c` (branch `master`,
  diambil 2026-10-21).
- SHA-256 `test.jsonl` sumber:
  `3730d312f6e3440559ace48831e51066acaca737f6eabec99bccb9e4b3c39d14`.
- Metode pemilihan: **10 baris pertama** split test (indeks 0–9). Dipilih
  karena deterministik dan mudah diaudit, bukan karena isi soalnya; tidak ada
  penyaringan berdasarkan panjang atau tingkat kesulitan.
- Lisensi: MIT, Copyright (c) 2021 OpenAI.
- Sitasi: Cobbe et al., 2021, *Training Verifiers to Solve Math Word
  Problems*, arXiv:2110.14168.

Prompt GSM8K dipakai sebagai workload yang konsisten, bukan untuk mengklaim
kemampuan matematis model (lihat docs/PRD.md §4).

## Reproduksi

```bash
curl -sSfLO https://raw.githubusercontent.com/openai/grade-school-math/3101c7d5072418e28b9008a6636bde82a006892c/grade_school_math/data/test.jsonl
python - <<'PY'
import json
rows = [json.loads(l) for l in open("test.jsonl", encoding="utf-8")]
with open("prompts/gsm8k_10.jsonl", "w", encoding="utf-8") as out:
    for i, r in enumerate(rows[:10]):
        out.write(json.dumps({
            "id": f"gsm8k-{i + 1:03d}",
            "source_index": i,
            "prompt": r["question"],
            "answer": r["answer"].split("####")[-1].strip(),
        }, ensure_ascii=False) + "\n")
PY
```

SHA-256 `gsm8k_10.jsonl` yang dihasilkan:
`d05b6593b2ce489ffa966ae901cc7032377b44ddb8ab0430a7ec70bd662f252d`.
