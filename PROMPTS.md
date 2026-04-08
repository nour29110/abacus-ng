# AI Usage Log

I used Claude throughout this take home. My philosophy: use AI to pressure test my own thinking, not to generate code I can't defend in an interview. Every prompt below was me trying to either break my own assumptions or force the model off its default "average of the internet" answer.

I also deliberately kept the AI away from anything load-bearing in the parser. If I can't explain a line of code, it doesn't go in the repo.

---

## Part 1: Code Review Prompts

### Prompt 1, adversarial review

> You are a staff security engineer who has seen every webhook vulnerability there is. Below is a Python Flask webhook. Don't list bugs generically, instead, for each issue, write the exact curl command an attacker would use to exploit it, and tell me which CWE it maps to. Be ruthless. If it's fine, say it's fine. [code pasted]

**What I was hoping for:** The "write the exploit curl" framing is the trick. Without it, LLMs give you vague advice like "consider using parameterized queries." With it, they're forced to be concrete, because you can't write a fake curl command. The CWE requirement does the same thing for cryptographic issues.

**What it actually did:** Good. It found the SQL injection, the timing attack, the `dev-secret` default, and the missing schema validation. It wrote a working `curl` for the SQLi and mapped things to CWE-89 and CWE-208 correctly. It flagged `SHA256(secret + body)` as "not constant-time HMAC," which is technically true but missed the actual attack.

**Did I re-prompt?** Yes. See prompt 2.

---

### Prompt 2, narrowing in on the crypto

> You flagged SHA256(secret + body) as "not constant-time HMAC." That's not the main problem. Name the specific cryptographic attack this construction enables and explain why HMAC was invented to prevent exactly this.

**What I was hoping for:** I already knew the answer was length-extension. I wanted to see whether the model would recover when nudged, or whether it would double down on its first (wrong) explanation. This is basically a test of whether it knows crypto or just pattern-matches.

**What it actually did:** Correctly identified length-extension, explained the Merkle-Damgård structure, and gave the HMAC inner/outer pad rationale. Good recovery, but the fact that it needed the nudge at all is exactly why I don't trust LLM security reviews unsupervised. If I hadn't already known what the real issue was, I would have stopped at prompt 1 with an incomplete review.

**Did I change my approach?** After this, I stopped treating the AI's first pass as "the review" and started treating it as "a list of leads to verify." Everything in `REVIEW.md` went through me before it landed.

---

## Part 2: Coding Challenge Prompts

### Prompt 3, setting the constraint

> I'm building a calculator backend and I refuse to use eval or any expression-evaluation library. That would contradict the security lesson from my own code review. Walk me through implementing a Pratt parser for + - * / ^ with unary minus and parens, in Python, in under 100 lines. Don't give me the code yet. First explain the precedence-climbing idea in plain English, then list the token types, then list the functions I'll need. I want to write it myself.

**What I was hoping for:** Two things. First, I wanted a scaffold, not code, because I planned to type the parser myself and needed to understand it well enough to defend every line in an interview. Second, the "no libraries" constraint is critical: the default AI answer to "build a calculator" is to use `eval`, `ast.literal_eval`, `sympy`, or `mathjs`. All of those sidestep the interesting part.

**What it actually did:** Great. It explained Pratt parsing in terms of "left binding power" vs "right binding power" (which is actually a cleaner mental model than the Wikipedia article), listed the token kinds I'd need, and outlined `tokenize`, `parse_expression(min_bp)`, and `parse_atom` as the three functions. Crucially, it gave me no code. I wrote the parser from that scaffold.

**Did I re-prompt?** No. The scaffold was all I needed, and I wanted the code to be mine.

---

### Prompt 4, using the AI as a fuzzer

> Here's my Pratt parser. Try to break it. Feed it 10 adversarial inputs, things like deeply nested parens, unary minus chains, float edge cases, empty string, unicode, scientific notation with weird exponents, and tell me which ones crash or give wrong output. Don't fix anything, just report. [code pasted]

**What I was hoping for:** LLMs are excellent at generating test cases and terrible at being trusted to fix code. This prompt uses the first capability and forbids the second. "Don't fix anything" is the key phrase. Without it, the model will rewrite your parser instead of testing it.

**What it actually did:** Generated 10 inputs. Six passed, four were interesting. Specifically: it found that `1e999` returned `inf` silently (which I then caught with the `math.isfinite` check in the evaluator), and it flagged `((((1))))` as a potential recursion concern (it's fine at that depth but would blow up at 1000+, which I'm not going to defend against in a calculator). The other two "issues" were false positives where the parser was actually doing the right thing and the model was wrong about the expected output. I wrote those up as passing test cases to catch future regressions.

**Did I re-prompt?** No. Moved on and wrote the tests.

---

## What Worked, What Didn't

**What the AI did well:**
- Generating adversarial test inputs once I constrained it to "report, don't fix"
- Explaining Pratt parsing at the right level of abstraction for my prompt
- Finding obvious bugs in the code review

**What the AI did poorly:**
- First-pass crypto review missed length-extension until I nudged it
- Default answers always reach for libraries, I had to explicitly forbid `eval` and `sympy` and `mathjs` before I got useful output on the parser
- Was confidently wrong twice in prompt 4 about what my parser should output, I had to verify each "bug" it reported before accepting it

**How I adjusted my prompts:**
Every prompt in this file starts with a constraint. "Don't give me code yet." "Don't fix anything, just report." "No libraries." "Be ruthless." Constraints are how you get useful answers out of an LLM, because the default output is the average of everything it's ever seen, and the average is never what you want. If the prompt doesn't have a constraint in it, I'm usually going to throw the answer away.

The other thing I learned: I treated the AI's output as leads to investigate, not conclusions to accept. Every bug it reported got verified. Every suggestion got checked against documentation or tested. The review, the parser, and the test suite are all mine, the AI just accelerated the parts where I already knew what I was looking for.