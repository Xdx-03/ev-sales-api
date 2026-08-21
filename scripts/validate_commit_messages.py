from __future__ import annotations

import argparse
import re
import subprocess

ALLOWED_SUBJECT = re.compile(
    r"^(feat|fix|test|docs|refactor|ci|chore|perf|build|style|revert)"
    r"(?:\([a-z0-9][a-z0-9-]*\))?: [\u4e00-\u9fff]"
)
ZERO_SHA = "0" * 40
MAX_SUBJECT_LENGTH = 72


def _commit_subjects(base_sha: str, head_sha: str) -> list[str]:
    revision = head_sha if base_sha == ZERO_SHA else f"{base_sha}..{head_sha}"
    result = subprocess.run(
        ["git", "log", "--format=%s", revision],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    return [line for line in result.stdout.splitlines() if line]


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 Conventional Commits 中文标题")
    parser.add_argument("base_sha")
    parser.add_argument("head_sha")
    args = parser.parse_args()

    subjects = _commit_subjects(args.base_sha, args.head_sha)
    if not subjects:
        raise SystemExit("提交范围内没有可校验的提交。")

    invalid = [
        subject
        for subject in subjects
        if not ALLOWED_SUBJECT.match(subject) or len(subject) > MAX_SUBJECT_LENGTH
    ]
    if invalid:
        details = "\n".join(f"- {subject}" for subject in invalid)
        raise SystemExit("提交标题必须使用“类型: 中文说明”, 且不超过 72 个字符:\n" + details)

    print(f"提交信息校验通过: {len(subjects)} 个提交")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
