Rename midori_ai_url to midoriai_url and _MIDORI_AI_URL to _MIDORIAI_URL.

Files to edit:
1. agents_runner/gh/task_plan.py
   - Rename constant _MIDORI_AI_URL -> _MIDORIAI_URL.
   - Rename kwarg midori_ai_url -> midoriai_url in _append_pr_attribution_footer call to load_prompt.
   - Note: The function parameter name in load_prompt() must match the new template placeholder {midoriai_url}.

2. agents_runner/prompts/pr_attribution_footer.md
   - Rename {midori_ai_url} -> {midoriai_url} in template variable list and usage line.

3. agents_runner/tests/test_prompt_loader_substitution.py
   - Replace all occurrences of midori_ai_url -> midoriai_url (kwarg on lines 14, 34; placeholder assertions on lines 23, 40).

4. agents_runner/tests/test_pr_footer_attribution.py
   - Replace "{midori_ai_url}" -> "{midoriai_url}" in _FOOTER_PLACEHOLDERS.
   - Replace midori_ai_url -> midoriai_url in assertions.

Completed by Coder. All four files updated: constant renamed to _MIDORIAI_URL, kwarg changed to midoriai_url, template placeholder changed to {midoriai_url}, test files updated accordingly.
