"""Bounded, source-literal verification for open structured fact predicates.

Canonical predicate names are extensible. A small set of linguistic answer
types disambiguates attributes, while the *saved text* supplies domain words.
This is not a semantic entailment model: unsupported paraphrases abstain. No
query, entity, benchmark ID or application-specific predicate is enumerated.
"""
from __future__ import annotations

import re
from collections.abc import Mapping

from .memory_correction import _typed_literal_supported


# Ordered narrow attributes precede broad names, dates and quantities. These
# describe answer types, not a closed schema of user facts.
_ATTRIBUTES = (
    (r"密码|口令|解锁码|门禁码|PIN", r"密码|口令|解锁码|门禁码|password|passcode|(?:^|_)pin(?:_|$)", "secret"),
    (r"手机号|电话号码|联系电话|手机号码", r"手机号|电话|phone|telephone", "phone"),
    (r"序列号|编号|证号|卡号|学号|工号|账户号|账号", r"序列号|编号|证号|卡号|学号|工号|账户号|账号|serial|number|identifier|account", "identifier"),
    (r"有效期|到期|有效到", r"有效期|有效至|到期|expir|valid_until", "expiry"),
    (r"(?:哪天|何时|什么时候).*(?:该还|归还|还书)|归还日", r"归还|还书|due_date|return_date", "return_date"),
    (r"品牌|牌子", r"品牌|牌子|brand", "brand"),
    (r"型号", r"型号|model", "model"),
    (r"品种|种类", r"品种|种类|variety|cultivar|species|type", "variety"),
    (r"颜色|色号", r"颜色|色号|[\u4e00-\u9fff]色|color|colour", "color"),
    (r"花了多少|多少钱|价格|费用", r"价格|费用|花了|price|cost", "price"),
    (r"职业|做哪一?行|做什么工作|从事什么", r"职业|工作|从事|occupation|profession", "occupation"),
    (r"负责|职责|分工", r"负责|职责|分工|role|responsibil|duty", "responsibility"),
    (r"文件夹|目录|路径", r"文件夹|目录|路径|folder|directory|path", "path"),
    (r"每周|星期|周几|每星期", r"每周|星期|周[一二三四五六日天]|weekday|weekly", "weekday"),
    (r"在哪(?:里|儿)?|在哪里|在哪个|哪儿|什么地方|去的地方|什么房间|哪个房间|哪个地点|住哪", r"地点|位置|房间|地址|住址|在[^，。]{1,30}(?:室|楼|馆|站|店|园|路)|location|venue|room|address|residence", "location"),
    (r"叫什么|叫啥|名字|姓名|怎么称呼", r"名字|姓名|称呼|叫|名为|name|nickname", "name"),
    (r"生日|出生日期", r"生日|出生日期|birthday|birth_date", "birthday"),
    (r"日期|哪天|何时|什么时候|几月|几号", r"日期|日子|时间|date|schedule|time|\d{4}[-年]\d{1,2}", "date"),
)

_FILLER = re.compile(
    r"还记得|记不记得|以前告诉过|告诉过|告诉|提醒|帮我回想|回想|回忆|帮我|请你|"
    r"现在|目前|如今|当时|以前|历史|今年|那会儿|那时候|原本|原来|常用|"
    r"用的|使用的|选的|叫做|叫什么|是什么|是哪|什么|哪里|哪个|哪种|多少|几个|几只|是否|怎么|"
    r"每周|每星期|星期|哪天|时候|哪儿|放在|放到|应该|该|可以|已经|"
    r"自己|用户|[那这][只台个箱盆件本部条张项]|那我|我的|你的|他的|她的|它的|"
    r"[我你他她它的了呢吗呀啊是为在去哪再把这那有用和到]|[?？。！!，,；;：:\s]"
)


def literal_values(value) -> tuple[str, ...]:
    """Flatten bounded JSON values only; property names do not prove values."""
    if isinstance(value, Mapping):
        return tuple(v for item in value.values() for v in literal_values(item))
    if isinstance(value, (list, tuple)):
        return tuple(v for item in value for v in literal_values(item))
    if value is None:
        return ()
    if isinstance(value, bool):
        return ("true" if value else "false",)
    return (str(value).strip(),) if str(value).strip() else ()


def has_fact_value(metadata) -> bool:
    return "fact_value" in metadata and bool(literal_values(metadata["fact_value"]))


def _without_subject(text, entry):
    meta = entry.metadata
    if meta.get("fact_subject") == "user:self":
        return text
    labels = [str(meta.get("fact_subject", "")).split(":", 1)[-1],
              str(meta.get("entity_id", "")).split(":", 1)[-1]]
    labels += [v for v in meta.get("subject_aliases", ()) if isinstance(v, str)]
    for label in sorted(set(labels), key=len, reverse=True):
        if len(label) >= 2 and label not in {"self", "user", "character"}:
            text = text.replace(label, " ")
    return text


