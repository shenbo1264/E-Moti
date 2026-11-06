"""Small deterministic evidence-demand router, with bounded ambiguous fallback.

This is deliberately a local policy, not a universal intent classifier. Its
reason/constraints are public so failures can be measured and corrected. No
model is called to route greetings or exact facts.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import re
from collections.abc import Mapping, Sequence

from .retrieval_contract import RetrievalBudget, RetrievalIntent, RetrievalPlan


_CASUAL = re.compile(r"^(?:[你您]好(?:呀|啊)?|嗨|哈[喽啰]|早(?:上好|安)?|晚上好|晚安|谢谢(?:你)?|"
                    r"(?:今天|现在|我)?(?:有点|好|很|太)?(?:无聊|累|困|开心|难过|烦)(?:了|啊|呀)?|"
                    r"陪我(?:聊聊|聊天|待一会儿)|随便聊聊|休息一会儿|嗯+|好的?|哈哈+)[。！!~～ ]*$", re.I)
_REFERENCE = re.compile(r"(?:那|这)(?:他|她|它|次|件|个|段)|^[他她它]|^那?我的?(?:呢|[?？])|详细|展开|后来呢|然后呢")
_QUESTION = re.compile(r"什么|哪里|哪儿|在哪|怎么|怎样|如何|多少|多久|几点|几岁|几[个次天本盆杯辆只件页张台粒]|哪[个些位种天本部项家一款间]|谁|为什么|是否|吗|呢|[?？]|记得|回忆|讲讲|说说|聊聊|找出来|再报一遍")
_HISTORY = re.compile(r"以前|过去|曾经|当时|那时|原来|之前住|历史")
_DETAIL = re.compile(r"详细|展开|具体|原始|证据|为什么|过程|细节|怎么|发生了什么|先后|后来|然后")
_EPISODE = re.compile(r"我们|咱们|一起|共同|第一次|那次|那段|那晚|那天|^那[个台件本]|回忆|经历|回顾|后我|上次.{0,14}(?:玩|游戏|休息|学习|聊天)")
_TASK = re.compile(r"部署|发布|安装|编译|构建|报错|端口|调试|任务经验|执行记录|踩坑|失败原因|排错|导出|备份|迁移|证书|故障|服务.*失败|^(?:为什么|上次|那次).{0,6}失败|后来.{0,8}成功")
_LIVE = re.compile(r"完成了吗|做完了吗|结束了吗|成功了吗|跑完了吗|进度|进展|跑到哪|现在.{0,10}(?:状态|在做|干到|在哪)|正在|还在运行|当前状态")
_AUTHORITIES = {"relay": "relay", "codex": "relay", "claude": "relay", "游戏": "game", "手机": "phone"}
_RELATION_FIELDS = ((r"叫(?:什么)?(?:名字)?|姓名|名字|哪位|是谁", "name"),
                    (r"住(?:在|哪|哪里|哪儿)|居住|地址|住址", "residence"),
                    (r"职业|工作|从事|是做什么|做哪[一]?行", "occupation"))
_SELF_WORDS = {"名字", "姓名", "昵称", "称呼", "职业", "工作", "地址", "住址", "住处", "居住地", "饮料", "饮品", "偏好", "口味"}
_FIELD_HEADING = re.compile(r"^(?:(?:我的)?(?:饮品偏好|饮料偏好|个人偏好|互动偏好|互动边界|昵称|称呼|姓名|居住地)"
                            r"(?:和|及|、)?)+(?:是什么|有哪些|什么)?[?？]?$")
_OPEN_FIELD_HEADING = re.compile(r"^(?:[^，。！？?]{1,24}(?:偏好|目标|安排|城市|地址)(?:是什么|有哪些|是哪|在哪)?|(?:my )?favou?rite [a-z][a-z -]{1,30})[?？]?$", re.I)
_NO_RECALL = re.compile(r"(?:不需要|不用|无需|不要|别)(?:再|去|特意)?(?:翻|查|检索|回顾|回忆|提)"
                        r"[^，。；;]{0,12}(?:记忆|往事|旧事|经历|过去|以前|历史)")
_VERSION = re.compile(r"(?<!\d)v?(\d+\.\d+(?:\.\d+)?)", re.I)
_PAST_EXECUTION = re.compile(r"上次|上回|之前|以前|当时|原来|那次|经验|沿用|复用|照做")
_PROCEDURE = re.compile(r"步骤|操作|顺序|条件|前提|办法|方法|处理|排序|连接|配对|配置|合并|拼好|识别|成功|失败|怎么|怎样|如何")
_CREATIVE = re.compile(r"假如|假设|如果我们|帮我编|(?:再)?编[一二三四五六七八九十两0-9]+[句个段篇]|"
                       r"写[一二三四五六七八九十两0-9]+[句首个段篇]|讲[一二三四五六七八九十两0-9]+个.*(?:笑话|故事)|"
                       r"给我.{0,6}(?:鼓励|打气)|聊点.*无关")
_NAMED_USER_MENTION = re.compile(
    r"我(?:的)?(?:朋友|同事|同学|家人|亲戚|邻居|搭档|室友|老师|教练|同伴)"
    r"([\u4e00-\u9fffA-Za-z·]{2,12}?)(?=说|做|买|带|拿|选|写|发|告诉|最近|刚刚|今天|昨天)")


def _literal_subject(query: str, subjects: tuple[str, ...] = (),
                     predicates: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Keep a linguistic owner hint; the store must ground it with real aliases.

    This does not create entities or guess a person's identity. An unresolved
    relationship stays unresolved rather than becoming the owner of the save.
    """
    if re.match(r"^那?我的?(?:呢|[?？])", query):
        return ("user:self",)
    if re.match(r"^那?[他她它]", query):
        # A pronoun is not an implicit reference to the owner of the save.
        # The bounded user-history resolver below may establish its antecedent.
        return ()
    if any(p.startswith("宠物称呼:") for p in predicates):
        return subjects
    relation = re.search(r"(?:我|用户)(?:的)?([^，。；;?？]{1,12}?)(?:的|(?P<owned_action>买|租|种|养|用|修|做|写)的)"
                         r"(?=[^，。；;?？]{2})", query)
    specific_subject = (subjects and subjects != ("user:self",)
                        and not any(s.startswith("relation:们") for s in subjects))
    # A field-specific parse keeps the complete relationship. A coarse first
    # possessive must not replace it with an activity or the parent person.
    # Explicit owned-object syntax still selects its owner rather than treating
    # the object phrase as a person. Reuse the existing action vocabulary.
    if specific_subject and not (relation and relation.group("owned_action")):
        return subjects
    if relation:
        label = relation[1].removesuffix("的")
        if label and not label.startswith("们") and not re.search(r"现在|以前|过去|之前|今天|那[只个台本箱]|自己|喜欢|希望|想|哪|什么|多少|告诉|用|买|租|种|养|修|做|写|选|[0-9]", label) and not re.fullmatch(r"常|经常|正在|刚|刚刚|曾经|已经|一直", label):
            return ("relation:" + label,)
    if specific_subject:
        return subjects
    if re.search(r"我们|咱们", query):
        return ()
    if re.search(r"(?:我|用户)", query) and not re.search(r"我们|咱们", query):
        return ("user:self",)
    if _task_demand(query):
        # A service or operation before 的 is the task's object, not a person.
        # Explicit owners/relationships above remain available as constraints.
        return ()
    named = re.match(r"^(?:那)?([\u4e00-\u9fffA-Za-z·]{2,12})的(?=.{2})", query)
    if named and named[1] not in {"自己", "用户", "我的", "以前", "过去", "现在", "当时", "今年", "去年", "今天", "昨天", "明天", "目前"} and not re.search(r"^[那这哪个台本只]|[上下中里外]$", named[1]):
        return (named[1],)
    return subjects


