"""Shared regex constants for the doc pipeline (leaf module)."""

import re

KEYWORD_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_./:-]+|[\u4e00-\u9fff]+")
VERSION_TOKEN_PATTERN = re.compile(
    r"(?:^|[^a-z0-9])(?:v(?:ersion)?|版本|rev(?:ision)?|修订)\s*[-_ ]?(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
DATE_TOKEN_PATTERN = re.compile(
    r"((?:19|20)\d{2})[-/.年](0?[1-9]|1[0-2])[-/.月](0?[1-9]|[12]\d|3[01])日?"
)
COMPACT_DATE_TOKEN_PATTERN = re.compile(r"(?<!\d)((?:19|20)\d{2})(0[1-9]|1[0-2])([0-3]\d)(?!\d)")
EXPIRY_HINT_PATTERN = re.compile(
    r"(?:有效期至|截止(?:日期)?|失效(?:日期)?|废止(?:日期)?|截止到|截至)\s*[:：]?\s*"
    r"(((?:19|20)\d{2})[-/.年](0?[1-9]|1[0-2])[-/.月](0?[1-9]|[12]\d|3[01])日?|((?:19|20)\d{2})(0[1-9]|1[0-2])([0-3]\d))"
)

