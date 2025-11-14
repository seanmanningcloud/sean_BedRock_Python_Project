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
