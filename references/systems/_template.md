# Template `systems/`

Salin file ini untuk tiap sistem baru di grid `systems/`. Ganti tiap kalimat
instruksi dengan isi nyata, dan hapus baris label bila sudah menandai tiap
klaim di badan teks.

> Label tiap klaim: [code] / [docs] / [inferred]

## Arketipe

Sebutkan arketipe (bisa hibrida) sistem ini dan alasan singkat berdasar 6 sumbu
pembeda.

## 1. Loop shape

Jelaskan bentuk loop-nya: ReAct / plan-execute / loop-until-done, dan siapa
yang memutuskan berhenti.

## 2. Context

Jelaskan strategi compaction, summarization, atau filesystem-as-memory yang
dipakai sistem ini.

## 3. Tool surface

Jelaskan apakah sistem ini memakai banyak tool sempit atau sedikit tool luas,
dan kenapa desain itu dipilih.

## 4. Delegation

Jelaskan apakah ada subagent atau arsitektur flat, dan bagaimana hasil
delegasi kembali ke pemanggil.

## 5. State & resume

Jelaskan mekanisme todo, scratchpad, checkpoint, dan resume yang dipakai.

## 6. Safety gate

Jelaskan kapan sistem ini minta izin manusia dan apa yang di-sandbox.

## 7. Capability routing & policy

Jelaskan bagaimana sistem memutuskan skill/mode mana yang dipakai: prosa +
judgment model, manifest deklaratif, atau classifier.

## Sumber

Cantumkan sumber tiap klaim: repo/commit untuk `[code]`, tautan dokumentasi
resmi untuk `[docs]`, atau catatan bahwa itu simpulan dari perilaku produk
untuk `[inferred]`.