def _task_demand(query: str) -> bool:
    # 当前执行状态中的“怎么样”不等于询问过去的操作方法。
    if (_LIVE.search(query) and re.search(r"现在|目前|当前|正在|最新", query)
            and not _PAST_EXECUTION.search(query)):
        return False
    if _TASK.search(query) and re.search(r"上次|上回|上月|之前|以前|过去|历史|为什么|怎么|如何|原因|经验|失败|踩坑|报错|计划|需要|后来.*成功", query):
        return True
    return bool(_PAST_EXECUTION.search(query) and _PROCEDURE.search(query)
                and (_VERSION.search(query) or re.search(r"设备|软件|应用|程序|文件|手机|平板|电脑|操作|步骤|配对|连接|排序|条件|前提", query)))


def _live_demand(query: str) -> bool:
    current = re.search(r"今天|今晚|现在|目前|当前|正在|最新|已经|了吗|了没|恢复了吗", query)
    # 完成、进展和状态本身没有执行者身份；个人记录仍交给记忆证据判断。
    external_state = re.search(r"营业|关门|开门|闭馆|开到|开放|发布|更新|修好|恢复|同步服务|出窑|出炉|运行|连接.*了吗", query)
    # A stated current precondition is not a request to re-read live state.
    return bool(current and external_state and _QUESTION.search(query)
                and not (_PAST_EXECUTION.search(query) and _PROCEDURE.search(query)))


