"""L2 pipeline 共享常量（中性叶子模块，不 import 任何项目模块）。

把 _VALID_DIFF_TYPES 抽到这里，是为了让 tools/script.py 与 l2_take.py 同源取值
而无需互相 import：否则 tools/script.py 要 import l2_take 才能拿 enum，便会与
config→tools、l2_take→config 形成环。两个消费方都只单向依赖本模块，无环。
"""

# diff_type 合法枚举值集合。
# tools/script.py 和 l2_take.py 均从此处导入，保证同源（spec §4.1）。
_VALID_DIFF_TYPES: frozenset[str] = frozenset({"match", "missing", "substitution", "insertion"})
