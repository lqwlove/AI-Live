"""Heuristic: whether text is primarily Chinese (CJK), aligned with ai.replier mock multilang checks."""


def append_zh_in_parens(original: str, zh: str) -> str:
    """展示用：原文后紧跟 (译文)，只推一条给前端。"""
    z = (zh or "").strip()
    if not z:
        return original
    return f"{original}({z})"


def is_primarily_chinese(text: str) -> bool:
    s = text.strip()
    if not s:
        return True

    cjk = sum(1 for c in s if "\u4e00" <= c <= "\u9fff")
    latin = sum(1 for c in s if ("A" <= c <= "Z") or ("a" <= c <= "z"))

    if cjk == 0 and latin == 0:
        return True
    if cjk == 0 and latin > 0:
        if len(s) <= 1:
            return True
        return False
    if latin == 0:
        return True
    return cjk >= latin
