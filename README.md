##  Overview

This project implements an automated **prompt deployment pipeline** for Pixel Learning Co. using:

* **Amazon Bedrock** (Claude 3 Sonnet)
* **S3 Static Website Hosting**
* **GitHub Actions CI/CD**
* **Python-based prompt rendering + template engine**

The pipeline automatically:

1. Loads a structured **prompt config** from `prompts/`
2. Renders a **template** from `prompt_templates/`
3. Sends it to **Amazon Bedrock (InvokeModel API)**
4. Saves the output as `.html` or `.md`
5. Uploads to **ONE S3 bucket**, using:

   * `beta/outputs/` for pull requests
   * `prod/outputs/` for merges to main

---

# 1.  AWS Setup

## 1.1 Choose Region

Use a region where Bedrock is supported, e.g.:

```
us-east-1
```

---

## 1.2 Enable Bedrock Model Access

In AWS Console:

1. Go to **Amazon Bedrock**
2. Open **Model Access**
3. Enable:

```
anthropic.claude-3-sonnet-20240229-v1:0
```

⚠️ Do NOT use Provisioned Throughput — only real-time InvokeModel.

---

## 1.3 Create One S3 Bucket (Static Website Hosting)

Create the bucket:

Example:

```
pixel-learning-content
```

Then:

1. Go to **Bucket → Properties**
2. Scroll to **Static website hosting**
3. Enable
4. Set:

   * Index document: `index.html` (optional for assignment)

This bucket will store:

```
beta/outputs/*.html
prod/outputs/*.html
```

---

## 1.4 Create IAM User for GitHub Actions

Go to:
**IAM → Users → Create user**

Name:

```
pixel-learning-github
```

Select **Programmatic access** (Access Key).

### Attach this inline policy (replace your bucket name):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3Access",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::pixel-learning-content",
        "arn:aws:s3:::pixel-learning-content/*"
      ]
    },
    {
      "Sid": "BedrockInvoke",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": "*"
    }
  ]
}
```

Save the generated:

* `AWS_ACCESS_KEY_ID`
* `AWS_SECRET_ACCESS_KEY`

We will add these to GitHub Secrets.

---

# 2.  GitHub Secrets Setup

Go to:

**GitHub Repo → Settings → Secrets & Variables → Actions → New Secret**

Add:

| Secret Name             | Value (Example)          |
| ----------------------- | ------------------------ |
| `AWS_ACCESS_KEY_ID`     | from IAM                 |
| `AWS_SECRET_ACCESS_KEY` | from IAM                 |
| `AWS_REGION`            | `us-east-1`              |
| `S3_BUCKET`             | `pixel-learning-content` |

---

# 3.  Repository Structure

Your project should look like:

```
.
├─ prompts/
│  └─ welcome_prompt.json
├─ prompt_templates/
│  └─ welcome_email.txt
├─ scripts/
│  └─ process_prompt.py
├─ outputs/      ← generated automatically
├─ .github/workflows/
│  ├─ on_pull_request.yml
│  └─ on_merge.yml
├─ requirements.txt
└─ README.md
```

---

# 4.  Prompt Configs & Templates

## 4.1 Create a Prompt Config

File: `prompts/welcome_prompt.json`

```json
{
  "slug": "welcome_jordan",
  "template": "welcome_email.txt",
  "output_format": "html",
  "max_tokens": 500,
  "variables": {
    "student_name": "Jordan",
    "course_name": "Intro to Automation",
    "onboarding_link": "https://pixel-learning.example.com/start"
  }
}
```

---

## 4.2 Create a Template

File: `prompt_templates/welcome_email.txt`

```txt
Write a friendly welcome email.

Student: {{ student_name }}
Course: {{ course_name }}
Onboarding link: {{ onboarding_link }}

Include:
- 3 tips for success
- Supportive tone
```

---

# 5.  Python Script (process_prompt.py)

File: `scripts/process_prompt.py`

```python
import os
import json
import glob
from pathlib import Path

import boto3
from jinja2 import Template

MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"


def load_config(path):
    with open(path, "r") as f:
        return json.load(f)


