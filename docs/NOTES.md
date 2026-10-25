# Catatan Reverse Engineering MLX

Catatan ini menjawab empat pertanyaan T03 tentang `mlx_lm/generate.py` dan
dampaknya pada `src/bench.py`. Nomor baris merujuk ke source yang disebut di
bawah; penjelasan ditulis ulang, bukan salinan kode.

## Metadata source

- Path source: `mlx_lm/generate.py` dari paket PyPI `mlx-lm==0.32.1`
  (2177 baris), dipasang bersama `mlx[cpu]==0.32.3` pada Python 3.12.
- Git commit/tag atau versi `mlx-lm`: rilis PyPI `0.32.1`.
- Tanggal pemeriksaan: 2026-10-24.
- Pemeriksa: anggota A (mengerjakan peran B juga, D-007).

Benchmark memakai versi yang sama persis: `requirements.txt` mem-pin
`mlx==0.32.3` dan `mlx-lm==0.32.1` (D-008), menggantikan build dev
`0.32.1.dev6` yang tidak bisa dipasang ulang dari PyPI. Pastikan dengan
`pip show mlx-lm` di Mac sebelum mengumpulkan data; manifest setiap run juga
mencatat versi paket.

## 1. `GenerationResponse`

Dataclass di baris 275–302. Field yang dipakai benchmark:

| Field | Arti | Catatan untuk benchmark |
| --- | --- | --- |
| `text` | potongan teks baru hasil detokenizer (bisa string kosong) | digabung untuk `output_sha256` |
| `token` | id token terakhir | — |
| `from_draft` | `True` jika token diusulkan draft model **dan** lolos verifikasi target | dasar `draft_fraction` |
| `prompt_tokens` | panjang prompt dalam token | — |
| `prompt_tps` | `prompt_tokens / waktu sampai token pertama` | lihat catatan prefill di bawah |
| `generation_tokens` | jumlah token keluaran sejauh ini (`n + 1`) | **termasuk token EOS** bila generasi berhenti karena EOS |
| `generation_tps` | `generation_tokens / waktu sejak token pertama` | jam dimulai setelah token pertama |
| `peak_memory` | `mx.get_peak_memory() / 1e9`, dalam **GB** | puncak sejak reset terakhir; bench memanggil `mx.reset_peak_memory()` per run |
| `finish_reason` | `"stop"` (EOS), `"length"` (batas token), atau `None` di respons antara | hanya respons terakhir yang terisi |

Setiap token di-*yield* tepat satu kali (loop di baris 732–771). Pada token terakhir,
baik karena EOS maupun batas `max_tokens`, loop berhenti dulu lalu satu
respons akhir dikirim untuk token itu. Karena itu jumlah respons sama dengan
`generation_tokens`, dan menghitung `from_draft` pada semua respons (seperti
`src/bench.py`) memberi jumlah token draft yang benar.

## 2. Penerimaan/penolakan token draft

`speculative_generate_step` (baris 485–666) bekerja per siklus:

1. **Prefill dua model.** Prompt dimasukkan ke cache draft dan cache target
   (bertahap per `prefill_step_size`, default 512), menyisakan token terakhir
   sebagai input awal. Cache target wajib bisa dipotong (*trimmable*); bila
   tidak, fungsi menolak berjalan.
2. **Draft.** Draft model menghasilkan `num_draft = min(sisa token, k)` token
   satu per satu dengan sampler yang sama.
3. **Verifikasi.** Target menjalankan **satu forward pass** atas token input
   ditambah semua token draft, lalu memilih token di setiap `k + 1` posisi
   dengan sampler yang sama.
4. **Terima/tolak.** Token draft dibandingkan berurutan dengan pilihan target
   pada posisi yang sama. Token yang **sama persis** diterima
   (`from_draft=True`); perbandingan berhenti di ketidakcocokan pertama. Ini
   pencocokan token eksak, bukan *rejection sampling* probabilistik.
5. **Token bonus.** Setelah token draft yang diterima, pilihan target pada
   posisi berikutnya selalu dikeluarkan (`from_draft=False`): pengganti token
   draft yang ditolak, atau token tambahan jika semua draft diterima.
6. **Mundurkan cache.** Entri cache untuk token draft yang ditolak dipotong
   dari cache target dan draft. Jika semua draft diterima, token draft
   terakhir disertakan pada siklus berikutnya karena draft belum memprosesnya.

Konsekuensi:

- Per siklus keluar `n_diterima + 1` token, sehingga `draft_fraction` maksimum
  kira-kira `k / (k + 1)` (0,67 untuk k=2; 0,8 untuk k=4; 0,89 untuk k=8).
  Nilainya bisa sedikit lebih tinggi bila generasi terpotong `max_tokens` di
  tengah siklus, karena token bonus siklus terakhir tidak sempat keluar (smoke
  run di bawah: 11/16 = 0,6875 untuk k=2).
- Pada temperature 0 (greedy), setiap token yang keluar adalah argmax target,
  jadi secara prinsip teks sama dengan decoding tanpa draft. Namun target
  menghitung `k + 1` posisi dalam satu batch, berbeda dari baseline yang satu
  posisi per langkah. Perbedaan pembulatan floating point (terutama bf16) bisa
  membalik argmax yang nilainya hampir sama. **`n_output_mismatch > 0` belum
  tentu bug**: cari posisi token pertama yang berbeda sebelum menyimpulkan.

## 3. Propagasi argument draft

`stream_generate` (baris 667–771) menerima `draft_model` sebagai parameter
eksplisit dan meneruskan sisa argumen (`**kwargs`) ke generator token:

