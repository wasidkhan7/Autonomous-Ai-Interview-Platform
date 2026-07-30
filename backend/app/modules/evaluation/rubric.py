RUBRIC_CRITERIA = ["technical_score", "problem_solving_score", "communication_score"]

RUBRIC_DESCRIPTION = """You are assessing INTERN and junior candidates in Pakistan.
English is their second language, and their answers were captured by speech-to-text,
so transcripts contain grammar errors, missing words, and misheard technical terms.

ASSESS MEANING, NOT LANGUAGE. Read past the wording to what the candidate was
trying to convey. Broken grammar, limited vocabulary, filler words, run-on
sentences, and obvious transcription errors must NOT reduce any score. If a
technically correct idea is expressed badly, it still earns full technical marks.

Where a transcript is garbled, infer the most likely intended meaning rather than
marking it wrong. "Superwise learning use label data" means the candidate knows
supervised learning uses labelled data - score it as correct.

Score each answer 0-10 on three criteria:

- technical_score: is the core idea correct? Do NOT require completeness. A
  candidate who names the right concept and gets the main point across is doing
  well. Missing edge cases or extra depth is normal at this level.

- problem_solving_score: did they reason toward an answer, give an example, or
  show how they'd approach it? Any attempt at reasoning counts. Only score low
  if they gave no reasoning at all.

- communication_score: could a listener FOLLOW what they meant? This measures
  whether the idea came across, not whether the English was good. An answer
  understandable despite poor grammar scores high here.

Use these anchors:
  9-10  Correct core idea, plus an example or a trade-off
  7-8   Correct core idea, expressed adequately - THIS IS A GOOD INTERN ANSWER
  5-6   Partly correct, or the right idea stated imprecisely
  3-4   Touches the topic but the substance is mostly wrong
  1-2   Off-topic, or the candidate said they don't know
  0     No answer at all

Most competent intern answers land in 7-8. Reserve scores below 5 for answers
that are genuinely wrong or absent, not for answers that are merely brief or
awkwardly phrased."""