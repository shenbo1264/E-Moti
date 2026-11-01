from dataclasses import dataclass
import re


RELATION_DOMAINS = {"relation_name": "人物姓名", "relation_residence": "人物居住地",
                    "relation_occupation": "人物职业"}
_FIELDS = {
    "name": (r"(?:的)?(?:名字(?:是|叫)|姓名是|名叫|叫)(?:做)?", "叫", ("名字", "姓名", "称呼")),
    "residence": (r"(?:现在)?住在", "住在", ("居住地", "住址", "住处", "地址")),
    "occupation": (r"(?:的)?(?:职业是|工作是)|从事", "的职业是", ("职业", "工作")),
}
_SELF_FIELDS = {"姓名", "名字", "称呼", "昵称", "常用称呼", "职业", "工作", "地址", "住址", "住处", "居住地", "常住地址"}
CORRECTION_PREFIX = re.compile(
    r"^(?:(?:(?:刚才|之前)?我?|我(?:刚才|之前)?)(?:把[^，。！？!?]{1,20})?"
    r"(?:说错|写错|记错)(?:了|[^，。！？!?]{1,20}了)|更正一下|纠正一下)[，,:： ]*")
REPORTED_RELATION = re.compile(r"我(?:的)?[^的，。；!?？！]{1,16}?(?:说|告诉|提到|认为|觉得)(?!错)")
_UNSAFE = re.compile(r"假如|假设|如果|可能|也许|不确定|不是|不叫|今天|明天|此刻|暂时|最近|"
                     r"打算|准备|计划|才怪|原话|举例|假话|的话|反话|仅仅|这句话|吗|呢|什么|"
                     r"[？?‘’“”\"「」]|或者|还是|但是|因为|所以|说[我他她]|告诉[我他她]")


@dataclass(frozen=True, slots=True)
class GroundedFact:
    relation: str
    predicate: str
    value: str

    @property
    def subject(self):
        return "relation:" + self.relation

    @property
    def slot(self):
        return self.subject + ":" + self.predicate

    @property
    def domain(self):
        return RELATION_DOMAINS["relation_" + self.predicate]

    @property
    def summary(self):
        return "用户的" + self.relation + _FIELDS[self.predicate][1] + self.value

    @property
    def metadata(self):
        return {"fact_subject": self.subject, "fact_predicate": self.predicate}


def _relation_match(text: str, verb: str):
    match = re.fullmatch(r"(?:我|用户)的(?P<relation>[\u4e00-\u9fff]{1,16}?)(?:" + verb
                         + r")(?P<value>[\u4e00-\u9fffA-Za-z· ]{1,30})", text)
    if match is None:
        return None
    relation = match["relation"]
    if relation in {"我", "他", "她", "它", *_SELF_FIELDS} or any(word in relation for word in ("的", "叫", "住在", "和", "或", "今天", "暂时")):
        return None
    # 宠物继续使用已有种类和称呼生命周期，避免同一事实出现两个存储槽。
    if relation in {"猫", "狗", "兔子", "鹦鹉", "仓鼠", "宠物"}:
        return None
    return match


def has_relation_copula(text: str) -> bool:
    # 仅识别关系主语形状，不给“是”后面的描述指定职业或其他语义字段。
    text = CORRECTION_PREFIX.sub("", text.strip()).rstrip("。！! ")
    return _relation_match(text, "是") is not None


def relation_fact(text: str, *, predicate_hint: str = "") -> GroundedFact | None:
    # 关系标签和属性值均来自完整原话；不依赖职业名单，也不推断代词指向。
    text = CORRECTION_PREFIX.sub("", text.strip()).rstrip("。！! ")
    if _UNSAFE.search(text) or REPORTED_RELATION.search(text):
        return None
    for predicate, (verb, _, _) in _FIELDS.items():
        # “是”本身不提供字段语义；只接受抽取器已明确分类的职业候选。
        if predicate == "occupation" and predicate_hint == predicate:
            verb = "(?:" + verb + ")|是"
        match = _relation_match(text, verb)
        if match:
            relation, value = match["relation"], match["value"].strip()
            return GroundedFact(relation, predicate, value)
    return None


def relation_forget_match(target: str, fact: GroundedFact) -> bool:
    target = re.sub(r"^(?:我的|用户的)", "", target)
    if target == fact.relation:
        return True
    return target in {fact.relation + join + alias for join in ("", "的")
                      for alias in _FIELDS[fact.predicate][2]}


def has_relation_forget_scope(target: str) -> bool:
    return any(re.fullmatch(r".+?(?:的)?" + re.escape(alias), target)
               for _, _, aliases in _FIELDS.values() for alias in aliases)