def _anchors(text):
    # Preserve exact quoted works and Latin identifiers; never remove them as
    # generic question words or silently treat a different work as equivalent.
    text = re.sub(r"(?:20\d{2}[年/-])?\d{1,2}[月/-]\d{1,2}日?", " ", text)
    text = re.sub(r"20\d{2}年|\d{1,2}月", " ", text)
    separated = _FILLER.sub(" ", text.casefold())
    clean = re.sub(r"\s+", "", separated)
    terms = []
    for token in re.findall(r"[\u4e00-\u9fff]+|[a-z0-9_./-]+", separated):
        if all("\u4e00" <= c <= "\u9fff" for c in token):
            terms.extend(token[i:i+2] for i in range(len(token)-1))
            if len(token) == 1:
                terms.append(token)
        else:
            terms.append(token)
    return clean, tuple(dict.fromkeys(terms))


def literal_field_support(entry, query: str) -> bool:
    """Require a stated literal value, attribute type and matching object.

    The caller separately authenticates subject, owner, scope and lifetime.
    Unknown predicate strings are allowed; unknown evidence is not.
    """
    meta = entry.metadata
    values = literal_values(meta.get("fact_value"))
    if not values or not (entry.source_ids or (entry.user_confirmed and
            entry.source in {"explicit_user_request", "user_correction", "profile_edit"})):
        return False
    # Use the same scalar-boundary proof as structured corrections: 7 cannot
    # be substantiated by 17, nor false by falsehood.
    if not _typed_literal_supported(meta["fact_value"], entry.summary):
        return False
    query = _without_subject(query, entry)
    search = " ".join((entry.title, entry.summary,
                       str(meta.get("fact_predicate", "")), str(meta.get("fact_domain", "")))).casefold()
    quoted = re.findall(r"《([^》]+)》|[“\"]([^”\"]+)[”\"]", query)
    if any((a or b).casefold() not in search for a, b in quoted):
        return False
    query_type = next(((pattern, evidence, name) for pattern, evidence, name in _ATTRIBUTES
                       if re.search(pattern, query, re.I)), None)
    if query_type:
        pattern, evidence, _ = query_type
        if not re.search(evidence, search, re.I):
            return False
        query = re.sub(pattern, " ", query, flags=re.I)
        # Location questions often leave a generic noun after the interrogative.
        if query_type[2] == "location":
            query = re.sub(r"房间|地方|地点|位置", " ", query)
        if query_type[2] == "path":
            query = re.sub(r"哪个|哪一个", " ", query)
    clean, terms = _anchors(query)
    # Removal of a linguistic attribute never removes its domain noun: a
    # phone-number question cannot be answered with a card number, or a bag's
    # colour with the user's shirt colour.
    source_clean, _ = _anchors(_without_subject(search, entry))
    if clean and clean in source_clean:
        return True
    if not terms:
        return query_type is not None
    # A missing object qualifier is not a small ranking penalty: east/west or
    # a particular device can distinguish two otherwise identical facts.
    # Semantic paraphrases that cannot satisfy this literal proof abstain.
    return all(term in source_clean for term in terms)


def literal_subject_match(entry, subjects: tuple[str, ...], query: str) -> bool:
    """A canonical constraint is never relaxed by embedding similarity."""
    meta = entry.metadata
    subject = str(meta.get("fact_subject") or ("user:self" if meta.get("fact_slot") else ""))
    entity = str(meta.get("entity_id", ""))
    if not subjects:
        return True
    return subject in subjects or (bool(entity) and entity in subjects)


def mention_candidates(query: str, subjects: tuple[str, ...]) -> tuple[str, ...]:
    """At most 32 exact alias probes from possessive/name prefixes.

    They resolve only against current source-backed aliases, never a list of
    occupations or guessed names. Candidate text alone cannot establish a link.
    """
    pieces = [s.removeprefix("relation:").removeprefix("entity:") for s in subjects
              if s != "user:self"]
    text = re.sub(r"^(?:那|现在|以前|告诉我|请告诉我|还记得|我(?:的)?|用户的)+", "", query)
    prefix = re.match(r"[\u4e00-\u9fffA-Za-z·]{2,24}", text)
    if prefix:
        pieces += [prefix[0][:n] for n in range(min(16, len(prefix[0])), 1, -1)]
    return tuple(dict.fromkeys(s for s in pieces if 2 <= len(s) <= 24))[:32]
