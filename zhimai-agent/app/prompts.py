import re
from .config import ROOT

PATTERN = re.compile(r'{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}')


def render(name, values):
    template = (ROOT / 'prompts' / name).read_text(encoding='utf-8')
    # 一次性替换模板占位符，不再次解释用户输入中的花括号。
    return PATTERN.sub(lambda match: str(values.get(match.group(1), match.group(0))), template)