def render_template(template_name, variables):
    tpath = Path("prompt_templates") / template_name
    with open(tpath, "r") as f:
        template = Template(f.read())
    return template.render(**variables)


def call_bedrock(prompt, max_tokens, region):
    client = boto3.client("bedrock-runtime", region_name=region)

    payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [
            {"role": "user", "content": f"Human: {prompt}"}
        ]
    }

    response = client.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps(payload)
    )

    data = json.loads(response["body"].read())
    return data["content"][0]["text"]


def save_output(slug, fmt, content):
    ext = "html" if fmt == "html" else "md"
    Path("outputs").mkdir(exist_ok=True)
    file_path = Path("outputs") / f"{slug}.{ext}"

    with open(file_path, "w") as f:
        f.write(content)

    return file_path


def upload_to_s3(file_path, environment):
    region = os.environ["AWS_REGION"]
    bucket = os.environ["S3_BUCKET"]
    prefix = f"{environment}/outputs/"

    s3 = boto3.client("s3", region_name=region)

    key = prefix + file_path.name

    content_type = "text/html" if file_path.suffix == ".html" else "text/markdown"

    s3.upload_file(
        str(file_path),
        bucket,
        key,
        ExtraArgs={"ContentType": content_type}
    )

    print(f"Uploaded to s3://{bucket}/{key}")


def main():
    environment = os.environ.get("ENVIRONMENT", "beta")
    region = os.environ["AWS_REGION"]

    for path in glob.glob("prompts/*.json"):
        cfg = load_config(path)

        prompt = render_template(cfg["template"], cfg["variables"])
        output = call_bedrock(prompt, cfg["max_tokens"], region)

        out_file = save_output(cfg["slug"], cfg["output_format"], output)

        upload_to_s3(out_file, environment)


if __name__ == "__main__":
    main()
```

---

# 6.  GitHub Actions Workflows

## 6.1 Pull Request Workflow → BETA

File: `.github/workflows/on_pull_request.yml`

```yaml
name: Beta Prompt Pipeline

on:
  pull_request:
    branches: [ main ]

jobs:
  beta-build:
    runs-on: ubuntu-latest

    env:
      AWS_REGION: ${{ secrets.AWS_REGION }}
      S3_BUCKET: ${{ secrets.S3_BUCKET }}
      ENVIRONMENT: beta

    steps:
      - uses: actions/checkout@v4

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ secrets.AWS_REGION }}

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - run: pip install -r requirements.txt

      - run: python scripts/process_prompt.py
```

---

## 6.2 Merge Workflow → PROD

File: `.github/workflows/on_merge.yml`

```yaml
name: Prod Prompt Pipeline

on:
  push:
    branches: [ main ]

jobs:
  prod-build:
    runs-on: ubuntu-latest

    env:
      AWS_REGION: ${{ secrets.AWS_REGION }}
      S3_BUCKET: ${{ secrets.S3_BUCKET }}
      ENVIRONMENT: prod

    steps:
      - uses: actions/checkout@v4

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ secrets.AWS_REGION }}

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - run: pip install -r requirements.txt

      - run: python scripts/process_prompt.py
```

---

# 7.  How to Trigger the Pipeline

## BETA Pipeline (Preview)

Triggered when you open a **Pull Request** to `main`.

Outputs uploaded to:

```
s3://pixel-learning-content/beta/outputs/<file>.html
```

---

## PROD Pipeline (Production)

Triggered when you **merge to main**.

Outputs uploaded to:

```
s3://pixel-learning-content/prod/outputs/<file>.html
```

---

# 8.  How to View the Generated Output

1. Get your bucket website endpoint from S3 console
   Example:

```
http://pixel-learning-content.s3-website-us-east-1.amazonaws.com
```

2. Append output path:

```
/beta/outputs/welcome_jordan.html
```

or

```
/prod/outputs/welcome_jordan.html
```

Example full URL:

```
http://pixel-learning-content.s3-website-us-east-1.amazonaws.com/prod/outputs/welcome_jordan.html
```

---