- Tanpa draft: `num_draft_tokens` dibuang dari kwargs, lalu `generate_step`
  dipakai; `from_draft` selalu `False`.
- Dengan draft: `max_kv_size` dan `prompt_progress_callback` dibuang
  (tidak didukung), `input_embeddings` ditolak, lalu
  `speculative_generate_step(prompt, model, draft_model, stream, **kwargs)`
  menerima `num_draft_tokens`, `sampler`, dan `max_tokens` lewat kwargs.
- Jika `num_draft_tokens` tidak diberikan, default fungsi adalah **2**.

`src/bench.py` memanggil `stream_generate(model, tokenizer, prompt_tokens,
max_tokens=..., sampler=make_sampler(temp=...), draft_model=...,
num_draft_tokens=k)`, sesuai jalur di atas.

## 4. Antarmuka CLI

Dari `python -m mlx_lm generate --help` (versi 0.32.1). Bentuk
`python -m mlx_lm.generate` masih berjalan tetapi mencetak peringatan
*deprecated*.

| Flag | Default | Catatan |
| --- | --- | --- |
| `--model` | `mlx-community/Llama-3.2-3B-Instruct-4bit` | **diam-diam memakai model lain bila tidak diisi** (alasan FR-02) |
| `--draft-model` | tidak ada | mengaktifkan speculative decoding |
| `--num-draft-tokens` | **3** | berbeda dari default fungsi (2); selalu tulis `k` eksplisit |
| `--max-tokens`, `-m` | 100 | |
| `--temp` | 0.0 | |
| `--seed` | tidak di-set | PRNG hanya di-seed bila flag diberikan; bench selalu memanggil `mx.random.seed(seed)` per run |
| `--chat-template-config` | — | JSON untuk `apply_chat_template`, mis. `'{"enable_thinking": false}'` |

CLI juga menolak draft model yang `vocab_size` tokenizer-nya berbeda dari
target. Contoh command yang setara dengan satu run Eksperimen B:

```bash
mlx_lm.generate --model mlx-community/Qwen3-4B-4bit \
    --draft-model mlx-community/Qwen3-0.6B-4bit --num-draft-tokens 4 \
    --max-tokens 256 --temp 0 --seed 0 \
    --chat-template-config '{"enable_thinking": false}' \
    --prompt "Janet's ducks lay 16 eggs per day. ..."
```

## Dampak pada benchmark

- `src/bench.py` sudah memakai nama field yang benar (`from_draft`,
  `peak_memory`, `generation_tps`, `prompt_tps`, `generation_tokens`) dan
  `load(..., revision=...)` untuk mem-pin commit model.
- **Ditambahkan:** pengecekan `vocab_size` tokenizer draft = target, meniru CLI.
- `generation_tokens` termasuk EOS. `joules_per_token` dibagi angka yang sama,
  sehingga konsisten antar-konfigurasi; jangan bandingkan dengan hitungan
  token yang membuang EOS.
- `prompt_tps` mode speculative mencakup prefill **dua** model, sehingga tidak
  sebanding langsung dengan baseline. Metrik utama adalah `generation_tps` dan
  `joules_per_token` (yang memakai `duration_s` end-to-end, D-003).
- `generation_tps` dari MLX tidak memasukkan waktu token pertama, sedangkan
  `duration_s` memasukkannya. Keduanya dicatat dan didefinisikan berbeda.
- Default `prefill_step_size` berbeda (2048 di jalur biasa, 512 di jalur
  speculative). Dampaknya kecil karena prompt GSM8K pendek (puluhan sampai
  ratusan token), tetapi tetap dicatat sebagai perbedaan jalur.

## Verifikasi eksekusi (smoke run CPU)

Pada 2026-10-24 `src/bench.py` dijalankan sungguhan dengan `mlx[cpu]==0.32.3`
dan `mlx-lm==0.32.1` di Linux x86_64 (tanpa GPU, `--no-power` karena
`powermetrics` hanya ada di macOS). Model `mlx-community/Qwen3-0.6B-4bit`
(commit `73e3e38`), prompt `gsm8k-001`, `--max-tokens 16 --warmup-tokens 4`.

| config | status | token | draft_fraction | peak memory | `output_sha256` |
| --- | --- | --- | --- | --- | --- |
| baseline (warm-up) | warmup | 4 | — | 0,37 GB | `c050764c…` |
| baseline | incomplete | 16 | — | 0,37 GB | `8e6b3d31…` |
| draft = target, k=2 (warm-up) | warmup | 4 | 0,75 | 0,73 GB | `c050764c…` |
| draft = target, k=2 | incomplete | 16 | 0,6875 | 0,73 GB | `8e6b3d31…` |

Yang terbukti:

- Pemanggilan `load(revision=...)`, `stream_generate(..., draft_model=...,
  num_draft_tokens=...)`, dan semua field `GenerationResponse` yang dipakai
  bench berjalan pada versi ini; record lolos `python -m src.schemas`, dan
  `python -m src.aggregate` membacanya tanpa error.
- Dengan draft identik dengan target, setiap token draft diterima, sehingga
  `draft_fraction` sama persis dengan hitungan siklus di §2, dan teks keluaran
  identik dengan baseline (hash sama).
- Memori puncak naik ±2× saat draft model dimuat (dua salinan bobot 0.6B).

Angka throughput (±0,2 token/s) tidak bermakna: backend CPU MLX di container
ini sangat lambat (matmul fp32 1024×1024 ±0,5 s) dan bukan perangkat target.
Pengukuran daya dan throughput yang sebenarnya tetap harus dijalankan di Mac.
