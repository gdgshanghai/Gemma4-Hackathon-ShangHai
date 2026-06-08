#!/usr/bin/env python3
"""Extract and validate core financial statements from converted Markdown."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
import os
import re
import urllib.error
import urllib.request


FINANCIAL_DATA_SCHEMA_VERSION = 13
FINANCIAL_CHECKS_SCHEMA_VERSION = 12
LLM_TABLE_JUDGE_PROMPT_VERSION = "financial_table_judge_v2"
FINANCIAL_RULE_VERSION = "financial_rules_v14"
FINANCIAL_LLM_PRESETS = {
    "gemma4": {
        "api_base": "http://127.0.0.1:8006/v1",
        "model": "Gemma-4-26B-A4B-it-NVFP4",
    },
    "qwen3.6": {
        "api_base": "http://127.0.0.1:8004/v1",
        "model": "Qwen3.6-35B-A3B-FP8",
    },
}

_CORE_STATEMENT_TYPES = {"balance_sheet", "income_statement", "cash_flow_statement"}

_FINANCIAL_INDUSTRY_PROFILES = {"bank", "securities", "insurance"}

_STATEMENT_TITLE_ALIASES = {
    "balance_sheet": ("资产负债表", "财务状况表"),
    "income_statement": ("利润表", "损益表", "综合收益表", "利润及其他综合收益表", "损益及其他综合收益表"),
    "cash_flow_statement": ("现金流量表",),
}

_CORE_STATEMENT_TITLE_TERMS = tuple(
    alias
    for aliases in _STATEMENT_TITLE_ALIASES.values()
    for alias in aliases
)

_KEY_METRIC_CANONICALS = {
    "operating_revenue",
    "operating_profit",
    "net_profit",
    "total_profit",
    "parent_net_profit",
    "deducted_parent_net_profit",
    "operating_cash_flow_net",
    "other_comprehensive_income",
    "total_assets",
    "total_liabilities",
    "equity_attributable_parent",
    "total_equity",
    "basic_eps",
    "diluted_eps",
    "deducted_basic_eps",
    "weighted_avg_roe",
    "deducted_weighted_avg_roe",
    "parent_nav_per_share",
    "ending_share_capital",
}


class _TableHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "tr":
            self._row = []
            return
        if tag not in {"td", "th"} or self._row is None:
            return
        attr_map = {name.lower(): value for name, value in attrs}
        self._cell = {
            "parts": [],
            "rowspan": _safe_int(attr_map.get("rowspan"), 1),
            "colspan": _safe_int(attr_map.get("colspan"), 1),
        }

    def handle_data(self, data):
        if self._cell is not None:
            self._cell["parts"].append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"td", "th"} and self._row is not None and self._cell is not None:
            text = _clean_cell_text("".join(self._cell["parts"]))
            self._row.append(
                {
                    "text": text,
                    "rowspan": max(1, self._cell["rowspan"]),
                    "colspan": max(1, self._cell["colspan"]),
                }
            )
            self._cell = None
            return
        if tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None


def _now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_int(value, default):
    try:
        parsed = int(str(value or "").strip())
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _clean_cell_text(text):
    text = unescape(str(text or "")).replace("\xa0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_html_table(table_html):
    parser = _TableHTMLParser()
    parser.feed(table_html or "")
    return _expand_spans(parser.rows)


def _expand_spans(raw_rows):
    rows = []
    pending = {}
    max_width = 0

    for raw_row in raw_rows:
        row = []
        col = 0
        next_pending = {}

        def fill_pending_cells():
            nonlocal col
            while col in pending:
                text, remaining = pending[col]
                row.append(text)
                if remaining > 1:
                    next_pending[col] = (text, remaining - 1)
                col += 1

        for cell in raw_row:
            fill_pending_cells()
            text = cell["text"]
            colspan = max(1, int(cell.get("colspan") or 1))
            rowspan = max(1, int(cell.get("rowspan") or 1))
            for offset in range(colspan):
                row.append(text)
                if rowspan > 1:
                    next_pending[col + offset] = (text, rowspan - 1)
            col += colspan

        while True:
            later_cols = [idx for idx in pending if idx >= col]
            if not later_cols:
                break
            target = min(later_cols)
            while col < target:
                row.append("")
                col += 1
            fill_pending_cells()

        pending = next_pending
        max_width = max(max_width, len(row))
        rows.append(row)

    if max_width:
        rows = [row + [""] * (max_width - len(row)) for row in rows]
    return rows


def _strip_html(html):
    text = re.sub(r"<[^>]+>", " ", html or "")
    return _clean_cell_text(text)


def _report_identity_text(markdown, filename=None):
    parts = [str(filename or "")]
    for line in str(markdown or "").splitlines()[:80]:
        if "<table" in line.lower():
            break
        cleaned = _strip_html(re.sub(r"^#+\s*", "", line)).strip()
        if not cleaned:
            continue
        compact = _compact_key(cleaned)
        if compact in {"目录", "释义", "重要提示目录和释义"}:
            break
        if len(cleaned) <= 120:
            parts.append(cleaned)
        if len(parts) >= 16:
            break
    return "\n".join(parts)


def _detect_report_year(markdown, filename=None):
    markdown = str(markdown or "")
    title_text = _report_identity_text(markdown, filename=filename)
    compact_title_text = _compact_key(title_text)
    for pattern in (
        r"(20\d{2})年(?:年度报告|年报|半年度报告|半年报|中报|季度报告|第?[一二三四1234]季度报告|[一二三四1234]季报|报告摘要)",
        r"(20\d{2})(?:年度报告|年报|半年度报告|半年报|中报|季度报告|第?[一二三四1234]季度报告|[一二三四1234]季报|报告摘要|Q[1-4])",
    ):
        match = re.search(pattern, compact_title_text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    for pattern in (
        r"(20\d{2})\s*年\s*(?:年度报告|年报|半年度报告|季度报告|报告摘要)",
        r"(20\d{2})(?:年度报告|年报|半年度报告|季度报告|报告摘要)",
    ):
        match = re.search(pattern, title_text)
        if match:
            return int(match.group(1))
    text = "\n".join([str(filename or ""), markdown[:120000]])
    for keyword in ("主要会计数据", "主要财务指标"):
        index = text.find(keyword)
        if index < 0:
            continue
        window = text[index : index + 5000]
        match = re.search(r"(20\d{2})\s*年", window)
        if match:
            return int(match.group(1))
    return None


def _detect_report_kind(markdown, filename=None):
    text = _report_identity_text(markdown, filename=filename)
    compact = _compact_key(text)
    compact_filename = _compact_key(filename or "")
    if "半年度报告摘要" in compact:
        return "interim_report_summary"
    if "年度报告摘要" in compact or "报告摘要" in compact:
        return "annual_report_summary"
    if _looks_like_quarterly_report_title(compact):
        return "quarterly_report"
    if any(term in compact for term in ("半年度报告", "半年报", "中期报告")) or "中报" in compact_filename:
        return "interim_report"
    return "annual_report"


def _looks_like_quarterly_report_title(compact):
    return bool(
        re.search(r"20\d{2}年?(?:第?[一二三四1234]季度报告|[一二三四1234]季报)", compact)
        or re.search(r"20\d{2}Q[1-4](?:报告|季报)?", compact, flags=re.IGNORECASE)
        or any(term in compact for term in ("第一季度报告", "第二季度报告", "第三季度报告", "第四季度报告"))
    )


def _detect_industry_profile(markdown, filename=None):
    text = "\n".join([str(filename or ""), str(markdown or "")[:50000]])
    compact = _compact_key(text)
    if any(term in compact for term in ("商业银行", "银行股份有限公司", "银行年度报告")) or (
        "利息净收入" in compact and "客户存款" in compact and "客户贷款" in compact
    ):
        return "bank"
    if any(term in compact for term in ("证券股份有限公司", "证券公司", "证券年度报告")) or (
        "手续费及佣金净收入" in compact and "客户资金存款" in compact
    ):
        return "securities"
    if any(term in compact for term in ("保险股份有限公司", "保险公司", "保险年度报告")) or (
        "保险业务收入" in compact and "赔付支出" in compact
    ):
        return "insurance"
    return "general"


def _table_context(markdown, start, end):
    before = markdown[max(0, start - 1800):start]
    after = markdown[end:min(len(markdown), end + 360)]
    lines = [line.strip() for line in before.splitlines() if line.strip()]
    heading = ""
    heading_keywords = _CORE_STATEMENT_TITLE_TERMS + ("所有者权益变动表", "股东权益变动表", "主要会计数据", "主要财务指标")
    for line in reversed(lines[-24:]):
        cleaned = re.sub(r"^#+\s*", "", line).strip()
        compact_cleaned = _compact_key(cleaned)
        if (
            any(keyword in cleaned or keyword in compact_cleaned for keyword in heading_keywords)
            and _looks_like_heading(cleaned)
        ):
            heading = cleaned
            break
    if not heading:
        for line in reversed(lines[-14:]):
            cleaned = re.sub(r"^#+\s*", "", line).strip()
            if _is_context_noise(cleaned):
                continue
            if len(cleaned) <= 70:
                heading = cleaned
                break

    unit_text = before[-1400:] + " " + after[:240]
    unit = ""
    unit_patterns = (
        r"单位(?:为)?[:：]\s*([^\s\n，,。；;）)]+)",
        r"金额单位(?:均)?为\s*([^\s\n，,。；;）)]+)",
        r"金额单位[:：]\s*([^\s\n，,。；;）)]+)",
    )
    unit_matches = []
    for pattern in unit_patterns:
        unit_matches.extend(re.finditer(pattern, unit_text))
    if unit_matches:
        unit = unit_matches[-1].group(1).strip()

    return {
        "heading": heading,
        "unit": unit,
        "near_text": _strip_html(before[-300:] + " " + after[:120])[:320],
        "near_before": _strip_html(before[-700:])[:700],
        "near_after": _strip_html(after[:240])[:240],
    }


def _is_context_noise(text):
    if not text:
        return True
    compact = _compact_key(text)
    if any(
        keyword in text or keyword in compact
        for keyword in ("资产负债表", "利润表", "现金流量表", "所有者权益变动表", "股东权益变动表", "主要会计数据", "主要财务指标")
    ):
        return False
    if re.search(r"单位[:：]|编制单位[:：]|主管会计|会计机构|法定代表人|公司负责人", text):
        return True
    if re.fullmatch(r"20\d{2}\s*年.*", text):
        return True
    if "后附财务报表附注" in text:
        return True
    return False


def _looks_like_heading(text):
    if not text or _is_context_noise(text):
        return False
    if "<table" in text.lower() or "</table" in text.lower():
        return False
    if len(text) > 90:
        return False
    if re.search(r"[。；;]", text):
        return False
    return True


def _iter_markdown_tables(markdown):
    for index, match in enumerate(
        re.finditer(r"<table\b.*?</table>", markdown or "", flags=re.IGNORECASE | re.DOTALL),
        start=1,
    ):
        yield {
            "table_index": index,
            "line": markdown.count("\n", 0, match.start()) + 1,
            "html": match.group(0),
            "context": _table_context(markdown, match.start(), match.end()),
        }


def _table_hash(table):
    payload = "\n".join(
        [
            str(table.get("table_index") or ""),
            str(table.get("line") or ""),
            table.get("html") or "",
            json.dumps(table.get("context") or {}, ensure_ascii=False, sort_keys=True),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()


def _table_preview(grid, max_rows=35, max_cols=8, max_chars=6000):
    lines = []
    for row in grid[:max_rows]:
        lines.append(" | ".join(str(cell or "") for cell in row[:max_cols]))
    preview = "\n".join(lines)
    return preview[:max_chars]


def _cache_token(text):
    token = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text or "unknown")).strip("._")
    return token or "unknown"


def _normalize_label(text):
    text = _clean_cell_text(text)
    text = re.sub(r"[（(][^()（）]*[）)]", "", text)
    text = re.sub(r"^[一二三四五六七八九十]+[、.．]", "", text)
    text = re.sub(r"^\d+(?:[.．、]|\s+)", "", text)
    text = re.sub(r"^(?:其中|加|减)[:：]", "", text)
    text = re.sub(r"[:：]$", "", text)
    text = text.replace("（", "(").replace("）", ")")
    return text.strip()


def _compact_key(text):
    text = _normalize_label(text)
    text = re.sub(r"\s+", "", text)
    text = text.replace("或", "")
    return re.sub(r"[，,、:：；;（）()\[\]【】“”\"'·]", "", text)


_CANONICAL_ALIASES = [
    (
        "total_liabilities_and_equity",
        (
            "负债和所有者权益总计",
            "负债和股东权益总计",
            "负债和所有者权益合计",
            "负债及所有者权益总计",
            "负债及股东权益总计",
        ),
    ),
    (
        "equity_attributable_parent",
        (
            "归属于母公司所有者权益合计",
            "归属于母公司股东权益合计",
            "归属于上市公司股东的净资产",
            "归属于母公司股东的权益",
            "归属于母公司股东权益",
            "归属于母公司所有者的权益",
            "归属于母公司股东权益小计",
            "归属于母公司所有者权益",
            "归属于上市公司股东的权益",
            "归属于本行股东权益合计",
            "归属于本行股东权益",
            "归属于本行股东的权益",
            "归属于本银行股东权益合计",
            "归属于本银行股东权益",
            "归属于本银行股东的权益",
            "归属于本公司股东权益合计",
            "归属于本公司股东权益",
            "归属于本公司股东的权益",
        ),
    ),
    ("total_assets", ("资产总计", "资产合计", "资产总额", "总资产")),
    ("current_assets", ("流动资产合计",)),
    ("non_current_assets", ("非流动资产合计",)),
    ("total_liabilities", ("负债合计", "负债总额", "总负债")),
    ("current_liabilities", ("流动负债合计",)),
    ("non_current_liabilities", ("非流动负债合计",)),
    ("minority_interests", ("少数股东权益",)),
    ("total_equity", ("所有者权益合计", "股东权益合计", "所有者权益总额", "股东权益总额")),
    ("total_operating_revenue", ("营业总收入",)),
    ("operating_revenue", ("营业收入",)),
    ("operating_profit", ("营业利润",)),
    ("non_operating_income", ("营业外收入",)),
    ("non_operating_expenses", ("营业外支出",)),
    ("total_profit", ("利润总额",)),
    ("income_tax_expense", ("所得税费用",)),
    (
        "parent_net_profit",
        (
            "归属于母公司股东的净利润",
            "归属于母公司所有者的净利润",
            "归属于上市公司股东的净利润",
            "归属于本行股东的净利润",
            "本行股东的净利润",
            "归属于银行股东的净利润",
            "银行股东的净利润",
            "归属于本银行股东的净利润",
            "本银行股东的净利润",
            "归属于本集团股东的净利润",
            "本集团股东的净利润",
        ),
    ),
    (
        "deducted_parent_net_profit",
        (
            "归属于上市公司股东的扣除非经常性损益的净利润",
            "归属于上市公司股东的扣除非经常性损益后的净利润",
            "归属于母公司股东的扣除非经常性损益的净利润",
            "归属于母公司股东的扣除非经常性损益后的净利润",
            "归属于母公司所有者的扣除非经常性损益的净利润",
            "归属于母公司所有者的扣除非经常性损益后的净利润",
            "归属于本行股东扣除非经常性损益的净利润",
            "归属于本行股东的扣除非经常性损益的净利润",
            "归属于本行股东的扣除非经常性损益后的净利润",
            "扣除非经常性损益后归属于公司普通股股东的净利润",
        ),
    ),
    ("minority_profit_loss", ("少数股东损益", "少数股东收益", "少数股东的净利润")),
    ("net_profit", ("净利润",)),
    ("other_comprehensive_income", ("其他综合收益的税后净额", "其他综合收益税后净额", "其他综合收益合计", "其他综合收益")),
    ("total_comprehensive_income", ("综合收益总额",)),
    ("parent_total_comprehensive_income", ("归属于母公司所有者的综合收益总额", "归属于母公司股东的综合收益总额")),
    ("minority_total_comprehensive_income", ("归属于少数股东的综合收益总额",)),
    ("operating_cash_inflow_total", ("经营活动现金流入小计",)),
    ("operating_cash_outflow_total", ("经营活动现金流出小计",)),
    ("operating_cash_flow_net", ("经营活动产生的现金流量净额", "经营活动使用的现金流量净额", "经营活动产生使用的现金流量净额", "经营活动产生/的现金流量净额", "经营活动现金流量净额")),
    ("investing_cash_inflow_total", ("投资活动现金流入小计",)),
    ("investing_cash_outflow_total", ("投资活动现金流出小计",)),
    ("investing_cash_flow_net", ("投资活动产生的现金流量净额", "投资活动使用的现金流量净额", "投资活动产生使用的现金流量净额", "投资活动产生/的现金流量净额", "投资活动现金流量净额")),
    ("financing_cash_inflow_total", ("筹资活动现金流入小计",)),
    ("financing_cash_outflow_total", ("筹资活动现金流出小计",)),
    ("financing_cash_flow_net", ("筹资活动产生的现金流量净额", "筹资活动使用的现金流量净额", "筹资活动产生使用的现金流量净额", "筹资活动产生/的现金流量净额", "筹资活动现金流量净额")),
    ("fx_effect_cash", ("汇率变动对现金及现金等价物的影响", "汇率变动对现金的影响")),
    ("cash_equivalents_net_increase", ("现金及现金等价物净增加额", "现金及现金等价物净减少额", "现金及现金等价物净变动额", "现金及现金等价物增加额", "现金及现金等价物减少额")),
    ("cash_equivalents_beginning", ("期初现金及现金等价物余额", "现金的期初余额", "年初现金及现金等价物余额")),
    ("cash_equivalents_ending", ("期末现金及现金等价物余额", "现金的期末余额", "年末现金及现金等价物余额")),
    ("basic_eps", ("基本每股收益",)),
    ("diluted_eps", ("稀释每股收益",)),
    ("deducted_basic_eps", ("扣除非经常性损益后的基本每股收益", "扣除非经常性损益后的每股收益")),
    ("weighted_avg_roe", ("加权平均净资产收益率",)),
    ("deducted_weighted_avg_roe", ("扣除非经常性损益后的加权平均净资产收益率",)),
    ("parent_nav_per_share", ("归属于母公司普通股股东的每股净资产", "归属于上市公司股东的每股净资产", "每股净资产")),
    ("ending_share_capital", ("期末总股本", "总股本")),
]

_ALIAS_MAP = {}
for canonical, aliases in _CANONICAL_ALIASES:
    for alias in aliases:
        _ALIAS_MAP[_compact_key(alias)] = canonical


def _canonical_name(label):
    compact = _compact_key(label)
    if not compact:
        return None
    if "扣除股份支付影响" in compact:
        return None
    if "扣除非经常性损益" in compact and "每股收益" in compact:
        return "deducted_basic_eps"
    if "扣除非经常性损益" in compact and "净资产收益率" in compact:
        return "deducted_weighted_avg_roe"
    if "扣除非经常性损益" in compact and "净利润" in compact:
        return "deducted_parent_net_profit"
    if "稀释每股收益" in compact:
        return "diluted_eps"
    if "基本每股收益" in compact:
        return "basic_eps"
    if "加权平均净资产收益率" in compact:
        return "weighted_avg_roe"
    if "每股净资产" in compact:
        return "parent_nav_per_share"
    if "总股本" in compact:
        return "ending_share_capital"
    if "归属于" in compact and "权益" in compact and _contains_any(
        compact,
        (
            "母公司",
            "上市公司",
            "本公司",
            "本行",
            "本银行",
            "普通股股东",
        ),
    ):
        return "equity_attributable_parent"
    if "经营活动" in compact and "现金流量净额" in compact:
        return "operating_cash_flow_net"
    if "投资活动" in compact and "现金流量净额" in compact:
        return "investing_cash_flow_net"
    if "筹资活动" in compact and "现金流量净额" in compact:
        return "financing_cash_flow_net"
    if "其他综合收益" in compact and "综合收益总额" not in compact:
        return _other_comprehensive_income_canonical(compact)
    if compact in _ALIAS_MAP:
        return _ALIAS_MAP[compact]
    if _looks_like_ratio_label(compact):
        return None
    for alias, canonical in sorted(_ALIAS_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if alias and alias in compact and _allow_substring_alias(alias, canonical, compact):
            return canonical
    return None


def _looks_like_ratio_label(compact):
    return any(word in compact for word in ("占营业收入", "比例", "比率", "变动比例", "增长率", "资产负债率"))


def _other_comprehensive_income_canonical(compact):
    if "少数股东" in compact and "其他综合收益" in compact:
        return "minority_other_comprehensive_income"
    if "归属于" in compact and "其他综合收益" in compact:
        return "parent_other_comprehensive_income"

    detail_terms = (
        "重分类进损益",
        "转损益",
        "不可转损益",
        "不能转损益",
        "公允价值变动",
        "信用损失",
        "减值准备",
        "折算差额",
        "权益法下",
        "现金流量套期",
        "保险合同金融变动",
        "小计",
    )
    if _contains_any(compact, detail_terms):
        return None

    total_labels = {
        "其他综合收益",
        "其他综合收益的税后净额",
        "其他综合收益税后净额",
        "其他综合收益合计",
    }
    if compact in total_labels or compact.endswith("其他综合收益税后净额") or compact.endswith("其他综合收益合计"):
        return "other_comprehensive_income"
    return None


def _allow_substring_alias(alias, canonical, compact):
    if canonical in {"operating_revenue", "net_profit"}:
        return compact.startswith(alias) or compact.endswith(alias)
    if canonical == "total_equity" and "归属于" in compact:
        return False
    return len(alias) >= 6


def _parse_number(text):
    raw = _clean_cell_text(text)
    if not raw or raw in {"-", "—", "--", "－", "不适用", "无"}:
        return None
    normalized = raw.replace(",", "").replace("，", "").replace(" ", "")
    normalized = normalized.replace("人民币", "").replace("元", "")
    negative = False
    if re.fullmatch(r"[（(].+[）)]", normalized):
        negative = True
        normalized = normalized[1:-1]
    normalized = normalized.replace("%", "")
    if not re.fullmatch(r"[-+]?\d+(?:\.\d+)?", normalized):
        return None
    value = float(normalized)
    return -abs(value) if negative else value


def _unit_scale(unit):
    unit = str(unit or "")
    if "百万元" in unit or "百万" in unit:
        return 1000000.0
    if "万元" in unit or unit == "万":
        return 10000.0
    if "千元" in unit:
        return 1000.0
    return 1.0


def _infer_row_scale(label, default_scale):
    compact = _clean_cell_text(label)
    if "百万元" in compact or "百万" in compact:
        return 1000000.0
    if "万元" in compact:
        return 10000.0
    if "千元" in compact:
        return 1000.0
    if "元" in compact:
        return 1.0
    return default_scale


def _currency_from_context(context):
    text = " ".join([context.get("unit") or "", context.get("near_text") or ""])
    if "人民币" in text:
        return "CNY"
    return ""


def _grid_compact_text(grid, max_rows=120, max_cols=8):
    return _compact_key(" ".join(" ".join(row[:max_cols]) for row in grid[:max_rows]))


def _row_compact_text(grid, max_rows=5, max_cols=8):
    return _compact_key(" ".join(" ".join(row[:max_cols]) for row in grid[:max_rows]))


def _contains_any(text, terms):
    return any(term in text for term in terms)


def _hits(text, terms):
    return [term for term in terms if term in text]


def _first_labels(grid, limit=8):
    labels = []
    for row in grid[:limit]:
        if not row:
            continue
        label = _compact_key(row[0])
        if label:
            labels.append(label)
    return labels


def _first_label_is_one_of(grid, terms):
    labels = _first_labels(grid, limit=8)
    return bool(labels and any(term in labels[0] for term in terms))


def _leading_statement_section_label(grid, terms, limit=8):
    labels = _first_labels(grid, limit=limit)
    for label in labels:
        if label in {"项目", "附注", "项目附注"}:
            continue
        if any(term in label for term in terms):
            return label
        return ""
    return ""


def _looks_like_change_analysis_table(compact_title, compact_head):
    if _is_formal_statement_title_for_any_type(compact_title, compact_title):
        return False
    if _contains_any(compact_head, ("同比增减", "变动比例", "变动原因", "增减%")):
        return True
    analysis_terms = (
        "同比增减",
        "变动比例",
        "变动",
        "变动%",
        "增减",
        "增减%",
        "增减幅度",
        "变动原因",
    )
    if _contains_any(compact_head, analysis_terms):
        return True
    title_terms = (
        "相关科目",
        "变动分析",
        "项目分析",
        "主要项目",
        "5现金流",
        "现金流分析",
    )
    return _contains_any(compact_title, title_terms)


def _looks_like_note_detail_table(compact_title, compact_head):
    if _looks_like_investee_financial_note(compact_title, compact_head):
        return True
    if _contains_any(compact_head, ("期末余额本期发生额", "期初余额上期发生额", "期末余额", "期初余额")):
        return True
    note_terms = (
        "重要联营企业",
        "重要合营企业",
        "主要合营公司",
        "主要联营公司",
        "简明资产负债表",
        "简明财务状况表",
        "主要财务信息",
        "关联方",
        "公允价值",
        "被合并方",
        "敏感性",
        "资产负债表日后事项",
    )
    return _contains_any(compact_title, note_terms)


def _looks_like_investee_financial_note(compact_title, compact_head):
    text = compact_title + compact_head
    investee_terms = (
        "合营企业",
        "联营企业",
        "合营公司",
        "联营公司",
        "被投资单位",
        "其他主体中的权益",
        "权益法",
        "重要联营企业",
        "重要合营企业",
        "不重要的合营企业",
        "不重要的联营企业",
        "调节至",
        "投资账面价值",
        "本财务报表账面价值",
    )
    financial_note_terms = (
        "主要财务信息",
        "汇总财务信息",
        "简明财务信息",
        "简明资产负债表",
        "简明财务状况表",
        "财务信息调整",
        "财务信息按照权益法",
        "下表列示",
        "本集团重要",
        "本集团不重要",
    )
    return _contains_any(text, investee_terms) and _contains_any(text, financial_note_terms)


def _looks_like_risk_maturity_table(compact_title, compact_head, compact_body):
    risk_terms = (
        "资产负债表内敞口净额",
        "资产负债表外敞口净额",
        "信用风险敞口",
        "流动性净额",
        "利率重定价缺口",
        "逾期无期限",
        "即期偿还",
        "重定价缺口",
        "信用承诺",
        "到期分析",
        "期限结构",
        "剩余到期日",
        "合同到期日",
        "重新定价日",
        "重定价日",
        "利率风险",
        "剩余到期日分析",
        "平均余额",
        "平均收益率",
        "平均成本率",
        "收益率/成本率",
        "利息收入/支出",
        "净头寸",
    )
    tenor_terms = (
        "逾期/无期限",
        "无期限",
        "实时偿还",
        "即期偿还",
        "1个月以内",
        "1个月至3个月",
        "3个月至1年",
        "1年至5年",
        "5年以上",
    )
    if _contains_any(compact_title, risk_terms):
        return True
    if _contains_any(compact_head, risk_terms):
        return True
    if _contains_any(compact_body, risk_terms):
        return True
    if _contains_any(compact_head, tenor_terms) and _contains_any(
        compact_body,
        ("资产负债表内敞口净额", "资产负债表外敞口净额", "流动性净额", "不计息", "合计"),
    ):
        return True
    return False


def _looks_like_signature_approval_table(grid, compact_title, compact_body):
    if len(grid) > 4:
        return False
    sign_terms = (
        "法定代表人",
        "主管会计工作",
        "会计机构负责人",
        "董事长",
        "行长",
        "首席财务官",
        "财务会计部总经理",
        "公司盖章",
        "公章",
    )
    financial_terms = (
        "资产总计",
        "负债合计",
        "营业收入",
        "利润总额",
        "净利润",
        "经营活动产生的现金流量",
        "现金及现金等价物",
    )
    return len(_hits(compact_body, sign_terms)) >= 2 and not _contains_any(compact_body, financial_terms)


def _looks_like_cash_flow_supplement_table(grid, compact_title, compact_body):
    if "现金流量表" not in compact_title:
        return False
    if len(grid) <= 2 and not any(_parse_number(cell) is not None for row in grid for cell in row):
        return True
    supplement_terms = ("补充资料", "将净利润调节为经营活动", "现金流量补充资料")
    main_cash_flow_terms = ("经营活动现金流入小计", "投资活动现金流入小计", "筹资活动现金流入小计")
    supplement_body_terms = ("净利润", "信用减值损失", "固定资产折旧", "使用权资产折旧", "无形资产摊销")
    return (
        (
            _contains_any(compact_title + compact_body[:500], supplement_terms)
            or len(_hits(compact_body[:800], supplement_body_terms)) >= 3
        )
        and not _contains_any(compact_body, main_cash_flow_terms)
    )


def _looks_like_currency_exposure_note_table(compact_title, compact_head, compact_body):
    currency_header = _contains_any(compact_head, ("人民币美元港币其他合计", "人民币美元(折人民币)港币(折人民币)其他(折人民币)合计"))
    exposure_terms = ("信贷承诺", "衍生金融工具", "外汇风险", "币种", "折人民币")
    return currency_header and len(_hits(compact_body + compact_title, exposure_terms)) >= 2


def _looks_like_management_analysis_table(compact_title, compact_head, compact_body):
    text = compact_title + compact_head + compact_body[:1200]
    analysis_terms = (
        "平均余额",
        "平均收益率",
        "平均成本率",
        "收益率成本率",
        "收益率/成本率",
        "利息收入支出",
        "利息收入/支出",
        "生息资产总额",
        "计息负债总额",
        "变动金额",
        "变动率",
        "占比",
        "按期限结构划分",
    )
    if len(_hits(text, analysis_terms)) >= 2:
        return True
    if _contains_any(text, ("变动金额", "变动率")) and _contains_any(text, ("营业收入", "利息收入", "利息净收入")):
        return True
    return False


def _balance_sheet_body_scope_hint(grid):
    body = _grid_compact_text(grid)
    head = _row_compact_text(grid, max_rows=3)
    if _contains_any(head, ("附注十六", "附注十七", "附注十八", "附注十九", "附注十三", "附注十四")):
        return "parent_company"
    if _contains_any(
        body,
        (
            "归属于母公司股东权益合计",
            "归属于母公司所有者权益合计",
            "归属于母公司股东权益",
            "归属于本行股东权益合计",
            "归属于本行股东的权益",
            "少数股东权益",
        ),
    ):
        return "consolidated"
    return None


def _looks_like_period_header_row(row):
    if not row:
        return False
    first = _compact_key(row[0])
    if first not in {"", "项目"}:
        return False
    period_count = 0
    for cell in row[1:]:
        text = str(cell or "").replace(" ", "")
        if re.fullmatch(r"20\d{2}", text) or re.fullmatch(r"20\d{2}年(?:度|末)?", text):
            period_count += 1
            continue
        if re.fullmatch(r"20\d{2}年\d{1,2}月\d{1,2}日", text):
            period_count += 1
    return period_count >= 2


def _looks_like_key_metrics_body(grid, compact_title, compact_head, compact_body):
    if "季度" in compact_title:
        return False
    if _looks_like_bank_financial_summary_body(grid, compact_title, compact_head, compact_body):
        return True
    performance_hits = _hits(
        compact_body,
        (
            "营业收入",
            "营业利润",
            "利润总额",
            "税前利润",
            "净利润",
            "归属于上市公司股东的净利润",
            "归属于母公司股东的净利润",
            "经营活动产生的现金流量净额",
        ),
    )
    position_hits = _hits(
        compact_body,
        (
            "总资产",
            "资产总额",
            "负债总额",
            "归属于上市公司股东的净资产",
            "归属于母公司股东的权益",
            "客户贷款及垫款总额",
            "客户存款",
        ),
    )
    ratio_hits = _hits(
        compact_body,
        (
            "加权平均净资产收益率",
            "基本每股收益",
            "核心一级资本充足率",
        ),
    )
    return (
        len(grid) >= 8
        and re.search(r"20\d{2}", compact_head)
        and len(performance_hits) >= 4
        and len(position_hits) >= 1
        and len(performance_hits) + len(position_hits) + len(ratio_hits) >= 6
    )


def _looks_like_bank_financial_summary_body(grid, compact_title, compact_head, compact_body):
    if len(grid) < 5 or not re.search(r"20\d{2}", compact_head):
        return False
    title_terms = ("财务概要", "经营业绩", "规模指标", "盈利能力指标", "主要财务数据", "主要财务指标")
    if not _contains_any(compact_title + compact_head, title_terms):
        return False
    performance_hits = _hits(
        compact_body,
        (
            "营业收入",
            "营业利润",
            "利润总额",
            "税前利润",
            "归属于本行股东的净利润",
            "归属于银行股东的净利润",
            "归属于本集团股东的净利润",
            "经营活动产生的现金流量净额",
        ),
    )
    indicator_hits = _hits(
        compact_body,
        (
            "平均总资产回报率",
            "加权平均净资产收益率",
            "成本收入比",
            "净利差",
            "净息差",
            "资本充足率",
            "不良贷款率",
            "拨备覆盖率",
        ),
    )
    bank_scale_hits = _hits(
        compact_body,
        (
            "客户贷款",
            "发放贷款",
            "贷款及垫款总额",
            "客户存款",
            "吸收存款",
            "存款总额",
            "资产总额",
            "总资产",
            "负债总额",
            "总负债",
            "归属于本行股东的权益总额",
        ),
    )
    return len(performance_hits) >= 3 or len(indicator_hits) >= 3 or len(bank_scale_hits) >= 3 or (len(performance_hits) >= 2 and len(bank_scale_hits) >= 1)


def _infer_statement_type_from_body(grid, compact_title):
    compact_head = _row_compact_text(grid)
    compact_body = _grid_compact_text(grid)
    rows = len(grid)
    if _looks_like_cash_flow_part_table(compact_title, compact_body) or _looks_like_cash_flow_net_part_table(compact_title, compact_body):
        return "cash_flow_statement", ["body.cash_flow.part"]
    if rows < 10:
        return None, []
    if _looks_like_change_analysis_table(compact_title, compact_head):
        return None, ["exclude.change_analysis"]
    if _looks_like_note_detail_table(compact_title, compact_head):
        return None, ["exclude.note_detail"]
    if _looks_like_risk_maturity_table(compact_title, compact_head, compact_body):
        return None, ["exclude.risk_table"]

    liability_section_terms = ("负债", "负债和所有者权益", "负债和股东权益", "负债及所有者权益", "负债及股东权益")
    starts_with_assets = bool(_leading_statement_section_label(grid, ("资产",)))
    starts_with_liabilities = bool(
        _leading_statement_section_label(grid, liability_section_terms)
    )

    asset_total_terms = ("资产总计", "资产合计", "资产总额")
    liability_equity_total_terms = (
        "负债和所有者权益总计",
        "负债和股东权益总计",
        "负债及所有者权益总计",
        "负债及股东权益总计",
    )
    if (
        starts_with_assets
        and rows >= 25
        and _contains_any(compact_body, asset_total_terms)
        and _contains_any(compact_body, liability_equity_total_terms)
    ):
        return "balance_sheet", ["body.balance_sheet.full"]

    cash_flow_hits = _cash_flow_body_hits(compact_body)
    if _looks_like_formal_cash_flow_body(compact_body, rows):
        return "cash_flow_statement", ["body.cash_flow.relaxed", f"hits={len(cash_flow_hits)}"]
    if _looks_like_partial_formal_cash_flow_body(compact_body, rows):
        return "cash_flow_statement", ["body.cash_flow.partial_formal", f"hits={len(cash_flow_hits)}"]
    if (
        rows >= 25
        and "经营活动产生的现金流量" in compact_body
        and _contains_any(compact_body, ("投资活动现金流入小计", "投资活动产生的现金流量"))
        and _contains_any(compact_body, ("筹资活动现金流入小计", "筹资活动产生的现金流量"))
        and _contains_any(compact_body, ("现金及现金等价物余额", "年末现金及现金等价物余额", "期末现金及现金等价物余额"))
    ):
        return "cash_flow_statement", ["body.cash_flow", f"hits={len(cash_flow_hits)}"]

    income_hits = _hits(
        compact_body,
        (
            "营业收入",
            "营业总收入",
            "利息净收入",
            "营业利润",
            "利润总额",
            "税前利润",
            "净利润",
            "归属于母公司股东的净利润",
            "归属于上市公司股东的净利润",
            "基本每股收益",
            "稀释每股收益",
        ),
    )
    if (
        rows >= 20
        and len(income_hits) >= 5
        and _contains_any(compact_body, ("营业收入", "营业总收入", "利息净收入"))
        and _contains_any(compact_body, ("净利润", "本年净利润"))
        and "经营活动现金流量" not in compact_body
    ):
        return "income_statement", ["body.income", f"hits={len(income_hits)}"]

    if (
        starts_with_assets
        and rows >= 12
        and _contains_any(compact_body, asset_total_terms)
        and _contains_any(
            compact_body,
            (
                "流动资产",
                "非流动资产",
                "客户贷款及垫款",
                "现金及存放中央银行款项",
                "货币资金",
                "结算备付金",
                "融出资金",
                "买入返售金融资产",
                "交易性金融资产",
                "其他债权投资",
            ),
        )
    ):
        return "balance_sheet", ["body.balance_sheet.asset_part"]
    if (
        starts_with_liabilities
        and rows >= 12
        and _contains_any(compact_body, liability_equity_total_terms)
        and "负债合计" in compact_body
        and _contains_any(compact_body, ("所有者权益合计", "股东权益合计"))
    ):
        return "balance_sheet", ["body.balance_sheet.liability_part"]

    return None, []


def _looks_like_cash_flow_part_table(compact_title, compact_body):
    if _looks_like_change_analysis_table(compact_title, compact_body):
        return False
    section_terms = (
        "经营活动产生的现金流量",
        "经营活动使用的现金流量",
        "投资活动产生的现金流量",
        "投资活动使用的现金流量",
        "筹资活动产生的现金流量",
        "筹资活动使用的现金流量",
    )
    title_or_head = compact_title + compact_body[:260]
    if not _contains_any(title_or_head, section_terms):
        return False
    subtotal_terms = (
        "经营活动现金流入小计",
        "经营活动现金流出小计",
        "投资活动现金流入小计",
        "投资活动现金流出小计",
        "筹资活动现金流入小计",
        "筹资活动现金流出小计",
    )
    if not _contains_any(compact_body, subtotal_terms):
        return False
    body_terms = subtotal_terms + (
        "经营活动产生的现金流量净额",
        "经营活动使用的现金流量净额",
        "投资活动产生的现金流量净额",
        "投资活动使用的现金流量净额",
        "筹资活动产生的现金流量净额",
        "筹资活动使用的现金流量净额",
        "现金及现金等价物净增加额",
        "现金及现金等价物净减少额",
        "期末现金及现金等价物余额",
        "年末现金及现金等价物余额",
    )
    return _contains_any(compact_body, body_terms)


def _cash_flow_net_terms_hit_count(compact):
    nets = (
        "经营活动产生的现金流量净额",
        "经营活动使用的现金流量净额",
        "经营活动产生使用的现金流量净额",
        "经营活动产生/的现金流量净额",
        "投资活动产生的现金流量净额",
        "投资活动使用的现金流量净额",
        "投资活动产生使用的现金流量净额",
        "投资活动产生/的现金流量净额",
        "筹资活动产生的现金流量净额",
        "筹资活动使用的现金流量净额",
        "筹资活动产生使用的现金流量净额",
        "筹资活动产生/的现金流量净额",
    )
    return len(_hits(compact, nets))


def _looks_like_cash_flow_net_part_table(compact_title, compact_body):
    if _looks_like_change_analysis_table(compact_title, compact_body):
        return False
    if _contains_any(compact_title, ("现金流分析", "现金流")) and "现金流量表" not in compact_title:
        return False
    if _contains_any(compact_body[:160], ("同比增减", "变动比例", "增减%")):
        return False
    return _cash_flow_net_terms_hit_count(compact_body) >= 3 and _contains_any(compact_body, ("汇率变动对现金及现金等价物的影响", "现金及现金等价物净增加额", "现金及现金等价物净减少额"))


def _cash_flow_body_hits(compact_body):
    return _hits(
        compact_body,
        (
            "经营活动产生的现金流量",
            "经营活动使用的现金流量",
            "经营活动产生使用的现金流量",
            "经营活动产生/的现金流量",
            "经营活动产生/的现金流量",
            "经营活动现金流入小计",
            "经营活动现金流出小计",
            "经营活动产生的现金流量净额",
            "经营活动使用的现金流量净额",
            "经营活动产生使用的现金流量净额",
            "经营活动产生/的现金流量净额",
            "投资活动产生的现金流量",
            "投资活动使用的现金流量",
            "投资活动产生/的现金流量",
            "投资活动产生/的现金流量",
            "投资活动现金流入小计",
            "投资活动现金流出小计",
            "投资活动产生的现金流量净额",
            "投资活动使用的现金流量净额",
            "投资活动产生/的现金流量净额",
            "筹资活动产生的现金流量",
            "筹资活动使用的现金流量",
            "筹资活动产生/的现金流量",
            "筹资活动产生/的现金流量",
            "筹资活动现金流入小计",
            "筹资活动现金流出小计",
            "筹资活动产生的现金流量净额",
            "筹资活动使用的现金流量净额",
            "筹资活动产生/的现金流量净额",
            "现金及现金等价物净增加额",
            "现金及现金等价物净减少额",
            "期初现金及现金等价物余额",
            "年初现金及现金等价物余额",
            "期末现金及现金等价物余额",
            "年末现金及现金等价物余额",
        ),
    )


def _looks_like_formal_cash_flow_body(compact_body, rows):
    if rows < 12:
        return False
    operating = _contains_any(
        compact_body,
        (
            "经营活动产生的现金流量",
            "经营活动使用的现金流量",
            "经营活动产生使用的现金流量",
            "经营活动现金流入小计",
            "经营活动现金流出小计",
        ),
    )
    investing = _contains_any(
        compact_body,
        (
            "投资活动产生的现金流量",
            "投资活动使用的现金流量",
            "投资活动现金流入小计",
            "投资活动现金流出小计",
        ),
    )
    financing = _contains_any(
        compact_body,
        (
            "筹资活动产生的现金流量",
            "筹资活动使用的现金流量",
            "筹资活动现金流入小计",
            "筹资活动现金流出小计",
        ),
    )
    bridge = _contains_any(
        compact_body,
        (
            "现金及现金等价物净增加额",
            "现金及现金等价物净减少额",
            "期初现金及现金等价物余额",
            "年初现金及现金等价物余额",
            "期末现金及现金等价物余额",
            "年末现金及现金等价物余额",
        ),
    )
    return operating and investing and financing and bridge and len(_cash_flow_body_hits(compact_body)) >= 5


def _looks_like_partial_formal_cash_flow_body(compact_body, rows):
    if rows < 20:
        return False
    operating = (
        _contains_any(compact_body, ("经营活动现金流入小计", "经营活动现金流出小计"))
        and _contains_any(compact_body, ("经营活动产生的现金流量净额", "经营活动使用的现金流量净额", "经营活动产生使用的现金流量净额", "经营活动产生/的现金流量净额"))
    )
    investing = (
        _contains_any(compact_body, ("投资活动现金流入小计", "投资活动现金流出小计"))
        and _contains_any(compact_body, ("投资活动产生的现金流量净额", "投资活动使用的现金流量净额", "投资活动产生使用的现金流量净额", "投资活动产生/的现金流量净额"))
    )
    financing_started = _contains_any(
        compact_body,
        ("筹资活动产生的现金流量", "筹资活动使用的现金流量", "筹资活动产生使用的现金流量", "筹资活动产生/的现金流量", "筹资活动现金流入小计"),
    )
    return operating and investing and financing_started


def _looks_like_minimal_formal_cash_flow_table(compact_title, compact_body):
    if not _is_formal_statement_title(compact_title, compact_title, "现金流量表"):
        return False
    if _looks_like_change_analysis_table(compact_title, compact_body):
        return False
    operating_net = _contains_any(compact_body, ("经营活动产生的现金流量净额", "经营活动使用的现金流量净额", "经营活动产生使用的现金流量净额", "经营活动产生/的现金流量净额"))
    investing_net = _contains_any(compact_body, ("投资活动产生的现金流量净额", "投资活动使用的现金流量净额", "投资活动产生/的现金流量净额"))
    financing_net = _contains_any(compact_body, ("筹资活动产生的现金流量净额", "筹资活动使用的现金流量净额", "筹资活动产生/的现金流量净额"))
    required_nets = operating_net and investing_net and financing_net
    bridge_terms = _contains_any(
        compact_body,
        (
            "汇率变动对现金及现金等价物的影响",
            "现金及现金等价物净增加额",
            "现金及现金等价物净减少额",
            "期初现金及现金等价物余额",
            "年初现金及现金等价物余额",
            "期末现金及现金等价物余额",
            "年末现金及现金等价物余额",
        ),
    )
    return required_nets and bridge_terms


def _formal_statement_body_is_plausible(statement_type, grid, compact_body):
    if not grid:
        return False
    if statement_type == "balance_sheet":
        balance_terms = (
            "资产总计",
            "资产合计",
            "资产总额",
            "负债合计",
            "所有者权益合计",
            "股东权益合计",
            "归属于母公司所有者权益合计",
            "归属于母公司股东权益合计",
            "少数股东权益",
            "负债和所有者权益总计",
            "负债和股东权益总计",
            "流动资产",
            "非流动资产",
            "流动负债",
            "非流动负债",
            "货币资金",
            "现金及存放中央银行款项",
            "发放贷款和垫款",
            "融出资金",
        )
        return len(_hits(compact_body, balance_terms)) >= 2
    if statement_type == "income_statement":
        income_terms = (
            "营业收入",
            "营业总收入",
            "利息净收入",
            "营业利润",
            "利润总额",
            "税前利润",
            "净利润",
            "归属于母公司股东的净利润",
            "归属于母公司所有者的净利润",
            "归属于上市公司股东的净利润",
            "其他综合收益税后净额",
            "其他综合收益的税后净额",
            "综合收益总额",
            "归属于母公司股东的综合收益总额",
            "归属于少数股东的综合收益总额",
            "基本每股收益",
        )
        return len(_hits(compact_body, income_terms)) >= 2
    if statement_type == "cash_flow_statement":
        return len(_cash_flow_body_hits(compact_body)) >= 2
    return False


def _classify_table(table, grid):
    table_type, _ = _classify_table_detail(table, grid)
    return table_type


def _classify_table_detail(table, grid):
    context = table["context"]
    heading = context.get("heading") or ""
    first_row_text = " ".join(grid[0][:3]) if grid else ""
    title = " ".join([heading, first_row_text]).strip()
    if not title:
        title = " ".join([context.get("near_text") or "", first_row_text]).strip()
    compact_heading = _compact_key(heading)
    compact_title = _compact_key(title)
    excluded = (
        "相关科目",
        "变动分析",
        "补充资料",
        "调整对",
        "影响如下",
        "现金流量表项目",
        "财务报表附注",
        "关键审计事项",
        "股份支付",
        "已背书贴现",
        "敏感性",
    )

    first_text = _compact_key(" ".join(grid[0]) if grid else "")
    all_text = _compact_key(" ".join(" ".join(row[:3]) for row in grid[:10]))
    if "季度" in compact_title:
        return None, ["exclude.quarter"]
    if (
        "主要会计数据" in first_text
        or "主要财务指标" in first_text
        or (("主要会计数据" in compact_heading or "主要财务指标" in compact_heading) and "扣除股份支付影响后" not in all_text)
    ):
        return "key_metrics", ["title.key_metrics"]

    compact_head = _row_compact_text(grid)
    compact_body = _grid_compact_text(grid)
    compact_context = _compact_key(" ".join([heading, context.get("near_before") or ""]))
    if _looks_like_investee_financial_note(compact_context, compact_head):
        return None, ["exclude.investee_financial_note"]
    if _looks_like_management_analysis_table(compact_title, compact_head, compact_body):
        return None, ["exclude.management_analysis"]
    if _looks_like_signature_approval_table(grid, compact_title, compact_body):
        return None, ["exclude.signature_approval"]
    if _looks_like_cash_flow_supplement_table(grid, compact_title, compact_body):
        return None, ["exclude.cash_flow_supplement"]
    if _looks_like_currency_exposure_note_table(compact_title, compact_head, compact_body):
        return None, ["exclude.currency_exposure_note"]
    if _looks_like_key_metrics_body(grid, compact_title, compact_head, compact_body):
        return "key_metrics", ["body.key_metrics"]
    if _looks_like_cash_flow_part_table(compact_title, compact_body) or _looks_like_cash_flow_net_part_table(compact_title, compact_body):
        return "cash_flow_statement", ["body.cash_flow.part"]
    if _looks_like_minimal_formal_cash_flow_table(compact_title, compact_body):
        return "cash_flow_statement", ["body.cash_flow.minimal_formal"]

    if _is_formal_statement_title_for_type(compact_heading, compact_title, "balance_sheet"):
        if not _formal_statement_body_is_plausible("balance_sheet", grid, compact_body):
            return None, ["exclude.formal_title_body_mismatch"]
        return "balance_sheet", ["title.formal"]
    if _is_formal_statement_title_for_type(compact_heading, compact_title, "cash_flow_statement"):
        formal_cash_net_part = _cash_flow_net_terms_hit_count(compact_body) >= 3 and _contains_any(
            compact_body,
            ("汇率变动对现金及现金等价物的影响", "现金及现金等价物净增加额", "现金及现金等价物净减少额"),
        )
        if _looks_like_change_analysis_table("", compact_head) and not formal_cash_net_part:
            return None, ["exclude.change_analysis"]
        if not _formal_statement_body_is_plausible("cash_flow_statement", grid, compact_body):
            return None, ["exclude.formal_title_body_mismatch"]
        return "cash_flow_statement", ["title.formal"]
    if _is_formal_statement_title_for_type(compact_heading, compact_title, "income_statement"):
        if not _formal_statement_body_is_plausible("income_statement", grid, compact_body):
            return None, ["exclude.formal_title_body_mismatch"]
        return "income_statement", ["title.formal"]

    if "所有者权益变动表" in compact_title or "股东权益变动表" in compact_title:
        return None, ["exclude.equity_statement"]

    inferred, evidence = _infer_statement_type_from_body(grid, compact_title)
    if inferred:
        return inferred, evidence
    exclude_text = compact_heading or compact_title
    if any(word in title or word in exclude_text for word in excluded):
        return None, ["exclude.context"]
    return None, evidence


def _body_candidate_types(grid):
    compact_body = _grid_compact_text(grid)
    candidates = []
    if _contains_any(compact_body, ("资产总计", "资产合计", "资产总额")) or _contains_any(
        compact_body,
        ("负债和所有者权益总计", "负债和股东权益总计", "负债及所有者权益总计", "负债及股东权益总计"),
    ):
        candidates.append("balance_sheet")
    if _contains_any(compact_body, ("营业收入", "营业总收入", "利息净收入")) and _contains_any(
        compact_body, ("净利润", "利润总额", "税前利润")
    ):
        candidates.append("income_statement")
    if "经营活动产生的现金流量" in compact_body or _contains_any(
        compact_body, ("经营活动现金流入小计", "现金及现金等价物余额")
    ):
        candidates.append("cash_flow_statement")
    return candidates


def _title_candidate_types(table, grid):
    context = table.get("context") or {}
    first_rows = " ".join(" ".join(row[:8]) for row in grid[:2])
    compact_context = _compact_key(" ".join([context.get("heading") or "", first_rows, context.get("near_text") or ""]))
    if not compact_context:
        return []
    if "资产负债表日后事项" in compact_context:
        return []
    candidates = []
    for statement_type, aliases in _STATEMENT_TITLE_ALIASES.items():
        if any(alias in compact_context for alias in aliases):
            candidates.append(statement_type)
    return candidates


def _llm_candidate_types(table, grid):
    candidates = []
    for statement_type in _body_candidate_types(grid) + _title_candidate_types(table, grid):
        if statement_type not in candidates:
            candidates.append(statement_type)
    return candidates


def _canonical_hit_count(grid):
    hits = set()
    for row in grid[:100]:
        for cell in row[:6]:
            canonical = _canonical_name(cell)
            if canonical:
                hits.add(canonical)
    return len(hits)


def _has_period_columns(grid, report_year):
    descriptors = _column_descriptors(grid, "key_metrics", "consolidated", report_year)
    return bool(descriptors)


def _should_consider_llm_candidate(table, grid, table_type, evidence, report_year, report_kind=None):
    if report_kind in {"annual_report_summary", "interim_report_summary"}:
        return False
    if table_type in _CORE_STATEMENT_TYPES:
        return False
    if table_type == "key_metrics":
        return False
    if len(grid) < 3:
        return False
    compact_title = _compact_key(" ".join([table["context"].get("heading") or "", " ".join(grid[0][:8]) if grid else ""]))
    compact_head = _row_compact_text(grid)
    compact_context = _compact_key(
        " ".join(
            [
                table["context"].get("heading") or "",
                table["context"].get("near_before") or "",
            ]
        )
    )
    compact_body = _grid_compact_text(grid)
    if (
        _looks_like_change_analysis_table(compact_title, compact_head)
        or _looks_like_note_detail_table(compact_context + compact_title, compact_head)
        or _looks_like_management_analysis_table(compact_title, compact_head, compact_body)
    ):
        return False
    if "所有者权益变动表" in compact_title or "股东权益变动表" in compact_title:
        return False
    if not _llm_candidate_types(table, grid) and _canonical_hit_count(grid) < 2:
        return False
    return _has_period_columns(grid, report_year)


def _missing_consolidated_statement_types(statements):
    present = {statement_type for statement_type, scope in statements if scope == "consolidated"}
    return sorted(_CORE_STATEMENT_TYPES - present)


def _is_formal_statement_title_for_type(compact_heading, compact_title, statement_type):
    return any(
        _is_formal_statement_title(compact_heading, compact_title, alias)
        for alias in _STATEMENT_TITLE_ALIASES.get(statement_type, ())
    )


def _is_formal_statement_title_for_any_type(compact_heading, compact_title):
    return any(
        _is_formal_statement_title_for_type(compact_heading, compact_title, statement_type)
        for statement_type in _CORE_STATEMENT_TYPES
    )


def _is_formal_statement_title(compact_heading, compact_title, keyword):
    title = compact_heading or compact_title
    if keyword not in title:
        return False
    if len(title) > 80:
        return False
    normalized = _normalize_statement_heading(title)
    allowed = {
        keyword,
        f"合并{keyword}",
        f"母公司{keyword}",
        f"公司{keyword}",
        f"本公司{keyword}",
        f"银行{keyword}",
        f"本行{keyword}",
        f"本银行{keyword}",
        f"本集团{keyword}",
        f"合并及公司{keyword}",
        f"合并及母公司{keyword}",
        f"合并及银行{keyword}",
        f"合并及本行{keyword}",
        f"合并及本银行{keyword}",
        f"合并{keyword}和母公司{keyword}",
        f"合并{keyword}和公司{keyword}",
        f"合并{keyword}和银行{keyword}",
        f"合并{keyword}和本行{keyword}",
        f"合并{keyword}和本银行{keyword}",
        f"合并{keyword}和{keyword}",
        f"合并{keyword}及{keyword}",
        f"合并{keyword}及银行{keyword}",
        f"合并{keyword}及本行{keyword}",
        f"合并{keyword}及本银行{keyword}",
    }
    return normalized in allowed


def _normalize_statement_heading(title):
    title = _compact_key(title)
    title = re.sub(r"^20\d{2}(?:年)?\d{1,2}月\d{1,2}日", "", title)
    title = re.sub(r"^20\d{2}(?:年)?度", "", title)
    title = re.sub(r"^20\d{2}年?", "", title)
    title = re.sub(r"^年度", "", title)
    title = re.sub(r"^\d+", "", title)
    title = re.sub(r"[-—－_]*(续)+$", "", title)
    title = re.sub(r"[-—－_]+$", "", title)
    return title


def _is_bare_statement_heading(title, statement_type):
    if not title:
        return False
    return _normalize_statement_heading(title) == _statement_title(statement_type)


def _default_scope(title):
    if "母公司" in title or "本公司" in title or "本行" in title or "本银行" in title or "银行" in title:
        if "合并" in title or "本集团" in title:
            return None
        return "parent_company"
    if re.search(r"(?:^|\d+[、.．]\s*)(?:公司|银行)(?:资产负债表|利润表|现金流量表)", title):
        return "parent_company"
    if "合并" in title or "本集团" in title:
        return "consolidated"
    return "consolidated"


def _default_scope_for_table(title, grid):
    scope = _default_scope(title)
    if "合并" in _compact_key(title):
        return "consolidated"
    if scope == "consolidated" and _looks_like_parent_company_note_header(grid):
        return "parent_company"
    return scope


def _scope_from_llm_decision(decision, fallback_scope):
    scope = str((decision or {}).get("scope") or "").strip()
    if scope in {"consolidated", "parent_company"}:
        return scope
    return fallback_scope


def _looks_like_parent_company_note_header(grid):
    head = _row_compact_text(grid, max_rows=2)
    if "附注五" in head or "附注四" in head:
        return False
    return bool(re.search(r"附注(?:十|1[0-9])", head))


def _scope_from_text(text, default_scope):
    text = str(text or "")
    compact = _compact_key(text)
    if "合并" in compact or "本集团" in compact or (
        "集团" in compact and "集团股份有限公司" not in compact and "集团有限公司" not in compact
    ):
        return "consolidated"
    if default_scope == "consolidated" and (
        "编制单位" in compact or "股份有限公司" in compact or "有限公司" in compact
    ) and not _contains_any(compact, ("母公司", "本公司", "本行", "本银行")):
        return "consolidated"
    if (
        "母公司" in compact
        or "本公司" in compact
        or "本行" in compact
        or "本银行" in compact
        or compact.endswith("公司")
        or compact.endswith("银行")
        or ("公司" in compact and "集团" not in compact and "合并" not in compact)
        or ("银行" in compact and "集团" not in compact and "合并" not in compact)
        or re.search(r"20\d{2}(?:年|年度|年\d{1,2}月\d{1,2}日)?(?:公司|银行)$", compact)
        or re.search(r"(?:^|[\s　])(?:公司|银行)($|[\s　])", text)
    ):
        return "parent_company"
    return default_scope or "consolidated"


def _scope_label(scope):
    return {"consolidated": "合并", "parent_company": "母公司"}.get(scope, scope or "")


def _period_from_text(text, statement_type, report_year):
    text = str(text or "").replace(" ", "")
    match = re.search(r"(20\d{2})年(\d{1,2})月(\d{1,2})日", text)
    if match:
        return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    match = re.search(r"(20\d{2})年末", text)
    if match:
        return f"{int(match.group(1)):04d}-12-31"
    match = re.search(r"(20\d{2})年度", text)
    if match:
        return match.group(1)
    match = re.search(r"(20\d{2})年", text)
    if match:
        year = int(match.group(1))
        if statement_type == "balance_sheet":
            return f"{year:04d}-12-31"
        return str(year)
    match = re.search(r"(?<!\d)(20\d{2})(?!\d)", text)
    if match:
        year = int(match.group(1))
        if statement_type == "balance_sheet":
            return f"{year:04d}-12-31"
        return str(year)
    if report_year:
        if "期末" in text:
            return f"{report_year:04d}-12-31" if statement_type == "balance_sheet" else str(report_year)
        if "期初" in text:
            prev = report_year - 1
            return f"{prev:04d}-12-31" if statement_type == "balance_sheet" else str(prev)
        if "本期" in text or "本年" in text:
            return str(report_year)
        if "上期" in text or "上年" in text:
            return str(report_year - 1)
        if "年末余额" in text:
            return f"{report_year:04d}-12-31" if statement_type == "balance_sheet" else str(report_year)
        if "年初余额" in text:
            prev = report_year - 1
            return f"{prev:04d}-12-31" if statement_type == "balance_sheet" else str(prev)
        if "本年发生额" in text or "本期发生额" in text:
            return str(report_year)
        if "上年发生额" in text or "上期发生额" in text:
            return str(report_year - 1)
    return ""


def _variant_from_text(text):
    if "调整后" in text:
        return "adjusted"
    if "调整前" in text:
        return "unadjusted"
    return ""


def _is_change_or_ratio_column(text):
    text = str(text or "")
    return "%" in text or "％" in text or any(word in text for word in ("增减", "变动", "增长率", "比例"))


def _value_key(period, variant=""):
    if not period:
        return ""
    return f"{period}_{variant}" if variant else period


def _first_numeric_row(grid):
    for idx, row in enumerate(grid):
        if idx > 8:
            return max(1, idx)
        if _looks_like_period_header_row(row):
            continue
        first = _compact_key(row[0] if row else "")
        if first in {"项目", "附注"}:
            continue
        if sum(1 for cell in row[1:] if _parse_number(cell) is not None) > 0:
            return idx
    return 1 if grid else 0


def _column_descriptors(grid, statement_type, default_scope, report_year):
    if not grid:
        return []
    if statement_type == "balance_sheet":
        return _balance_sheet_column_descriptors(grid, default_scope, report_year)
    first_numeric = _first_numeric_row(grid)
    max_cols = max(len(row) for row in grid)
    headers = []
    for col in range(max_cols):
        parts = []
        for row in grid[:first_numeric]:
            if col < len(row) and row[col]:
                parts.append(row[col])
        headers.append(" ".join(parts))

    descriptors = []
    for col, header in enumerate(headers):
        if col == 0:
            continue
        if "附注" in header and not re.search(r"20\d{2}|期末|期初|本期|上期|本年|上年", header):
            continue
        if _is_change_or_ratio_column(header):
            continue
        period = _period_from_text(header, statement_type, report_year)
        if not period:
            continue
        variant = _variant_from_text(header)
        descriptors.append(
            {
                "column_index": col,
                "label": header,
                "period": period,
                "variant": variant,
                "value_key": _value_key(period, variant),
                "scope": _scope_from_text(header, default_scope),
            }
        )
    if descriptors:
        return descriptors
    if statement_type == "cash_flow_statement":
        return _cash_flow_part_column_descriptors(grid, default_scope, report_year)
    return descriptors


def _cash_flow_part_column_descriptors(grid, default_scope, report_year):
    if not grid or not report_year:
        return []
    compact_body = _grid_compact_text(grid)
    if not _contains_any(
        compact_body,
        (
            "经营活动现金流入小计",
            "经营活动现金流出小计",
            "投资活动现金流入小计",
            "投资活动现金流出小计",
            "筹资活动现金流入小计",
            "筹资活动现金流出小计",
        ),
    ):
        return []
    max_cols = max(len(row) for row in grid)
    numeric_scores = []
    for col in range(max_cols):
        numeric_count = 0
        for row in grid:
            if col < len(row) and _parse_number(row[col]) is not None:
                numeric_count += 1
        numeric_scores.append((col, numeric_count))
    value_cols = [col for col, count in numeric_scores if col > 0 and count >= 3]
    if len(value_cols) < 2:
        return []
    value_cols = value_cols[-2:]
    periods = (str(report_year), str(report_year - 1))
    return [
        {
            "column_index": col,
            "label": period,
            "period": period,
            "variant": "",
            "value_key": _value_key(period),
            "scope": default_scope or "consolidated",
        }
        for col, period in zip(value_cols, periods)
    ]


def _balance_sheet_column_descriptors(grid, default_scope, report_year):
    if not grid:
        return []
    first_numeric = _first_numeric_row(grid)
    max_cols = max(len(row) for row in grid)
    headers = []
    for col in range(max_cols):
        parts = []
        for row in grid[:first_numeric]:
            if col < len(row) and row[col]:
                parts.append(row[col])
        headers.append(" ".join(parts))

    descriptors = []
    for col, header in enumerate(headers):
        if col == 0:
            continue
        if "附注" in header and not re.search(r"20\d{2}|期末|期初|本期|上期|本年|上年|年末|年初", header):
            continue
        if _is_change_or_ratio_column(header):
            continue
        period = _period_from_text(header, "balance_sheet", report_year)
        if not period:
            continue
        variant = _variant_from_text(header)
        descriptors.append(
            {
                "column_index": col,
                "label": header,
                "period": period,
                "variant": variant,
                "value_key": _value_key(period, variant),
                "scope": _scope_from_text(header, default_scope),
            }
        )
    if descriptors:
        return descriptors
    # Fallback for annual reports where balance sheet headers span title rows and the
    # period labels live in a single row with "年末余额 / 年初余额".
    header_row = None
    for row in grid[:6]:
        compact = " ".join(row[:6])
        if any(term in compact for term in ("年末余额", "年初余额", "资产负债表日")):
            header_row = row
            break
    if not header_row:
        return _balance_sheet_numeric_column_fallback(grid, default_scope, report_year)
    fallback = []
    for col, cell in enumerate(header_row):
        if col == 0:
            continue
        period = _period_from_text(cell, "balance_sheet", report_year)
        if not period:
            continue
        fallback.append(
            {
                "column_index": col,
                "label": cell,
                "period": period,
                "variant": "",
                "value_key": _value_key(period),
                "scope": _scope_from_text(cell, default_scope),
            }
        )
    return fallback


def _balance_sheet_numeric_column_fallback(grid, default_scope, report_year):
    if not grid or not report_year:
        return []
    compact_body = _grid_compact_text(grid)
    if not _contains_any(
        compact_body,
        (
            "流动资产合计",
            "非流动资产合计",
            "资产总计",
            "负债合计",
            "股东权益合计",
            "所有者权益合计",
            "负债和股东权益总计",
            "负债和所有者权益总计",
        ),
    ):
        return []
    max_cols = max(len(row) for row in grid)
    numeric_scores = []
    for col in range(max_cols):
        numeric_count = 0
        for row in grid:
            if col < len(row) and _parse_number(row[col]) is not None:
                numeric_count += 1
        numeric_scores.append((col, numeric_count))
    value_cols = [col for col, count in numeric_scores if col > 0 and count >= 3]
    if len(value_cols) < 2:
        return []
    value_cols = value_cols[-2:]
    periods = (f"{report_year:04d}-12-31", f"{report_year - 1:04d}-12-31")
    return [
        {
            "column_index": col,
            "label": period,
            "period": period,
            "variant": "",
            "value_key": _value_key(period),
            "scope": default_scope or "consolidated",
        }
        for col, period in zip(value_cols, periods)
    ]


def _balance_sheet_descriptor_groups(grid, descriptors):
    label_columns = _paired_balance_sheet_label_columns(grid, descriptors)
    if len(label_columns) < 2:
        return [(0, descriptors)]

    max_cols = max(len(row) for row in grid) if grid else 0
    groups = []
    for index, label_col in enumerate(label_columns):
        boundary = label_columns[index + 1] if index + 1 < len(label_columns) else max_cols
        group_descriptors = [desc for desc in descriptors if label_col < desc["column_index"] < boundary]
        if group_descriptors:
            groups.append((label_col, group_descriptors))
    return groups or [(0, descriptors)]


def _paired_balance_sheet_label_columns(grid, descriptors):
    if not grid or not descriptors:
        return [0]
    value_keys = [desc["value_key"] for desc in descriptors if desc.get("value_key")]
    if len(value_keys) == len(set(value_keys)):
        return [0]

    max_cols = max(len(row) for row in grid)
    descriptor_cols = {desc["column_index"] for desc in descriptors}
    candidates = [0]
    for col in range(1, max_cols):
        if col in descriptor_cols:
            continue
        if not any(desc["column_index"] > col for desc in descriptors):
            continue
        if _balance_sheet_label_column_score(grid, col) >= 8:
            candidates.append(col)
    return candidates


def _balance_sheet_label_column_score(grid, col):
    score = 0
    nonempty = 0
    numeric = 0
    canonical_hits = 0
    section_hits = 0
    for row in grid:
        if col >= len(row):
            continue
        text = row[col]
        if not _clean_cell_text(text):
            continue
        nonempty += 1
        if _parse_number(text) is not None:
            numeric += 1
            continue
        compact = _compact_key(text)
        if _canonical_name(text):
            canonical_hits += 1
            score += 3
        if _contains_any(compact, ("资产", "负债", "所有者权益", "股东权益", "流动资产", "非流动资产", "流动负债", "非流动负债")):
            section_hits += 1
            score += 1
    if not nonempty or numeric > nonempty / 2:
        return 0
    if canonical_hits < 2 or section_hits < 2:
        return 0
    return score


def _statement_title(statement_type):
    return {
        "balance_sheet": "资产负债表",
        "income_statement": "利润表",
        "cash_flow_statement": "现金流量表",
    }.get(statement_type, statement_type)


def _new_statement(task_id, filename, statement_type, scope, title, unit, scale, currency):
    return {
        "statement_id": f"{statement_type}:{scope}",
        "statement_type": statement_type,
        "statement_name": _statement_title(statement_type),
        "scope": scope,
        "scope_name": _scope_label(scope),
        "title": title,
        "unit": unit,
        "scale": scale,
        "currency": currency,
        "columns": [],
        "items": [],
        "table_indexes": [],
        "line_numbers": [],
        "_item_lookup": {},
    }


def _add_statement_item(statement, label, row, descriptors, table, scale):
    display_name = _normalize_label(label)
    canonical = _canonical_name(display_name)
    values = {}
    raw_values = {}
    sources = {}
    for desc in descriptors:
        col = desc["column_index"]
        if desc["scope"] != statement["scope"] or col >= len(row):
            continue
        raw = row[col]
        value = _parse_number(raw)
        if value is None:
            continue
        key = desc["value_key"]
        values[key] = value * scale
        raw_values[key] = raw
        sources[key] = {
            "table_index": table["table_index"],
            "line": table["line"],
        }

    if not values:
        return

    lookup_key = canonical or _compact_key(display_name)
    if not lookup_key:
        return
    item = statement["_item_lookup"].get(lookup_key)
    if item is None:
        item = {
            "name": display_name,
            "canonical_name": canonical,
            "values": {},
            "raw_values": {},
            "sources": {},
        }
        statement["_item_lookup"][lookup_key] = item
        statement["items"].append(item)

    for key, value in values.items():
        if key not in item["values"]:
            item["values"][key] = value
            item["raw_values"][key] = raw_values[key]
            item["sources"][key] = sources[key]


def _extract_statement_table(data, statements, table, grid, statement_type, report_year, forced_scope=None):
    context = table["context"]
    title = context.get("heading") or _statement_title(statement_type)
    unit = context.get("unit") or ""
    scale = _unit_scale(unit)
    currency = _currency_from_context(context)
    default_scope = forced_scope or _default_scope_for_table(title, grid)
    descriptors = _column_descriptors(grid, statement_type, default_scope, report_year)
    if not descriptors:
        data["warnings"].append(f"表 {table['table_index']} 未识别到可校验期间列: {title}")
        return
    descriptor_groups = (
        _balance_sheet_descriptor_groups(grid, descriptors)
        if statement_type == "balance_sheet"
        else [(0, descriptors)]
    )

    for desc in descriptors:
        key = (statement_type, desc["scope"])
        if key not in statements:
            statements[key] = _new_statement(
                data.get("task_id"),
                data.get("filename"),
                statement_type,
                desc["scope"],
                title,
                unit,
                scale,
                currency,
            )
        statement = statements[key]
        column = {
            "key": desc["value_key"],
            "period": desc["period"],
            "variant": desc["variant"],
            "label": desc["label"],
        }
        if not any(existing["key"] == column["key"] for existing in statement["columns"]):
            statement["columns"].append(column)
        if table["table_index"] not in statement["table_indexes"]:
            statement["table_indexes"].append(table["table_index"])
        if table["line"] not in statement["line_numbers"]:
            statement["line_numbers"].append(table["line"])

    for label_col, group_descriptors in descriptor_groups:
        for row in grid:
            if not row or label_col >= len(row):
                continue
            label = row[label_col]
            compact = _compact_key(label)
            if not compact or compact in {"项目", "附注"}:
                continue
            if not any(
                desc["column_index"] < len(row) and _parse_number(row[desc["column_index"]]) is not None
                for desc in group_descriptors
            ):
                continue
            for statement in statements.values():
                if statement["statement_type"] != statement_type:
                    continue
                _add_statement_item(statement, label, row, group_descriptors, table, scale)


def _is_bank_metric_table(grid):
    text = _grid_compact_text(grid)
    return "利息净收入" in text and _contains_any(text, ("客户存款", "客户贷款及垫款", "资产总额", "负债总额"))


def _extract_key_metrics(data, table, grid, report_year):
    context = table["context"]
    unit = context.get("unit") or ""
    default_scale = _unit_scale(unit)
    descriptors = _column_descriptors(grid, "key_metrics", "consolidated", report_year)
    if not descriptors:
        return

    metrics = []
    section_scale = default_scale
    is_bank_metric_table = _is_bank_metric_table(grid)
    for row in grid:
        if not row:
            continue
        label = row[0]
        canonical = _canonical_name(label)
        if not canonical and _compact_key(label) == "税前利润" and is_bank_metric_table:
            canonical = "total_profit"
        if not canonical or canonical not in _KEY_METRIC_CANONICALS:
            row_text = " ".join(row)
            inferred_scale = _infer_row_scale(row_text, section_scale)
            if inferred_scale != section_scale:
                section_scale = inferred_scale
            continue
        row_scale = _infer_row_scale(label, section_scale)
        item = {
            "name": _normalize_label(label),
            "canonical_name": canonical,
            "unit": unit,
            "scale": row_scale,
            "values": {},
            "raw_values": {},
            "sources": {},
        }
        for desc in descriptors:
            col = desc["column_index"]
            if col >= len(row):
                continue
            value = _parse_number(row[col])
            if value is None:
                continue
            key = desc["value_key"]
            item["values"][key] = value * row_scale
            item["raw_values"][key] = row[col]
            item["sources"][key] = {
                "table_index": table["table_index"],
                "line": table["line"],
            }
        if item["values"]:
            metrics.append(item)

    if metrics:
        data["key_metrics"].extend(metrics)


class QwenTableJudge:
    def __init__(self, api_base=None, model=None, cache_dir=None, timeout=None, prompt_version=None):
        preset = FINANCIAL_LLM_PRESETS.get(os.environ.get("FINANCIAL_LLM_PRESET", "").strip().lower(), {})
        self.api_base = (api_base or os.environ.get("FINANCIAL_LLM_API_BASE") or preset.get("api_base") or "").rstrip("/")
        self.model = model or os.environ.get("FINANCIAL_LLM_MODEL") or preset.get("model") or "qwen3.6"
        self.cache_dir = cache_dir or os.environ.get("FINANCIAL_LLM_CACHE_DIR")
        self.timeout = float(timeout or os.environ.get("FINANCIAL_LLM_TIMEOUT", "45"))
        self.prompt_version = prompt_version or LLM_TABLE_JUDGE_PROMPT_VERSION

    @classmethod
    def from_env(cls, cache_dir=None):
        enabled = os.environ.get("FINANCIAL_LLM_JUDGE_ENABLED", "0") == "1"
        preset = FINANCIAL_LLM_PRESETS.get(os.environ.get("FINANCIAL_LLM_PRESET", "").strip().lower(), {})
        api_base = os.environ.get("FINANCIAL_LLM_API_BASE") or preset.get("api_base")
        if not enabled or not api_base:
            return None
        return cls(cache_dir=cache_dir)

    def judge(self, table, grid, missing_types, filename=None, report_year=None, rule_evidence=None):
        table_hash = _table_hash(table)
        cached = self._read_cache(table_hash)
        if cached:
            return cached
        request_payload = self._request_payload(table, grid, missing_types, filename, report_year, rule_evidence)
        decision = self._call_model(request_payload)
        normalized = self._normalize_decision(decision, table, table_hash)
        self._write_cache(table_hash, request_payload, normalized)
        return normalized

    def _cache_path(self, table_hash):
        if not self.cache_dir:
            return None
        prompt_slug = _cache_token(self.prompt_version)
        model_slug = _cache_token(self.model)
        return os.path.join(self.cache_dir, f"{table_hash}.{prompt_slug}.{model_slug}.json")

    def _chat_completions_url(self):
        if self.api_base.endswith("/v1"):
            return f"{self.api_base}/chat/completions"
        return f"{self.api_base}/v1/chat/completions"

    def _read_cache(self, table_hash):
        path = self._cache_path(table_hash)
        if not path or not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as infile:
                cached = json.load(infile)
        except (OSError, json.JSONDecodeError):
            return None
        response = cached.get("response") if isinstance(cached, dict) else None
        if isinstance(response, dict):
            response = dict(response)
            response["cache_hit"] = True
            return response
        return None

    def _write_cache(self, table_hash, request_payload, response):
        path = self._cache_path(table_hash)
        if not path:
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        payload = {
            "model": self.model,
            "prompt_version": self.prompt_version,
            "table_hash": table_hash,
            "request": request_payload,
            "response": response,
            "created_at": _now_iso(),
        }
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as outfile:
            json.dump(payload, outfile, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)

    def _request_payload(self, table, grid, missing_types, filename, report_year, rule_evidence):
        context = table.get("context") or {}
        return {
            "filename": filename or "",
            "report_year": report_year,
            "table_index": table.get("table_index"),
            "line": table.get("line"),
            "missing_statement_types": list(missing_types or []),
            "rule_evidence": list(rule_evidence or []),
            "heading": context.get("heading") or "",
            "unit": context.get("unit") or "",
            "near_text": context.get("near_text") or "",
            "candidate_types": _llm_candidate_types(table, grid),
            "table_preview": _table_preview(grid),
        }

    def _prompt(self, request_payload):
        schema = {
            "decision": "accept|reject|needs_review",
            "statement_type": "balance_sheet|income_statement|cash_flow_statement|unknown",
            "scope": "consolidated|parent_company|unknown",
            "confidence": 0.0,
            "is_formal_statement": False,
            "merge_with_previous": False,
            "merge_with_next": False,
            "evidence": [],
            "risk_flags": [],
            "reason": "",
        }
        return (
            "你是财报表格裁判。只判断表格性质，不提取任何数字，不计算校验。\n"
            "请根据标题、上下文、表头、表体行项目判断该表是否为正式三大财务报表。\n"
            "排除管理层分析表、变动分析表、附注明细、联营/合营企业主要财务信息。\n"
            "只输出严格 JSON，不要输出解释性文本。JSON schema 示例：\n"
            f"{json.dumps(schema, ensure_ascii=False)}\n"
            "待判断数据：\n"
            f"{json.dumps(request_payload, ensure_ascii=False)}"
        )

    def _call_model(self, request_payload):
        if not self.api_base:
            return {"decision": "needs_review", "reason": "llm_api_base_not_configured"}
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你只输出严格 JSON。"},
                {"role": "user", "content": self._prompt(request_payload)},
            ],
            "temperature": 0,
        }
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self._chat_completions_url(),
            data=raw,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            return {"decision": "needs_review", "reason": f"llm_error:{exc}"}
        content = ""
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return {"decision": "needs_review", "reason": "llm_invalid_response"}
        return _parse_json_object(content)

    def _normalize_decision(self, decision, table, table_hash):
        if not isinstance(decision, dict):
            decision = {"decision": "needs_review", "reason": "llm_non_json_response"}
        normalized = dict(decision)
        normalized["table_index"] = table.get("table_index")
        normalized["line"] = table.get("line")
        normalized["table_hash"] = table_hash
        normalized["model"] = self.model
        normalized["prompt_version"] = self.prompt_version
        decision_value = str(normalized.get("decision") or "needs_review").strip()
        if decision_value not in {"accept", "reject", "needs_review"}:
            decision_value = "needs_review"
        normalized["decision"] = decision_value
        statement_type = str(normalized.get("statement_type") or "unknown").strip()
        if statement_type not in _CORE_STATEMENT_TYPES:
            statement_type = "unknown"
        normalized["statement_type"] = statement_type
        scope = str(normalized.get("scope") or "unknown").strip()
        if scope not in {"consolidated", "parent_company", "unknown"}:
            scope = "unknown"
        normalized["scope"] = scope
        try:
            confidence = float(normalized.get("confidence") or 0)
        except (TypeError, ValueError):
            confidence = 0.0
        normalized["confidence"] = max(0.0, min(1.0, confidence))
        for key in ("evidence", "risk_flags"):
            if not isinstance(normalized.get(key), list):
                normalized[key] = []
        return normalized


def _parse_json_object(text):
    text = str(text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return {}
    return {}


def _decision_confidence(decision):
    try:
        return float((decision or {}).get("confidence") or 0)
    except (TypeError, ValueError):
        return 0.0


def _llm_decision_is_usable(decision, missing_types):
    if not isinstance(decision, dict):
        return False
    if decision.get("decision") != "accept":
        return False
    if decision.get("statement_type") not in set(missing_types or []):
        return False
    if decision.get("scope") not in {"consolidated", "parent_company"}:
        return False
    if _decision_confidence(decision) < 0.78:
        return False
    if decision.get("is_formal_statement") is False:
        return False
    return True


def _apply_llm_judge(data, statements, candidates, missing_types, llm_judge, filename, report_year):
    if not llm_judge or not missing_types or not candidates:
        return
    for candidate in candidates:
        if not missing_types:
            break
        table = candidate["table"]
        grid = candidate["grid"]
        decision = llm_judge.judge(
            table,
            grid,
            missing_types,
            filename=filename,
            report_year=report_year,
            rule_evidence=candidate.get("evidence"),
        )
        if not isinstance(decision, dict):
            decision = {"decision": "needs_review", "reason": "llm_invalid_decision"}
        data["llm_table_judgments"].append(decision)
        data["classification_evidence"].append(
            {
                "table_index": table["table_index"],
                "line": table["line"],
                "table_type": decision.get("statement_type") or "unknown",
                "evidence": ["llm.table_judge", f"decision={decision.get('decision')}", f"confidence={decision.get('confidence')}"]
                + list(decision.get("evidence") or []),
            }
        )
        if not _llm_decision_is_usable(decision, missing_types):
            continue
        statement_type = decision["statement_type"]
        scope = _scope_from_llm_decision(decision, _default_scope_for_table(table["context"].get("heading") or _statement_title(statement_type), grid))
        _extract_statement_table(data, statements, table, grid, statement_type, report_year, forced_scope=scope)
        missing_types = _missing_consolidated_statement_types(statements)


def build_financial_data(markdown, task_id=None, filename=None, llm_judge=None, llm_cache_dir=None):
    markdown = markdown or ""
    report_year = _detect_report_year(markdown, filename=filename)
    report_kind = _detect_report_kind(markdown, filename=filename)
    industry_profile = _detect_industry_profile(markdown, filename=filename)
    if llm_judge is None:
        llm_judge = QwenTableJudge.from_env(cache_dir=llm_cache_dir)
    data = {
        "schema_version": FINANCIAL_DATA_SCHEMA_VERSION,
        "rule_version": FINANCIAL_RULE_VERSION,
        "task_id": task_id,
        "filename": filename,
        "report_kind": report_kind,
        "report_year": report_year,
        "industry_profile": industry_profile,
        "statements": [],
        "key_metrics": [],
        "classification_evidence": [],
        "llm_table_judgments": [],
        "warnings": [],
        "generated_at": _now_iso(),
    }

    statements = {}
    llm_candidates = []
    parent_sequence_active = False
    balance_sheet_sequence_scope = None
    for table in _iter_markdown_tables(markdown):
        grid = parse_html_table(table["html"])
        if not grid:
            continue
        table_type, evidence = _classify_table_detail(table, grid)
        if _should_consider_llm_candidate(table, grid, table_type, evidence, report_year, report_kind=report_kind):
            candidate_evidence = list(evidence or [])
            candidate_types = _llm_candidate_types(table, grid)
            if candidate_types:
                candidate_evidence.append(f"llm_candidate.types={','.join(candidate_types)}")
            canonical_hits = _canonical_hit_count(grid)
            if canonical_hits:
                candidate_evidence.append(f"llm_candidate.canonical_hits={canonical_hits}")
            llm_candidates.append({"table": table, "grid": grid, "evidence": candidate_evidence})
        if table_type:
            data["classification_evidence"].append(
                {
                    "table_index": table["table_index"],
                    "line": table["line"],
                    "table_type": table_type,
                    "evidence": evidence,
                }
            )
        if table_type == "key_metrics":
            _extract_key_metrics(data, table, grid, report_year)
        elif table_type in {"balance_sheet", "income_statement", "cash_flow_statement"}:
            forced_scope = None
            heading = table["context"].get("heading") or ""
            body_scope_hint = _balance_sheet_body_scope_hint(grid) if table_type == "balance_sheet" else None
            if _is_bare_statement_heading(heading, table_type) and (table_type, "consolidated") in statements:
                forced_scope = "parent_company"
            if table_type == "balance_sheet" and _default_scope_for_table(heading or _statement_title(table_type), grid) == "parent_company":
                forced_scope = "parent_company"
            elif table_type == "balance_sheet" and body_scope_hint:
                forced_scope = body_scope_hint
            elif (
                table_type == "balance_sheet"
                and balance_sheet_sequence_scope
                and any(str(item).startswith("body.balance_sheet") for item in evidence)
            ):
                forced_scope = balance_sheet_sequence_scope
            if (
                table_type in {"balance_sheet", "income_statement", "cash_flow_statement"}
                and parent_sequence_active
                and any(str(item).startswith("body.") for item in evidence)
            ):
                forced_scope = "parent_company"
            if (
                table_type == "balance_sheet"
                and forced_scope is None
                and (table_type, "consolidated") in statements
                and any(str(item).startswith("body.") for item in evidence)
            ):
                # Body-only balance-sheet fragments after the formal consolidated
                # statement are usually duplicated parent-company pages or note
                # snippets. Do not let them overwrite consolidated core totals.
                forced_scope = "parent_company"
            _extract_statement_table(data, statements, table, grid, table_type, report_year, forced_scope=forced_scope)
            scope_hint = forced_scope or _default_scope_for_table(heading or _statement_title(table_type), grid)
            if table_type == "balance_sheet":
                parent_sequence_active = scope_hint == "parent_company"
                if any(str(item).startswith("body.balance_sheet") for item in evidence) or "title.formal" in evidence:
                    balance_sheet_sequence_scope = scope_hint
            elif table_type in {"income_statement", "cash_flow_statement"}:
                parent_sequence_active = False
                balance_sheet_sequence_scope = None

    missing_types = _missing_consolidated_statement_types(statements)
    if report_kind not in {"annual_report_summary", "interim_report_summary"} and "balance_sheet" in missing_types:
        _extract_fragmented_balance_sheet(data, statements, markdown, report_year)
        missing_types = _missing_consolidated_statement_types(statements)
    _apply_llm_judge(data, statements, llm_candidates, missing_types, llm_judge, filename, report_year)
    remaining_missing_types = _missing_consolidated_statement_types(statements)
    if report_kind not in {"annual_report_summary", "interim_report_summary"} and remaining_missing_types:
        missing_names = "、".join(_statement_title(statement_type) for statement_type in remaining_missing_types)
        if not llm_judge:
            data["warnings"].append(f"完整年报未识别到合并三大表: {missing_names}；本地大模型裁判未启用")
        elif not llm_candidates:
            data["warnings"].append(f"完整年报未识别到合并三大表: {missing_names}；未找到可交给本地大模型裁判的候选表")
        else:
            data["warnings"].append(f"完整年报经本地大模型裁判后仍未确认合并三大表: {missing_names}")

    for statement in statements.values():
        statement.pop("_item_lookup", None)
        statement["columns"].sort(key=lambda item: item["key"])
        data["statements"].append(statement)
    data["key_metrics"] = _merge_key_metrics(data["key_metrics"])
    data["statements"].sort(key=lambda item: (item["statement_type"], item["scope"]))
    data["summary"] = {
        "statement_count": len(data["statements"]),
        "key_metric_count": len(data["key_metrics"]),
        "scopes": sorted({item["scope"] for item in data["statements"]}),
    }
    return data


def _extract_fragmented_balance_sheet(data, statements, markdown, report_year):
    if not report_year:
        return
    profit_index = _find_statement_heading_index(markdown, "合并利润表")
    if profit_index < 0:
        return
    current_date = f"{int(report_year):04d}-12-31"
    previous_date = f"{int(report_year) - 1:04d}-12-31"
    window = markdown[max(0, profit_index - 18000): min(len(markdown), profit_index + 1200)]
    rows = []
    for canonical, label in (
        ("total_assets", "资产总计"),
        ("total_liabilities", "负债合计"),
        ("total_equity", "股东权益合计"),
        ("total_liabilities_and_equity", "负债和股东权益总计"),
    ):
        values = _fragmented_balance_sheet_values(window, label)
        if values:
            rows.append((canonical, label, values))
    if len(rows) < 3:
        return
    total_assets = rows[0][2] if rows and rows[0][0] == "total_assets" else None
    liabilities = next((values for canonical, _, values in rows if canonical == "total_liabilities"), None)
    equity = next((values for canonical, _, values in rows if canonical == "total_equity"), None)
    total = next((values for canonical, _, values in rows if canonical == "total_liabilities_and_equity"), None)
    if not _fragmented_balance_sheet_totals_are_consistent(total_assets, liabilities, equity, total):
        return

    statement = _new_statement(
        data.get("task_id"),
        data.get("filename"),
        "balance_sheet",
        "consolidated",
        "合并资产负债表",
        "",
        1.0,
        "CNY",
    )
    statement["columns"] = [
        {"key": current_date, "period": current_date, "variant": "", "label": str(report_year)},
        {"key": previous_date, "period": previous_date, "variant": "", "label": str(report_year - 1)},
    ]
    statement["table_indexes"] = []
    statement["line_numbers"] = []
    line_lookup = {
        "资产总计": _line_for_text(markdown, "资产总计"),
        "负债合计": _line_for_text(markdown, "负债合计"),
        "股东权益合计": _line_for_text(markdown, "股东权益合计"),
        "负债和股东权益总计": _line_for_text(markdown, "负债和股东权益总计"),
    }
    for canonical, label, values in rows:
        item = {
            "name": label,
            "canonical_name": canonical,
            "values": {current_date: values[0], previous_date: values[1]},
            "raw_values": {current_date: _format_raw_number(values[0]), previous_date: _format_raw_number(values[1])},
            "sources": {
                current_date: {"table_index": None, "line": line_lookup.get(label) or 0},
                previous_date: {"table_index": None, "line": line_lookup.get(label) or 0},
            },
        }
        statement["items"].append(item)
        if line_lookup.get(label) and line_lookup[label] not in statement["line_numbers"]:
            statement["line_numbers"].append(line_lookup[label])
    statements[("balance_sheet", "consolidated")] = statement
    data["classification_evidence"].append(
        {
            "table_index": None,
            "line": min(statement["line_numbers"] or [0]),
            "table_type": "balance_sheet",
            "evidence": ["fragmented.balance_sheet.totals"],
        }
    )
    data["warnings"].append("合并资产负债表由碎片化表格总数兜底提取，建议复核原文版式")


def _fragmented_balance_sheet_values(text, label):
    plain = _strip_html(text)
    for match in re.finditer(re.escape(label), plain):
        window = plain[match.end(): match.end() + 260]
        numbers = []
        for number_match in re.finditer(r"[（(]?\d[\d,，]*(?:\.\d+)?[）)]?", window):
            value = _parse_number(number_match.group(0))
            if value is None:
                continue
            numbers.append(value)
            if len(numbers) >= 2:
                break
        if len(numbers) >= 2 and min(abs(numbers[0]), abs(numbers[1])) >= 10000:
            return (numbers[0], numbers[1])
    return None


def _find_statement_heading_index(markdown, heading):
    text = str(markdown or "")
    compact_heading = _compact_key(heading)
    for match in re.finditer(r"^#+\s*(.+)$", text, flags=re.MULTILINE):
        if compact_heading in _compact_key(match.group(1)):
            return match.start()
    direct = text.find(heading)
    if direct >= 0:
        return direct
    return -1


def _first_number(text):
    match = re.search(r"[（(]?\d[\d,，]*(?:\.\d+)?[）)]?", str(text or ""))
    if not match:
        return None
    return _parse_number(match.group(0))


def _fragmented_balance_sheet_totals_are_consistent(total_assets, liabilities, equity, total):
    if not total_assets or not liabilities or not equity:
        return False
    for index in range(2):
        expected = liabilities[index] + equity[index]
        left = total[index] if total else total_assets[index]
        tolerance = _tolerance([left, expected], scale=1.0)
        if abs(left - expected) > tolerance:
            return False
        if total and abs(total_assets[index] - total[index]) > _tolerance([total_assets[index], total[index]], scale=1.0):
            return False
    return True


def _format_raw_number(value):
    if value is None:
        return ""
    return f"{value:,.2f}"


def _line_for_text(markdown, text):
    index = str(markdown or "").find(text)
    if index < 0:
        return 0
    return str(markdown or "").count("\n", 0, index) + 1


def _merge_key_metrics(metrics):
    merged = {}
    for metric in metrics:
        canonical = metric.get("canonical_name")
        if not canonical:
            continue
        existing = merged.get(canonical)
        if existing is None:
            existing = {
                "name": metric.get("name") or canonical,
                "canonical_name": canonical,
                "unit": metric.get("unit") or "",
                "scale": metric.get("scale") or 1.0,
                "values": {},
                "raw_values": {},
                "sources": {},
            }
            merged[canonical] = existing
        for key, value in (metric.get("values") or {}).items():
            if key not in existing["values"]:
                existing["values"][key] = value
                existing["raw_values"][key] = (metric.get("raw_values") or {}).get(key)
                existing["sources"][key] = (metric.get("sources") or {}).get(key)
    return list(merged.values())


def _item_map(statement):
    return {
        item.get("canonical_name"): item
        for item in statement.get("items", [])
        if item.get("canonical_name")
    }


def _value(statement, canonical, period):
    item = _item_map(statement).get(canonical)
    if not item:
        return None, None
    if period in item.get("values", {}):
        return item["values"][period], item
    return None, item


def _source_table_for_item(item, period):
    source = ((item or {}).get("sources") or {}).get(period) or {}
    table_index = source.get("table_index")
    try:
        return int(table_index)
    except (TypeError, ValueError):
        return None


def _source_tables_for_inputs(statement, inputs, period):
    if not statement:
        return {}
    items = _item_map(statement)
    tables = {}
    for canonical in inputs or []:
        item = items.get(canonical)
        table_index = _source_table_for_item(item, period)
        if table_index is not None:
            tables[canonical] = table_index
    return tables


def _source_table_span_suspect(source_tables):
    values = [value for value in (source_tables or {}).values() if value is not None]
    if len(values) < 2:
        return False
    return max(values) - min(values) > 8


def _magnitude_mismatch_suspect(left_value, right_value):
    if left_value is None or right_value is None:
        return False
    left = abs(float(left_value))
    right = abs(float(right_value))
    smaller = min(left, right)
    larger = max(left, right)
    if smaller < 1.0:
        return False
    return larger / smaller >= 100.0


def _periods_for_statement(statement):
    periods = set()
    for item in statement.get("items", []):
        periods.update(item.get("values", {}).keys())
    return sorted(periods)


def _tolerance(values, scale=1.0):
    numeric = [abs(value) for value in values if value is not None]
    magnitude = max(numeric) if numeric else 0.0
    return max(float(scale or 1.0), magnitude * 0.000005, 1.0)


def _check(rule_id, rule_name, statement, period, left_name, left_value, right_formula, right_value, scale, inputs):
    if left_value is None or right_value is None:
        return {
            "rule_id": rule_id,
            "rule_name": rule_name,
            "statement_type": statement.get("statement_type") if statement else "",
            "scope": statement.get("scope") if statement else "",
            "period": period,
            "status": "skipped",
            "reason": "missing_required_items",
            "inputs": inputs,
        }
    diff = left_value - right_value
    tolerance = _tolerance([left_value, right_value], scale=scale)
    status = "pass" if abs(diff) <= tolerance else "fail"
    source_tables = _source_tables_for_inputs(statement, inputs, period)
    reason = ""
    if status == "fail" and _source_table_span_suspect(source_tables):
        status = "warning"
        reason = "source_scope_mismatch_suspect"
    elif status == "fail" and _magnitude_mismatch_suspect(left_value, right_value):
        status = "warning"
        reason = "parse_suspect_magnitude_mismatch"
    item = {
        "rule_id": rule_id,
        "rule_name": rule_name,
        "statement_type": statement.get("statement_type") if statement else "",
        "scope": statement.get("scope") if statement else "",
        "period": period,
        "left": {"name": left_name, "value": left_value},
        "right": {"formula": right_formula, "value": right_value},
        "diff": diff,
        "tolerance": tolerance,
        "status": status,
        "inputs": inputs,
    }
    if source_tables:
        item["source_tables"] = source_tables
    if reason:
        item["reason"] = reason
    return item


def _soft_check(rule_id, rule_name, statement, period, left_name, left_value, right_formula, right_value, scale, inputs, warning_reason=None):
    item = _check(rule_id, rule_name, statement, period, left_name, left_value, right_formula, right_value, scale, inputs)
    if item.get("status") == "fail":
        item["status"] = "warning"
        item["reason"] = warning_reason or "rough_check_outside_tolerance"
    elif item.get("status") == "pass":
        item["reason"] = warning_reason or "rough_check_passed"
    return item


def _warning_item(rule_id, rule_name, statement_type, scope, period, message, inputs=None, values=None):
    item = {
        "rule_id": rule_id,
        "rule_name": rule_name,
        "statement_type": statement_type or "",
        "scope": scope or "",
        "period": period,
        "status": "warning",
        "reason": message,
        "inputs": inputs or [],
    }
    if values is not None:
        item["values"] = values
    return item


def _derived_item(rule_id, rule_name, statement_type, scope, period, value, inputs=None, status="pass", reason="derived_metric"):
    return {
        "rule_id": rule_id,
        "rule_name": rule_name,
        "statement_type": statement_type or "",
        "scope": scope or "",
        "period": period,
        "status": status,
        "reason": reason,
        "value": value,
        "inputs": inputs or [],
    }


def _statement_by(data, statement_type, scope="consolidated"):
    for statement in data.get("statements", []):
        if statement.get("statement_type") == statement_type and statement.get("scope") == scope:
            return statement
    return None


def _metric_by(data, canonical):
    for item in data.get("key_metrics", []):
        if item.get("canonical_name") == canonical:
            return item
    return None


def _metric_value(data, canonical, report_year):
    item = _metric_by(data, canonical)
    if not item:
        return None, None
    keys = []
    if report_year:
        keys.extend([str(report_year), f"{report_year}-12-31"])
    keys.extend(sorted(item.get("values", {}).keys(), reverse=True))
    for key in keys:
        if key in item.get("values", {}):
            return item["values"][key], item
    return None, item


def _statement_value(data, statement_type, canonical, period, scope="consolidated"):
    statement = _statement_by(data, statement_type, scope=scope)
    if not statement:
        return None, None, None
    value, item = _value(statement, canonical, period)
    return value, item, statement


def _balance_sheet_total_assets(statement, period):
    if not statement:
        return None, None, False
    value, item = _value(statement, "total_assets", period)
    if value is not None:
        return value, item, False
    total_liabilities_and_equity, item = _value(statement, "total_liabilities_and_equity", period)
    if total_liabilities_and_equity is not None:
        return total_liabilities_and_equity, item, True
    total_liabilities, _ = _value(statement, "total_liabilities", period)
    total_equity, _ = _value(statement, "total_equity", period)
    if total_liabilities is not None and total_equity is not None:
        return total_liabilities + total_equity, None, True
    return None, None, False


def build_financial_checks(data):
    checks = []
    warnings = []
    if not isinstance(data, dict):
        data = {}

    for statement in data.get("statements", []):
        statement_type = statement.get("statement_type")
        scale = statement.get("scale") or 1.0
        for period in _periods_for_statement(statement):
            if statement_type == "balance_sheet":
                checks.extend(_balance_sheet_checks(statement, period, scale))
            elif statement_type == "income_statement":
                checks.extend(_income_statement_checks(statement, period, scale))
            elif statement_type == "cash_flow_statement":
                checks.extend(_cash_flow_checks(statement, period, scale))

    checks.extend(_cross_metric_checks(data))
    checks.extend(_derived_financial_indicator_checks(data))
    checks.extend(_yoy_change_warning_checks(data))

    if data.get("report_kind") in {"annual_report_summary", "interim_report_summary"} and not data.get("statements"):
        warnings.append("当前文件为报告摘要，已识别主要会计数据/财务指标，但不应将摘要文件当作完整年报；如需三大表，请使用年度报告全文")
    else:
        if not _statement_by(data, "balance_sheet"):
            warnings.append("未提取到合并资产负债表")
        if not _statement_by(data, "income_statement"):
            warnings.append("未提取到合并利润表")
        if not _statement_by(data, "cash_flow_statement"):
            warnings.append("未提取到合并现金流量表")

    counts = {"pass": 0, "fail": 0, "warning": 0, "skipped": 0}
    for item in checks:
        counts[item.get("status", "skipped")] = counts.get(item.get("status", "skipped"), 0) + 1
    overall = "fail" if counts.get("fail") else ("pass" if counts.get("pass") else "skipped")
    return {
        "schema_version": FINANCIAL_CHECKS_SCHEMA_VERSION,
        "rule_version": FINANCIAL_RULE_VERSION,
        "task_id": data.get("task_id"),
        "filename": data.get("filename"),
        "report_kind": data.get("report_kind"),
        "report_year": data.get("report_year"),
        "industry_profile": data.get("industry_profile"),
        "overall_status": overall,
        "summary": {
            "total": len(checks),
            "pass": counts.get("pass", 0),
            "fail": counts.get("fail", 0),
            "warning": counts.get("warning", 0),
            "skipped": counts.get("skipped", 0),
        },
        "checks": checks,
        "warnings": warnings + data.get("warnings", []),
        "generated_at": _now_iso(),
    }


def _balance_sheet_checks(statement, period, scale):
    total_assets, total_assets_item, total_assets_derived = _balance_sheet_total_assets(statement, period)
    total_liabilities, _ = _value(statement, "total_liabilities", period)
    total_equity, _ = _value(statement, "total_equity", period)
    total_liabilities_and_equity, _ = _value(statement, "total_liabilities_and_equity", period)
    current_assets, _ = _value(statement, "current_assets", period)
    non_current_assets, _ = _value(statement, "non_current_assets", period)
    current_liabilities, _ = _value(statement, "current_liabilities", period)
    non_current_liabilities, _ = _value(statement, "non_current_liabilities", period)
    parent_equity, _ = _value(statement, "equity_attributable_parent", period)
    minority_interests, _ = _value(statement, "minority_interests", period)
    checks = [
        _check(
            "bs.assets_eq_liabilities_plus_equity",
            "资产总计 = 负债合计 + 所有者权益合计",
            statement,
            period,
            "资产总计",
            total_assets,
            "负债合计 + 所有者权益合计",
            _sum_optional(total_liabilities, total_equity),
            scale,
            ["total_assets", "total_liabilities", "total_equity"],
        ),
        _check(
            "bs.total_assets_eq_liabilities_and_equity_total",
            "资产总计 = 负债和所有者权益总计",
            statement,
            period,
            "资产总计",
            total_assets,
            "负债和所有者权益总计",
            total_liabilities_and_equity,
            scale,
            ["total_assets", "total_liabilities_and_equity"],
        ),
        _check(
            "bs.current_plus_non_current_assets",
            "流动资产合计 + 非流动资产合计 = 资产总计",
            statement,
            period,
            "资产总计",
            total_assets,
            "流动资产合计 + 非流动资产合计",
            _sum_optional(current_assets, non_current_assets),
            scale,
            ["total_assets", "current_assets", "non_current_assets"],
        ),
        _check(
            "bs.current_plus_non_current_liabilities",
            "流动负债合计 + 非流动负债合计 = 负债合计",
            statement,
            period,
            "负债合计",
            total_liabilities,
            "流动负债合计 + 非流动负债合计",
            _sum_optional(current_liabilities, non_current_liabilities),
            scale,
            ["total_liabilities", "current_liabilities", "non_current_liabilities"],
        ),
    ]
    if statement.get("scope") == "consolidated" and (parent_equity is not None or minority_interests is not None):
        checks.append(
            _check(
                "bs.parent_equity_plus_minority",
                "归母权益 + 少数股东权益 = 所有者权益合计",
                statement,
                period,
                "所有者权益合计",
                total_equity,
            "归属于母公司权益合计 + 少数股东权益",
            _sum_optional(parent_equity, minority_interests),
            scale,
            ["total_equity", "equity_attributable_parent", "minority_interests"],
        )
        )
    return checks


def _income_statement_checks(statement, period, scale):
    operating_profit, _ = _value(statement, "operating_profit", period)
    nonop_income, _ = _value(statement, "non_operating_income", period)
    nonop_expenses, _ = _value(statement, "non_operating_expenses", period)
    total_profit, _ = _value(statement, "total_profit", period)
    income_tax, _ = _value(statement, "income_tax_expense", period)
    net_profit, _ = _value(statement, "net_profit", period)
    parent_net_profit, _ = _value(statement, "parent_net_profit", period)
    minority_profit, _ = _value(statement, "minority_profit_loss", period)
    minority_formula = "归属于母公司股东的净利润 + 少数股东损益"
    minority_inputs = ["net_profit", "parent_net_profit", "minority_profit_loss"]
    if _looks_like_truncated_minority_profit_loss(net_profit, parent_net_profit, minority_profit, scale):
        minority_profit = net_profit - parent_net_profit
        minority_formula = "归属于母公司股东的净利润 + 推导少数股东损益(净利润-归母净利润)"
        minority_inputs = ["net_profit", "parent_net_profit", "minority_profit_loss", "derived_minority_profit_loss"]
    other_comprehensive, _ = _value(statement, "other_comprehensive_income", period)
    total_comprehensive, _ = _value(statement, "total_comprehensive_income", period)
    comprehensive_formula, comprehensive_right, comprehensive_inputs = _comprehensive_income_bridge_candidate(
        statement,
        period,
        scale,
        net_profit,
        other_comprehensive,
        total_comprehensive,
    )
    return [
        _check(
            "is.total_profit_bridge",
            "利润总额 = 营业利润 + 营业外收入 - 营业外支出",
            statement,
            period,
            "利润总额",
            total_profit,
            "营业利润 + 营业外收入 +/- 营业外支出",
            _closest_candidate(
                total_profit,
                _sum_optional(operating_profit, nonop_income, _negate(nonop_expenses)),
                _sum_optional(operating_profit, nonop_income, nonop_expenses),
            ),
            scale,
            ["total_profit", "operating_profit", "non_operating_income", "non_operating_expenses"],
        ),
        _check(
            "is.net_profit_bridge",
            "净利润 = 利润总额 - 所得税费用",
            statement,
            period,
            "净利润",
            net_profit,
            "利润总额 +/- 所得税费用",
            _closest_candidate(
                net_profit,
                _sum_optional(total_profit, _negate(income_tax)),
                _sum_optional(total_profit, income_tax),
            ),
            scale,
            ["net_profit", "total_profit", "income_tax_expense"],
        ),
        _check(
            "is.net_profit_attribution",
            "净利润 = 归母净利润 + 少数股东损益",
            statement,
            period,
            "净利润",
            net_profit,
            minority_formula,
            _sum_optional(parent_net_profit, minority_profit),
            scale,
            minority_inputs,
        ),
        _check(
            "is.total_comprehensive_income_bridge",
            "综合收益总额 = 净利润 + 其他综合收益",
            statement,
            period,
            "综合收益总额",
            total_comprehensive,
            comprehensive_formula,
            comprehensive_right,
            scale,
            comprehensive_inputs,
        ),
    ]


def _looks_like_truncated_minority_profit_loss(net_profit, parent_net_profit, minority_profit, scale):
    if net_profit is None or parent_net_profit is None or minority_profit is None:
        return False
    direct_right = parent_net_profit + minority_profit
    direct_tolerance = _tolerance([net_profit, direct_right], scale=scale)
    if abs(net_profit - direct_right) <= direct_tolerance:
        return False
    implied = net_profit - parent_net_profit
    if abs(implied) <= direct_tolerance:
        return False
    # OCR/table split artifacts sometimes keep only the first digit of the minority line.
    # Treat it as truncated only when the extracted value is tiny versus the implied value.
    return abs(minority_profit) <= max(float(scale or 1.0) * 10, abs(implied) * 0.001)


def _comprehensive_income_bridge_candidate(statement, period, scale, net_profit, other_comprehensive, total_comprehensive):
    candidates = []

    def add_candidate(formula, value, inputs):
        if value is None:
            return
        candidates.append((formula, value, inputs))

    add_candidate(
        "净利润 + 其他综合收益的税后净额",
        _sum_optional(net_profit, other_comprehensive),
        ["total_comprehensive_income", "net_profit", "other_comprehensive_income"],
    )

    parent_oci, _ = _value(statement, "parent_other_comprehensive_income", period)
    minority_oci, _ = _value(statement, "minority_other_comprehensive_income", period)
    add_candidate(
        "净利润 + 归属于母公司股东的其他综合收益 + 归属于少数股东的其他综合收益",
        _sum_optional(net_profit, parent_oci, minority_oci),
        [
            "total_comprehensive_income",
            "net_profit",
            "parent_other_comprehensive_income",
            "minority_other_comprehensive_income",
        ],
    )
    if parent_oci is not None and (
        statement.get("scope") == "parent_company" or minority_oci is None
    ):
        add_candidate(
            "净利润 + 归属口径其他综合收益",
            _sum_optional(net_profit, parent_oci),
            ["total_comprehensive_income", "net_profit", "parent_other_comprehensive_income"],
        )

    if net_profit is not None and total_comprehensive is not None:
        implicit_zero_tolerance = _tolerance([net_profit, total_comprehensive], scale=scale)
        if abs(total_comprehensive - net_profit) <= implicit_zero_tolerance:
            add_candidate(
                "净利润 + 未列示其他综合收益(按0)",
                net_profit,
                ["total_comprehensive_income", "net_profit"],
            )

    if not candidates:
        return "净利润 + 其他综合收益的税后净额", None, [
            "total_comprehensive_income",
            "net_profit",
            "other_comprehensive_income",
        ]
    if total_comprehensive is None:
        return candidates[0]
    return min(candidates, key=lambda item: abs(total_comprehensive - item[1]))


def _cash_flow_checks(statement, period, scale):
    op_in, _ = _value(statement, "operating_cash_inflow_total", period)
    op_out, _ = _value(statement, "operating_cash_outflow_total", period)
    op_net, _ = _value(statement, "operating_cash_flow_net", period)
    inv_in, _ = _value(statement, "investing_cash_inflow_total", period)
    inv_out, _ = _value(statement, "investing_cash_outflow_total", period)
    inv_net, _ = _value(statement, "investing_cash_flow_net", period)
    fin_in, _ = _value(statement, "financing_cash_inflow_total", period)
    fin_out, _ = _value(statement, "financing_cash_outflow_total", period)
    fin_net, _ = _value(statement, "financing_cash_flow_net", period)
    fx, _ = _value(statement, "fx_effect_cash", period)
    net_inc, _ = _value(statement, "cash_equivalents_net_increase", period)
    begin, _ = _value(statement, "cash_equivalents_beginning", period)
    ending, _ = _value(statement, "cash_equivalents_ending", period)
    return [
        _check(
            "cf.operating_net",
            "经营活动现金流量净额 = 经营现金流入 - 经营现金流出",
            statement,
            period,
            "经营活动产生的现金流量净额",
            op_net,
            "经营活动现金流入小计 +/- 经营活动现金流出小计",
            _closest_candidate(op_net, _sum_optional(op_in, _negate(op_out)), _sum_optional(op_in, op_out)),
            scale,
            ["operating_cash_flow_net", "operating_cash_inflow_total", "operating_cash_outflow_total"],
        ),
        _check(
            "cf.investing_net",
            "投资活动现金流量净额 = 投资现金流入 - 投资现金流出",
            statement,
            period,
            "投资活动产生的现金流量净额",
            inv_net,
            "投资活动现金流入小计 +/- 投资活动现金流出小计",
            _closest_candidate(inv_net, _sum_optional(inv_in, _negate(inv_out)), _sum_optional(inv_in, inv_out)),
            scale,
            ["investing_cash_flow_net", "investing_cash_inflow_total", "investing_cash_outflow_total"],
        ),
        _check(
            "cf.financing_net",
            "筹资活动现金流量净额 = 筹资现金流入 - 筹资现金流出",
            statement,
            period,
            "筹资活动产生的现金流量净额",
            fin_net,
            "筹资活动现金流入小计 +/- 筹资活动现金流出小计",
            _closest_candidate(fin_net, _sum_optional(fin_in, _negate(fin_out)), _sum_optional(fin_in, fin_out)),
            scale,
            ["financing_cash_flow_net", "financing_cash_inflow_total", "financing_cash_outflow_total"],
        ),
        _check(
            "cf.net_increase_bridge",
            "现金及现金等价物净增加额 = 三项现金流量净额 + 汇率影响",
            statement,
            period,
            "现金及现金等价物净增加额",
            net_inc,
            "经营活动净额 + 投资活动净额 + 筹资活动净额 + 汇率影响",
            _sum_optional(op_net, inv_net, fin_net, fx or 0.0),
            scale,
            ["cash_equivalents_net_increase", "operating_cash_flow_net", "investing_cash_flow_net", "financing_cash_flow_net", "fx_effect_cash"],
        ),
        _check(
            "cf.ending_cash_bridge",
            "期末现金及现金等价物余额 = 期初余额 + 净增加额",
            statement,
            period,
            "期末现金及现金等价物余额",
            ending,
            "期初现金及现金等价物余额 + 现金及现金等价物净增加额",
            _sum_optional(begin, net_inc),
            scale,
            ["cash_equivalents_ending", "cash_equivalents_beginning", "cash_equivalents_net_increase"],
        ),
    ]


def _sum_optional(*values):
    if any(value is None for value in values):
        return None
    return sum(values)


def _negate(value):
    if value is None:
        return None
    return -value


def _closest_candidate(expected, *candidates):
    valid = [value for value in candidates if value is not None]
    if not valid:
        return None
    if expected is None:
        return valid[0]
    return min(valid, key=lambda value: abs(expected - value))


def _cross_metric_checks(data):
    report_year = data.get("report_year")
    if not report_year:
        return []
    current_year = str(report_year)
    current_date = f"{int(report_year):04d}-12-31"
    rules = [
        ("cross.revenue", "主要会计数据营业收入 = 合并利润表营业收入", "operating_revenue", "income_statement", "operating_revenue", current_year),
        ("cross.total_profit", "主要会计数据利润总额 = 合并利润表利润总额", "total_profit", "income_statement", "total_profit", current_year),
        ("cross.parent_net_profit", "主要会计数据归母净利润 = 合并利润表归母净利润", "parent_net_profit", "income_statement", "parent_net_profit", current_year),
        ("cross.operating_cash_flow", "主要会计数据经营现金流 = 合并现金流量表经营现金流", "operating_cash_flow_net", "cash_flow_statement", "operating_cash_flow_net", current_year),
        ("cross.total_assets", "主要会计数据总资产 = 合并资产负债表资产总计", "total_assets", "balance_sheet", "total_assets", current_date),
        ("cross.parent_equity", "主要会计数据归母净资产 = 合并资产负债表归母权益", "equity_attributable_parent", "balance_sheet", "equity_attributable_parent", current_date),
    ]
    checks = []
    for rule_id, rule_name, metric_name, statement_type, statement_item, period in rules:
        metric_value, metric_item = _metric_value(data, metric_name, report_year)
        statement_value, statement_item_data, statement_obj = _statement_value(data, statement_type, statement_item, period)
        derived_total_assets = False
        if statement_value is None and statement_type == "balance_sheet" and statement_item == "total_assets":
            statement_value, statement_item_data, derived_total_assets = _balance_sheet_total_assets(statement_obj, period)
        scale = max(float((metric_item or {}).get("scale") or 1.0), float((statement_obj or {}).get("scale") or 1.0))
        statement_value, factor = _auto_align_scale(metric_value, statement_value, scale)
        formula = (statement_item_data or {}).get("name") or statement_item
        if factor != 1.0:
            formula = f"{formula} * {factor:g}"
        checks.append(
            _soft_check(
                rule_id,
                rule_name,
                statement_obj or {"statement_type": statement_type, "scope": "consolidated"},
                period,
                (metric_item or {}).get("name") or metric_name,
                metric_value,
                formula,
                statement_value,
                scale,
                [metric_name, statement_item],
                warning_reason="跨章节指标与财务报表不一致，可能存在重述、调整后指标、口径差异或抽取错位，建议复核来源表",
            )
        )
    return checks


def _derived_financial_indicator_checks(data):
    report_year = data.get("report_year")
    if not report_year:
        return []
    current_year = str(report_year)
    current_date = f"{int(report_year):04d}-12-31"
    industry_profile = data.get("industry_profile") or "general"
    checks = []

    balance = _statement_by(data, "balance_sheet")
    total_assets, _, _ = _balance_sheet_total_assets(balance, current_date) if balance else (None, None, False)
    total_liabilities, _ = _value(balance, "total_liabilities", current_date) if balance else (None, None)
    if total_assets is not None and total_liabilities is not None and total_assets:
        ratio = total_liabilities / total_assets
        status = "pass"
        reason = "derived_metric"
        if industry_profile not in _FINANCIAL_INDUSTRY_PROFILES and ratio >= 0.8:
            status = "warning"
            reason = "资产负债率较高，建议结合行业和附注复核偿债压力"
        checks.append(
            _derived_item(
                "ratio.asset_liability_ratio",
                "资产负债率 = 负债合计 / 资产总计",
                "balance_sheet",
                "consolidated",
                current_date,
                ratio,
                ["total_liabilities", "total_assets"],
                status=status,
                reason=reason,
            )
        )

    equity, _ = _value(balance, "equity_attributable_parent", current_date) if balance else (None, None)
    nav_metric, nav_item = _metric_value(data, "parent_nav_per_share", report_year)
    share_capital, share_item = _metric_value(data, "ending_share_capital", report_year)
    if equity is not None and share_capital not in (None, 0) and nav_metric is not None:
        estimated_nav = equity / share_capital
        checks.append(
            _soft_check(
                "rough.parent_nav_per_share",
                "每股净资产粗略复核 = 归母权益 / 期末总股本",
                balance or {"statement_type": "balance_sheet", "scope": "consolidated"},
                current_date,
                (nav_item or {}).get("name") or "每股净资产",
                nav_metric,
                "归属于母公司权益 / 期末总股本",
                estimated_nav,
                max(float((nav_item or {}).get("scale") or 1.0), 0.01),
                ["parent_nav_per_share", "equity_attributable_parent", "ending_share_capital"],
                warning_reason="粗略复核不一致，可能由股本口径、单位或加权因素导致",
            )
        )

    income = _statement_by(data, "income_statement")
    parent_profit, _ = _value(income, "parent_net_profit", current_year) if income else (None, None)
    eps_metric, eps_item = _metric_value(data, "basic_eps", report_year)
    if parent_profit is not None and share_capital not in (None, 0) and eps_metric is not None:
        estimated_eps = parent_profit / share_capital
        checks.append(
            _soft_check(
                "rough.basic_eps",
                "基本每股收益粗略复核 = 归母净利润 / 期末总股本",
                income or {"statement_type": "income_statement", "scope": "consolidated"},
                current_year,
                (eps_item or {}).get("name") or "基本每股收益",
                eps_metric,
                "归母净利润 / 期末总股本",
                estimated_eps,
                max(float((eps_item or {}).get("scale") or 1.0), 0.01),
                ["basic_eps", "parent_net_profit", "ending_share_capital"],
                warning_reason="EPS 仅为粗略复核，正式口径通常使用加权平均股数",
            )
        )
    return checks


def _yoy_change_warning_checks(data):
    report_year = data.get("report_year")
    if not report_year:
        return []
    current_year = str(report_year)
    previous_year = str(int(report_year) - 1)
    current_date = f"{int(report_year):04d}-12-31"
    previous_date = f"{int(report_year) - 1:04d}-12-31"
    checks = []

    metric_rules = [
        ("operating_revenue", "营业收入"),
        ("parent_net_profit", "归母净利润"),
        ("operating_cash_flow_net", "经营活动现金流量净额"),
        ("total_assets", "总资产"),
        ("total_liabilities", "总负债"),
    ]
    for canonical, label in metric_rules:
        metric = _metric_by(data, canonical)
        if not metric:
            continue
        current_key = current_date if current_date in metric.get("values", {}) else current_year
        previous_key = previous_date if previous_date in metric.get("values", {}) else previous_year
        current_value = metric.get("values", {}).get(current_key)
        previous_value = metric.get("values", {}).get(previous_key)
        if current_value is None or previous_value in (None, 0):
            continue
        change = (current_value - previous_value) / abs(previous_value)
        if abs(change) < 0.3:
            continue
        checks.append(
            _warning_item(
                f"yoy.key_metric.{canonical}",
                f"{label}同比变动超过 30%",
                "key_metrics",
                "consolidated",
                current_key,
                f"{label}同比变动 {change:.2%}，建议结合年报解释和附注复核",
                [canonical],
                {"current": current_value, "previous": previous_value, "change_ratio": change},
            )
        )
    return checks


def _auto_align_scale(left_value, right_value, scale):
    if left_value is None or right_value is None:
        return right_value, 1.0
    factors = (1.0, 1000.0, 10000.0, 1000000.0, 0.001, 0.0001, 0.000001)
    best_factor = min(factors, key=lambda factor: abs(left_value - right_value * factor))
    aligned = right_value * best_factor
    if best_factor != 1.0 and abs(left_value - aligned) <= _tolerance([left_value, aligned], scale=scale):
        return aligned, best_factor
    return right_value, 1.0
