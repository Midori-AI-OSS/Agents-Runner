Rename MidoriAITemplateDetection class to MidoriaiTemplateDetection.

Files to edit:
1. agents_runner/midoriai_template.py
   - Rename class MidoriAITemplateDetection -> MidoriaiTemplateDetection.
   - Update all references to MidoriAITemplateDetection in the file (in scan_midoriai_agents_template return type and return statement).

2. agents_runner/environments/midoriai_template.py
   - Update import: from agents_runner.midoriai_template import MidoriAITemplateDetection -> MidoriaiTemplateDetection.
   - Update all type annotations and usages.

3. agents_runner/docker/agent_worker_prompt.py
   - Update import and all type annotations/usages.

4. agents_runner/docker/agent_worker_setup.py
   - Update import, type annotations (line 62 field, line 323 return type of _detect_and_persist_template), and class reference in _detect_and_persist_template (line 339 construction).

5. agents_runner/ui/interactive_prep_worker.py
   - Update import, type annotations, and usage.

---

Completed: Renamed class MidoriAITemplateDetection to MidoriaiTemplateDetection across all 5 files. All imports, type annotations, return types, and constructor references updated. No remaining references outside this task file.