def _recent_user_text(history: Sequence[object], query: str) -> tuple[str, ...]:
    result = []
    for row in tuple(history)[-8:]:
        role = row.get("role") if isinstance(row, Mapping) else getattr(row, "role", "")
        text = row.get("text", row.get("content", "")) if isinstance(row, Mapping) else getattr(row, "text", "")
        if role == "user" and isinstance(text, str) and text != query:
            result.append(text[:600])
    return tuple(result[-4:])


def _calendar_number(text: str) -> int:
    digits = {char: number for number, char in enumerate("零一二三四五六七八九")}
    digits.update({"〇": 0, "两": 2})
    if text.isascii() and text.isdigit():
        return int(text)
    if all(char in digits for char in text):
        return int("".join(str(digits[char]) for char in text))
    total, current, previous_unit = 0, 0, 10000
    for char in text:
        if char in digits:
            if current:
                raise ValueError("invalid calendar numeral")
            current = digits[char]
        elif char in {"十", "百", "千"}:
            unit = {"十": 10, "百": 100, "千": 1000}[char]
            if unit >= previous_unit:
                raise ValueError("invalid calendar numeral unit order")
            total += (current or 1) * unit
            current, previous_unit = 0, unit
        else:
            raise ValueError("invalid calendar numeral")
    return total + current


def _temporal(query: str, *, now: int | None = None, calendar_zone=timezone.utc) -> tuple[str, int | None, int | None]:
    # 仅转换年月日的位置，原问题及人物、活动等实体保持不变。
    try:
        query = re.sub(r"([0-9零〇一二三四五六七八九十百千两]+)(?=[年月])",
                       lambda match: str(_calendar_number(match[0])), query)
        query = re.sub(r"(月(?:份)?)([0-9零〇一二三四五六七八九十百千两]+)(?=[日号])",
                       lambda match: match[1] + str(_calendar_number(match[2])), query)
    except ValueError:
        return "unresolved", None, None
    if re.search(r"农历|阴历|\d+月(?:初|廿|[上中下]旬|[某几A-Za-z?？]{1,3}[日号])", query):
        return "unresolved", None, None
    explicit_year = re.search(r"(\d+)年(?=\d+月)", query)
    if explicit_year and len(explicit_year[1]) != 4:
        return "unresolved", None, None
    date = re.search(r"(?<!\d)(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})(?:日|号)?", query)
    if date:
        try:
            start = datetime(*(int(x) for x in date.groups()), tzinfo=calendar_zone)
            # 日历日可能跨夏令时切换；先增加本地日期，再换算时间戳。
            end = start + timedelta(days=1)
            return "as_of", int(start.timestamp()), int(end.timestamp())
        except ValueError:
            return "unresolved", None, None
    month_day = re.search(r"(?:(\d{4})年|(今年|去年|明年))?(\d{1,2})月(?:份)?(?:(\d{1,2})[日号])?", query)
    relative_month = re.search(r"上个月|上月|这个月|本月", query)
    if month_day or relative_month:
        if month_day and month_day[1]:
            year = int(month_day[1])
        elif now is not None:
            year = datetime.fromtimestamp(now, calendar_zone).year
            if month_day and month_day[2]:
                year += {"今年": 0, "去年": -1, "明年": 1}[month_day[2]]
        else:
            return "unresolved", None, None
        try:
            if month_day:
                month = int(month_day[3])
                day = int(month_day[4]) if month_day[4] else 1
            else:
                anchor = datetime.fromtimestamp(now, calendar_zone)
                month = anchor.month - int(relative_month[0] in {"上个月", "上月"})
                if month == 0:
                    year, month = year - 1, 12
                day = 1
            start = datetime(year, month, day, tzinfo=calendar_zone)
            end = (start + timedelta(days=1) if month_day and month_day[4] else
                   datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=calendar_zone))
            return "as_of", int(start.timestamp()), int(end.timestamp())
        except (ValueError, OverflowError):
            return "unresolved", None, None
    if re.search(r"\d{4}年|\d+月|今年|去年|前年|昨天|前天|上周|上星期|季度|"
                 r"[0-9零〇一二三四五六七八九十]+号(?:那天|那会|的时候)", query):
        return "unresolved", None, None
    if _HISTORY.search(query) and re.search(r"现在|目前|如今", query):
        return "timeline", None, None
    if _HISTORY.search(query):
        return "history", None, None
    if re.search(r"计划|打算|准备|将来|明天|下周|未来", query):
        return "planned", None, None
    return "current", None, None


