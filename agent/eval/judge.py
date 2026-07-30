import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.environ["GROQ_API_KEY"])

JUDGE_MODEL = "llama-3.1-8b-instant"  # small + cheap is fine for a narrow yes/no judgment


def llm_judge(answer: str, criteria: str) -> tuple[bool, str]:
    """Returns (passed, reason). Kept deliberately narrow: the judge only ever
    sees the answer and the specific criteria for THIS task — not the whole
    conversation — so it can't be swayed by irrelevant context."""
    prompt = (
        f"Criteria: {criteria}\n\n"
        f"Answer to evaluate: {answer}\n\n"
        "Does the answer satisfy the criteria? Reply in exactly this format:\n"
        "VERDICT: PASS or FAIL\n"
        "REASON: one short sentence"
    )
    response = client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,  # determinism matters for a judge — same input should always get same verdict
    )
    text = response.choices[0].message.content
    verdict_line = text.split("REASON:")[0].upper()  # only look at the VERDICT line for PASS/FAIL
    passed = "PASS" in verdict_line
    reason = text.split("REASON:")[-1].strip() if "REASON:" in text else text
    return passed, reason