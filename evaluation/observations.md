# Observations from first real run (qwen2.5 0.5b / 1.5b / 3b, CPU only)

1. Sky task ("three short sentences"): small model returned 2 sentences, validation
   PASSED (validator false accept). Analyzer found no constraint because the
   length rule only matches digits, not number words ("three").
2. Translation task: correct French, but answer was phrased as "X translates to X".
   Heuristic validators cannot judge this.
3. No escalation happened in these 3 tasks; all first attempts passed validation.
4. Latency includes model load time on the first call to each model.