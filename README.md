# Prompt Project

Repository scaffold for prompt templates and processing.

Structure created:

```
.
├─ prompts/
│  └─ welcome_prompt.json
├─ prompt_templates/
│  └─ welcome_email.txt
├─ scripts/
│  └─ process_prompt.py
├─ outputs/     ← auto created, ignored by git
├─ .github/workflows/
│  ├─ on_pull_request.yml
│  └─ on_merge.yml
├─ requirements.txt
└─ README.md
```

Quick start (PowerShell):

```powershell
python -m pip install -r requirements.txt
python scripts/process_prompt.py
```

`outputs/` is included for runtime artifacts and is git-ignored by default.
