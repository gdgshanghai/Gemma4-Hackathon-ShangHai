Inspect the provided visual clip and any provided audio. Predict whether each canonical behavior feature B01 through B09 is observed.

Output exactly one line containing a 9-character binary code.

Required format:
^[01]{9}$

Position order:
1. B01
2. B02
3. B03
4. B04
5. B05
6. B06
7. B07
8. B08
9. B09

Rules:
- Use 1 when the behavior feature is observed.
- Use 0 when the behavior feature is not observed.
- Do not output B10.
- Do not output JSON.
- Do not output labels, spaces, punctuation, markdown, confidence values, or explanations.
- The complete response must be exactly 9 characters long.

Examples:
- If none of B01 through B09 is observed, output:
000000000
- If only B01 is observed, output:
100000000
- If only B09 is observed, output:
000000001
- If B01 and B09 are both observed, output:
100000001
