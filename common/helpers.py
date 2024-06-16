import json
from dataclasses import dataclass


@dataclass(frozen=True, match_args=False)
class CssStr:
    val: str


def css_stringify(val: int | float | str | dict | list | tuple | CssStr) -> str:
    if isinstance(val, (int, float, str)):
        return json.dumps(val)
    if isinstance(val, (CssStr)):
        return val.val
    if isinstance(val, (list)):
        return ",".join(map(css_stringify, val))
    if isinstance(val, (tuple)):
        return " ".join(map(css_stringify, val))
    if isinstance(val, dict):
        return " ".join(f"{k}({css_stringify(v)})" for k, v in val.items())
    raise ValueError(f"Unsupported type: {type(val)}")


def ints_to_unicode_range(ints: list[int] | set[int]):
    chunks: list[str] = list()
    if len(ints) == 0:
        return chunks

    def enc(c: int):
        return hex(c)[2:].upper()

    def _(start: int, end: int):
        s = f"U+{enc(start)}"
        if end > start:
            s += f"-{enc(end)}"
        return s

    ints = sorted(ints)
    start = ints[0]
    end = ints[0]
    for i in ints[1:]:
        if i == end + 1:
            end = i
            continue
        chunks.append(_(start, end))
        start = i
        end = i
    chunks.append(_(start, end))

    return chunks