def _fact_constraints(query: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    pet = re.search(r"(?:我(?:的|家(?:的)?)?|用户的)(?:小)?(猫|狗|兔子|鹦鹉|仓鼠|宠物).{0,6}(?:叫|名字|称呼)", query)
    if pet:
        return ("user:self",), ("宠物称呼:" + pet[1], "宠物:" + pet[1], "pet", "宠物")
    # Relationship labels are captured from syntax, never a profession list.
    rel = re.search(r"(?:我|用户)(?:的)?([\u4e00-\u9fffA-Za-z]{1,16}?)(?:的)?"
                    r"(?=叫什么|叫啥|名字|姓名|住在哪|住哪|住在什么|的职业|职业|做什么工作|工作是|是做什么|做哪[一]?行)", query)
    if rel and rel[1].strip("的") and rel[1].strip("的") not in _SELF_WORDS and not re.search(r"喜欢|现在|以前|记得|希望|自己|什么|叫|哪", rel[1]):
        label = rel[1].removesuffix("的")
        label = re.sub(r"^(?:学)?(.+?)的(老师|教练)$", r"\1\2", label)
        for pattern, field in _RELATION_FIELDS:
            if re.search(pattern, query[rel.start():]):
                return ("relation:" + label,), (field,)
    # Exact requested attributes take precedence over broad preference/entity
    # matches; a price, serial number or birthday is a different field.
    exact = ((r"手机号|电话号码|联系电话|手机号码", ("phone", "手机号", "电话")),
             (r"生日|出生日期", ("birthday", "生日", "出生日期")),
             (r"序列号", ("serial_number", "序列号")),
             (r"花了多少|多少钱|价格|费用", ("price", "purchase_price", "价格")),
             (r"哪天买|什么时候买|购买日期", ("purchase_date", "购买日期")),
             (r"到期|有效期", ("expires_at", "到期日", "有效期")),
             (r"型号|品牌", ("device", "device_model", "device_brand", "设备")),
             (r"宠物|养的", ("pet", "宠物")),
             (r"夜间.*提醒|提醒.*要求|打扰|保持安静", ("boundary", "互动边界")),
             (r"怎么.*开玩笑|吐槽|夸我|交互.*风格", ("style_preference", "互动偏好")),
             (r"习惯|通常|早餐|起床", ("habit", "习惯", "个人偏好", "preference:个人偏好:like")))
    for pattern, fields in exact:
        if re.search(pattern, query):
            owner = re.match(r"([\u4e00-\u9fffA-Za-z·]{2,12})的(?:联系|电话|生日|出生)", query)
            if owner and not owner[1].startswith(("我", "用户")):
                return (owner[1],), fields
            return ("user:self",), fields
    if re.search(r"街道|门牌|详细地址|具体地址", query):
        return ("user:self",), ("street_address", "街道地址", "详细地址")
    alias = re.search(r"([\u4e00-\u9fffA-Za-z·]{2,16})的(?:职业|工作|住址|居住地|名字|姓名)", query)
    if alias and alias[1] not in {"自己", "用户", "我的", "我自己"} and not re.search(r"我|用户", alias[1]):
        field = next((value for pattern, value in _RELATION_FIELDS if re.search(pattern, query[alias.start():])), "")
        if field:
            return (alias[1],), (field,)
    alias = re.match(r"(?:那)?([\u4e00-\u9fffA-Za-z·]{2,12}?)(?:做什么工作|住在哪里|住在哪|住哪里|叫什么)", query)
    if alias and not re.search(r"[我你他她它]|用户", alias[1]):
        field = next((value for pattern, value in _RELATION_FIELDS if re.search(pattern, query)), "")
        if field:
            return (alias[1],), (field,)
    if re.search(r"住(?:在)?哪|居住|住址|住处|搬到|居所|home|live in", query, re.I):
        return ("user:self",), ("居住地", "residence")
    if re.search(r"(?:我的?|我自己的?|用户的)(?:名字|姓名)|我叫(?:什么|啥)|who am i", query, re.I):
        return ("user:self",), ("姓名", "name")
    if re.search(r"(?:叫|称呼)我|我(?:的|喜欢的?|希望的?)?(?:什么)?(?:昵称|称呼)", query):
        return ("user:self",), ("称呼", "nickname")
    if re.search(r"我.{0,4}(?:职业|做什么工作|从事什么|做哪[一]?行)|我的工作|occupation", query, re.I):
        return ("user:self",), ("职业", "occupation")
    if re.search(r"(?:不能|不应|不要|别).*(?:当成|等同).*过敏", query):
        return ("user:self",), ("preference:个人偏好:avoid", "avoid", "长期忌口")
    if "过敏" in query:
        return ("user:self",), ("过敏", "allergy")
    if re.search(r"忌口|避开.*食材|不能吃|不想加|不要加|别放|忌讳.*吃", query):
        return ("user:self",), ("过敏", "长期忌口", "preference:个人偏好:avoid", "avoid")
    if re.search(r"喝|饮[料品]|drink|beverage", query, re.I):
        return ("user:self",), ("饮料偏好", "preference:饮料偏好:like", "preference:饮料偏好:avoid")
    if re.search(r"喜欢|兴趣|爱好|偏好|最爱|讨厌|不喜欢|like|hobb", query, re.I):
        if re.search(r"不喜欢|讨厌", query):
            return ("user:self",), ("preference:个人偏好:avoid", "preference:饮料偏好:avoid", "avoid")
        return ("user:self",), ("个人偏好", "preference:个人偏好:like", "preference:饮料偏好:like", "饮料偏好")
    if re.search(r"每周|星期|周几|哪天|每星期", query):
        return ("user:self",), ("每周安排",)
    if re.search(r"计划|打算|准备.{0,8}(?:做|去)", query):
        return ("user:self",), ("plan",)
    return (), ()


def _details(query: str, route: str) -> tuple[str, ...]:
    if route not in {"episode", "task"}:
        return ()
    tests = ((r"为什么|根因|原因", "cause"), (r"什么颜色|哪种颜色", "color"),
             (r"几[个次天本盆杯辆只件页张台]|多少|多久|多长时间|多长", "quantity"), (r"哪家店|在哪里|哪儿|什么地方", "location"),
             (r"第三个人|还有谁|另一个人|那个人叫什么", "participant"),
             (r"哪本书|什么电影|哪部电影|叫什么名字", "title"),
             (r"怎么解决|如何解决|怎样修好|怎么修好|如何.*导出|哪个选项|后来.*成功|怎么成功", "procedure"))
    details = tuple(name for pattern, name in tests if re.search(pattern, query))
    if route == "task" and "失败后" in query and "procedure" in details:
        details = ("cause", *details)
    return details


def _task_app(query: str) -> str:
    match = re.search(r"([\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9_.-]{0,20}?(?:工具|服务|应用|软件))", query)
    if not match:
        return ""
    return re.sub(r"^(?:(?:上次|之前|我们|我的?|部署|发布|安装|运行|启动|用|的))+", "", match[1])


def _open_field_heading(query: str) -> bool:
    return bool(_OPEN_FIELD_HEADING.fullmatch(query) and not re.search(
        r"^(?:什么是|何谓|如何|怎么|怎样|帮我|请|回想|回忆)|时候|时", query))


def _is_chat(query: str, *, has_calendar_query: bool = False) -> bool:
    if _CASUAL.fullmatch(query) or _NO_RECALL.search(query):
        return True
    if _FIELD_HEADING.fullmatch(query) or _open_field_heading(query):
        return False
    if _CREATIVE.search(query):
        return True
    if re.search(r"还记得|回忆|我们.*(?:上次|当时|第一次|一起)|我.*(?:偏好|喜欢|习惯)|按我的", query):
        return False
    if _task_demand(query) or _live_demand(query) or (_LIVE.search(query) and (_TASK.search(query) or "任务" in query or any(key in query.casefold() for key in _AUTHORITIES))):
        return False
    subjects, predicates = _fact_constraints(query)
    subjects = _literal_subject(query, subjects, predicates)
    if subjects and subjects != ("user:self",):
        return False
    # 时间已由统一解析器识别；不能再用数字写法决定中文日期是否值得检索。
    if has_calendar_query and _QUESTION.search(query):
        return False
    if re.search(r"^(?:嗨|[你您]好|早上好|晚上好|晚安|谢谢)|陪.*(?:发呆|发会儿呆|待一会|安静|聊聊)|安静.*(?:陪|待)|(?:累|天气|放松|无聊|休息)", query) and not _QUESTION.search(query):
        return True
    if not re.search(r"[我他她它]|用户|之前|上次|那[次个段台只本]|记得|回顾|relay|codex|claude|agent", query, re.I):
        # General knowledge, arithmetic and creation need no personal archive.
        if _QUESTION.search(query) or len(query) > 5:
            return True
    return False


class MemoryRetrievalRouter:
    def __init__(self, budget: RetrievalBudget | None = None, *, time_basis: str = "unix",
                 timezone_name: str = "UTC"):
        if time_basis not in {"logical", "unix"}:
            raise ValueError("time_basis must be 'logical' or 'unix'")
        self.budget = budget or RetrievalBudget()
        self.time_basis = time_basis
        self.calendar_zone = ZoneInfo(timezone_name or "UTC")

    def plan(self, query: str, *, history: Sequence[object] = (), scope: str = "companion",
             now: int | None = None) -> RetrievalPlan:
        text = str(query).strip()[:1200]
        if (not text or _CASUAL.fullmatch(text) or _NO_RECALL.search(text)
                or re.search(r"^(?:假如|假设|如果我们)", text)
                or (re.search(r"^(?:嗨|[你您]好|早上好|晚上好|晚安|谢谢)", text) and not _QUESTION.search(text))):
            return RetrievalPlan((RetrievalIntent("chat", text, scopes=(scope,), reason="no_evidence_demand"),))
        parts = [s.strip(" ，,。！？!?；; ") for s in re.split(r"[；;\n]|[，,。！？!?](?=.{2})|、(?=叫|住|做|姓)|另外|顺便|以及|并且|同时", text) if s.strip()]
        parts = parts or [text]
        if (len(parts) >= 2 and _task_demand(text)
                and all(not _QUESTION.search(part) and not _CREATIVE.search(part) for part in parts[:-1])):
            # Declared device/version/precondition clauses belong to the task
            # question. They are not separate requests to search the archive.
            parts = [text.strip("。！？!?")]
        if len(parts) >= 2:
            time_mode, _, _ = _temporal(parts[0], now=now, calendar_zone=self.calendar_zone)
            if (re.search(r"(?:时|时候|的话|方面|的话题)$", parts[0])
                    or (time_mode in {"as_of", "unresolved"} and not _QUESTION.search(parts[0]))
                    or (_task_demand(parts[1]) and not _QUESTION.search(parts[0]) and not _CREATIVE.search(parts[0]))
                    or (_EPISODE.search(text) and not _QUESTION.search(parts[0]) and not _CREATIVE.search(parts[0]))):
                parts = [parts[0] + "，" + parts[1], *parts[2:]]
        personal_request = bool(re.search(r"我|用户|记得|回忆", text))
        intents = [self._one(part, scope, implicit_fact=personal_request and len(parts) > 1, now=now)
                   for part in parts[:self.budget.max_intents]]
        for index in range(1, len(intents)):
            previous, intent = intents[index - 1], intents[index]
            if previous.route in {"episode", "task"} and intent.route in {"chat", "bounded"} and _details(intent.query, previous.route):
                intents[index] = replace(previous, query=previous.query + "，" + intent.query,
                    detail=bool(_DETAIL.search(intent.query)), reason="same_turn_evidence_continuation")
            elif (previous.route == "fact" and previous.subjects and intent.route in {"chat", "bounded", "fact"}
                  and not re.search(r"我|你|[他她它]|用户|的", intent.query)):
                field = next((value for pattern, value in _RELATION_FIELDS if re.search(pattern, intent.query)), "")
                if field:
                    intents[index] = replace(intent, route="fact", subjects=previous.subjects,
                                             predicates=(field,), reason="same_turn_subject_continuation")
        if len(intents) == 1 and intents[0].route == "fact" and "设备" in intents[0].predicates and re.search(r"和.*喜欢|喜欢.*和", text):
            preference = re.split(r"和|以及", text)[-1]
            intents.append(RetrievalIntent("fact", "我" + preference, subjects=("user:self",),
                predicates=("个人偏好", "preference:个人偏好:like", "like"), reason="additional_explicit_attribute"))
        intents = [replace(i, details=_details(i.query, i.route)) for i in intents]
        # Keep every intent for diagnostics. The executor skips chat intents;
        # dropping them here concealed mixed requests and distorted routing QA.
        inherited = False
        # Time ambiguity belongs to the affected intent. It must not suppress
        # unrelated current facts in a mixed request through reference handling.
        unresolved = False
        if _REFERENCE.search(text):
            previous = None
            for old in reversed(_recent_user_text(history, text)):
                earlier = self.plan(old, scope=scope, now=now)
                useful = [i for i in earlier.intents if i.route in {"fact", "episode", "task"}]
                named_mention = _NAMED_USER_MENTION.search(old)
                if named_mention:
                    # This is only a literal candidate supplied by the user.
                    # The retrieval service must still prove it against a
                    # current source-backed alias; assistant text is ignored.
                    previous = RetrievalIntent("fact", old, subjects=(named_mention[1],),
                                               predicates=("unresolved_field",),
                                               reason="unverified_user_reference")
                    break
                mention = re.search(r"我的([\u4e00-\u9fff]{1,12}?)(?=最近|刚才|昨天|今天|联系|告诉|说|发来|[。！! ]|$)", old)
                if mention and (not useful or all(i.reason == "personal_attribute_not_resolved" for i in useful)):
                    previous = RetrievalIntent("fact", old, subjects=("relation:" + mention[1],))
                    break
                if len(useful) == 1:
                    previous = useful[0]
                    break
                if len(useful) > 1:
                    break
            if previous is not None:
                updated = []
                for intent in intents:
                    if re.match(r"^那?我的?(?:呢|[?？]|$)", intent.query):
                        combined = previous.query
                        for subject in previous.subjects:
                            label = subject.removeprefix("relation:")
                            if label != "user:self":
                                combined = combined.replace(label, "", 1) if "我" + label in combined else combined.replace(label, "我", 1)
                        updated.append(replace(previous, query=combined, subjects=("user:self",),
                                               reason="bounded_user_reference_self_switch"))
                    elif re.match(r"^那?[他她它]", intent.query):
                        predicate = next((field for pattern, field in _RELATION_FIELDS
                                          if re.search(pattern, intent.query)), "")
                        inherited_pet = predicate == "name" and any(p.startswith("宠物称呼:") for p in previous.predicates)
                        own_fields = intent.predicates if intent.predicates and intent.predicates != ("unresolved_field",) else ()
                        fields = previous.predicates if inherited_pet else ((predicate,) if predicate else own_fields or intent.predicates or previous.predicates)
                        updated.append(replace(intent, route="fact", subjects=previous.subjects,
                                               predicates=fields,
                                               reason="bounded_user_reference"))
                    elif intent.route == "bounded" or re.search(r"那次|那段|详细|展开|后来|然后", intent.query):
                        combined = previous.query + " " + intent.query
                        updated.append(replace(previous, query=combined,
                                               detail=bool(_DETAIL.search(intent.query)), details=_details(combined, previous.route),
                                               reason="bounded_user_reference"))
                    else:
                        updated.append(intent)
                if re.search(r"现在|目前|如今|当前|当下|现阶段", text):
                    # 当前问题明确切回现在时，仅承接主体/话题，不继承前轮日期。
                    updated = [replace(item, temporal_mode="current", as_of=None, as_of_end=None)
                               if original.temporal_mode == "current" else item
                               for original, item in zip(intents, updated)]
                intents, inherited = updated, True
            elif re.search(r"^那?[他她它]|^那我的呢|^那次|^那段|^详细|^展开|^后来呢|^然后呢", text):
                unresolved = True
        return RetrievalPlan(tuple(intents), inherited_context=inherited, unresolved_reference=unresolved)

    def _one(self, query: str, scope: str, implicit_fact: bool = False,
             now: int | None = None) -> RetrievalIntent:
        temporal, as_of, as_of_end = _temporal(query, now=now, calendar_zone=self.calendar_zone)
        if self.time_basis == "logical" and temporal == "as_of":
            # Desktop saves historically use an accumulated logical clock.
            # A calendar date cannot be compared to it or silently migrated.
            temporal, as_of, as_of_end = "unresolved", None, None
        # 询问预约内容与询问实际参加结果使用不同证据，日历合法性仍先检查。
        if (temporal not in {"unresolved", "history", "timeline"} and re.search(r"预约|计划|安排", query)
                and re.search(r"是什么|哪|时间|日期|内容|项目|状态", query)
                and not re.search(r"已经|后来|实际|最终|曾经|参加过|完成", query)):
            temporal = "planned"
        detail = bool(_DETAIL.search(query))
        base = {"query": query, "scopes": (scope,), "temporal_mode": temporal,
                "as_of": as_of, "as_of_end": as_of_end, "detail": detail}
        subjects, predicates = _fact_constraints(query)
        subjects = _literal_subject(query, subjects, predicates)
        # 省略所有者的字段标题只提出字面字段需求，不把前面的物品当成人名。
        # 开放字段仍须由原始卡片证明，通识定义问句不匹配标题语法。
        if _open_field_heading(query) and not _FIELD_HEADING.fullmatch(query):
            owner = ("user:self",) if re.match(r"^(?:我的?|用户|my )", query, re.I) else ()
            return RetrievalIntent("fact", **base, subjects=owner,
                                   predicates=("unresolved_field",), reason="literal_field_heading")
        if _is_chat(query, has_calendar_query=as_of is not None or temporal == "unresolved") and not (implicit_fact and predicates):
            return RetrievalIntent("chat", **base, reason="no_evidence_demand")
        authority = next((value for key, value in _AUTHORITIES.items() if key in query.casefold()), "")
        if ((_LIVE.search(query) and (authority or _TASK.search(query) or "任务" in query))
                or _live_demand(query)) and not _task_demand(query):
            return RetrievalIntent("live", **base, authority=authority or "executor", reason="external_authority_required")
        if _task_demand(query):
            app = re.search(r"(?:应用|软件|app)\s*[:：]?\s*([A-Za-z][\w.-]*)", query, re.I)
            version = _VERSION.search(query)
            return RetrievalIntent("task", **{**base, "scopes": ("task_experience",), "temporal_mode": temporal if temporal in {"planned", "as_of", "unresolved"} else "current"},
                                   subjects=subjects,
                                   app=app[1] if app else _task_app(query), version=version[1] if version else "",
                                   reason="past_execution_evidence")
        if predicates and re.search(r"我那台|我的|我自己的|^我(?:现在|以前)", query) and not re.search(r"我们|咱们|一起|共同", query):
            return RetrievalIntent("fact", **base, subjects=subjects, predicates=predicates,
                                   reason="explicit_subject_field")
        if subjects and _QUESTION.search(query) and not _EPISODE.search(query):
            return RetrievalIntent("fact", **base, subjects=subjects, predicates=predicates or ("unresolved_field",),
                                   reason="explicit_subject_field" if predicates else "personal_attribute_not_resolved")
        if _EPISODE.search(query) and (_QUESTION.search(query) or re.search(r"第一次|回顾", query)):
            return RetrievalIntent("episode", **{**base, "temporal_mode": temporal if temporal in {"planned", "as_of", "unresolved"} else "current"},
                                   subjects=subjects,
                                   requires_shared_event=bool(re.search(r"我们|咱们|一起|共同", query)),
                                   reason="episode_evidence")
        if predicates and (_QUESTION.search(query) or re.search(r"我|用户|计划|打算", query) or _FIELD_HEADING.fullmatch(query)):
            return RetrievalIntent("fact", **base, subjects=subjects, predicates=predicates,
                                   reason="explicit_subject_field")
        if re.search(r"我的?|用户|^[他她它]", query) and _QUESTION.search(query):
            return RetrievalIntent("fact", **base, subjects=subjects, predicates=("unresolved_field",),
                                   reason="personal_attribute_not_resolved")
        return RetrievalIntent("bounded", **base, subjects=subjects, reason="ambiguous_bounded_retrieval")
