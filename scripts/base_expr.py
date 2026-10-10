#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
base_expr.py — Obsidian base の述語式ミニ言語（ビューエンジン Step1〜2・2026-07-28）

`filters:` の各リーフ（例 `month.contains("2025-06")` / `status != "archived"` /
`type.containsAny("📕本", "📖漫画")` / `!due.isEmpty()` / `file.inFolder("07_Logs/ログ")`）と
`formulas:` の式（例 `if(due.isEmpty(), "", if(due < today(), "🔴 超過", ...))`）の両方を
字句解析→構文解析→評価の3段で処理する。`eval()` は使わない。

タスク管理.mdステップ（2026-07-28）で `today()` 日付関数・比較演算子(<,<=,>,>=)・
単項`=`（`==`の別表記。`status = "on-hold"` で実測）・素の関数呼び出し（`if(cond, a, b)`）・
加算演算子（`today() + "7d"`）を追加。

    expr       := additive ( ("==" | "=" | "!=" | "<" | "<=" | ">" | ">=") additive )?
    additive   := unary ( "+" unary )*
    unary      := "!" unary | value
    value      := STRING | list | postfix
    list       := "[" (value ("," value)*)? "]"           # リストリテラル（Areas10ブロックで実測・2026-07-28）
    postfix    := IDENT "(" args? ")"                     # 素の関数呼び出し（today()/if()。タスク管理.md実測）
                | IDENT ("." IDENT)*                      # プロパティ参照
                | IDENT ("." IDENT)* "." IDENT "(" args? ")"  # メソッド呼び出し（末尾のみ）
    args       := arg ("," arg)*
    arg        := expr                                    # if()の分岐は入れ子exprを許す
"""
import re
from datetime import date, timedelta


class BaseExprError(Exception):
    pass


# ── 字句解析 ──────────────────────────────────────────
_TOKEN_RE = re.compile(
    r'(?P<STRING>"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')'
    r'|(?P<NEQ>!=)'
    r'|(?P<EQ>==)'
    r'|(?P<EQ1>=)'
    r'|(?P<LE><=)'
    r'|(?P<GE>>=)'
    r'|(?P<LT><)'
    r'|(?P<GT>>)'
    r'|(?P<PLUS>\+)'
    r'|(?P<BANG>!)'
    r'|(?P<DOT>\.)'
    r'|(?P<LPAREN>\()'
    r'|(?P<RPAREN>\))'
    r'|(?P<LBRACKET>\[)'
    r'|(?P<RBRACKET>\])'
    r'|(?P<COMMA>,)'
    r'|(?P<IDENT>[A-Za-z_][A-Za-z0-9_]*)'
)

_COMPARE_OP = {"EQ": "==", "EQ1": "==", "NEQ": "!=", "LT": "<", "LE": "<=", "GT": ">", "GE": ">="}


def tokenize(s):
    tokens = []
    pos, n = 0, len(s)
    while pos < n:
        if s[pos].isspace():
            pos += 1
            continue
        m = _TOKEN_RE.match(s, pos)
        if not m:
            raise BaseExprError(f"unexpected character at {pos} in {s!r}: {s[pos:pos + 20]!r}")
        kind = m.lastgroup
        text = m.group(kind)
        if kind == "STRING":
            text = text[1:-1]
        tokens.append((kind, text))
        pos = m.end()
    tokens.append(("EOF", None))
    return tokens


# ── 構文解析（再帰下降。演算子は == / != の1段のみなのでPratt段数も1段） ──
class _Parser:
    def __init__(self, tokens, src):
        self.tokens = tokens
        self.src = src
        self.i = 0

    def peek(self):
        return self.tokens[self.i]

    def advance(self):
        t = self.tokens[self.i]
        self.i += 1
        return t

    def expect(self, kind):
        t = self.advance()
        if t[0] != kind:
            raise BaseExprError(f"expected {kind} but got {t} in {self.src!r}")
        return t

    def parse_expr(self):
        node = self.parse_additive()
        if self.peek()[0] in _COMPARE_OP:
            op_kind, _ = self.advance()
            right = self.parse_additive()
            node = ("compare", _COMPARE_OP[op_kind], node, right)
        return node

    def parse_additive(self):
        node = self.parse_unary()
        while self.peek()[0] == "PLUS":
            self.advance()
            right = self.parse_unary()
            node = ("add", node, right)
        return node

    def parse_unary(self):
        if self.peek()[0] == "BANG":
            self.advance()
            return ("not", self.parse_unary())
        return self.parse_value()

    def parse_value(self):
        if self.peek()[0] == "STRING":
            _, text = self.advance()
            return ("lit", text)
        if self.peek()[0] == "LBRACKET":
            return self.parse_list()
        return self.parse_postfix()

    def parse_list(self):
        self.expect("LBRACKET")
        items = []
        if self.peek()[0] != "RBRACKET":
            items.append(self.parse_value())
            while self.peek()[0] == "COMMA":
                self.advance()
                items.append(self.parse_value())
        self.expect("RBRACKET")
        return ("list", items)

    def parse_postfix(self):
        _, first = self.expect("IDENT")
        if self.peek()[0] == "LPAREN":
            # 素の関数呼び出し（today()/if(...)）。プロパティ経由でなく直接の関数名として扱う。
            self.advance()
            args = self._parse_args()
            self.expect("RPAREN")
            return ("call", [], first, args)
        path = [first]
        while self.peek()[0] == "DOT":
            self.advance()
            _, name = self.expect("IDENT")
            if self.peek()[0] == "LPAREN":
                self.advance()
                args = self._parse_args()
                self.expect("RPAREN")
                return ("call", path, name, args)
            path.append(name)
        return ("path", path)

    def _parse_args(self):
        args = []
        if self.peek()[0] != "RPAREN":
            args.append(self.parse_arg())
            while self.peek()[0] == "COMMA":
                self.advance()
                args.append(self.parse_arg())
        return args

    def parse_arg(self):
        # if() の分岐は文字列だけでなく比較・加算・入れ子 if() も取りうるため、フル expr を許す。
        return self.parse_expr()


def parse(pred_str):
    tokens = tokenize(pred_str)
    p = _Parser(tokens, pred_str)
    node = p.parse_expr()
    if p.peek()[0] != "EOF":
        raise BaseExprError(f"trailing tokens after expression: {pred_str!r}")
    return node


# ── プロパティ解決 ──────────────────────────────────────
_FILE_FIELDS = {"name", "folder", "ext", "path", "ctime", "mtime", "size"}


def resolve_property(path, record):
    """ドット区切りのプロパティパスを Note レコード（vault_index._build_record の形）から解決する。
    file.* は record のトップレベル項目、note.* は file.* を含め record 全体
    （まず record 直下→無ければ fm）、裸の識別子は frontmatter 優先・無ければ record 直下にフォールバック。
    """
    if not path:
        return None
    head, rest = path[0], path[1:]
    if head == "file":
        if not rest:
            return record.get("path")
        key = rest[0]
        return record.get(key) if key in _FILE_FIELDS else None
    if head == "note":
        if not rest:
            return None
        key = rest[0]
        if key in record:
            return record.get(key)
        return record.get("fm", {}).get(key)
    if head == "formula":
        # formulas: の名前空間（`formula.期限バッジ` 等）。view_engine.run_view が事前計算した
        # {formula名: 評価結果} を record["formula"] にマージしてから呼ぶ前提（タスク管理.mdステップ）。
        if not rest:
            return None
        return record.get("formula", {}).get(rest[0])
    fm = record.get("fm", {})
    if head in fm:
        return fm.get(head)
    return record.get(head)


def _contains(value, needle):
    """Obsidianの `.contains()` は 文字列プロパティ=部分一致／リストプロパティ=要素完全一致、と
    挙動が違う。vault_index は一部キー（area/tags/month等）を単一値でも常にリスト化するため、
    このインデックス経由では両者の区別が失われている。ここでは両対応（部分一致 or 完全一致）にして、
    「単一値がリスト化されたケース」を正しくカバーする（2026-07-28プランの既知の簡略化・要再検証）。
    """
    if value is None:
        return False
    if isinstance(value, list):
        return any(str(item) == needle or needle in str(item) for item in value)
    return needle in str(value)


def _is_empty(value):
    if value is None:
        return True
    if isinstance(value, list):
        return len(value) == 0
    if isinstance(value, str):
        return value.strip() == ""
    return False


def _truthy(value):
    if value is None:
        return False
    if isinstance(value, list):
        return len(value) > 0
    if isinstance(value, str):
        return value.strip() != ""
    return bool(value)


_DATE_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})")
_DURATION_RE = re.compile(r"^(\d+)d$")


def _to_date(value):
    """比較演算子(<,<=,>,>=)用の日付コアース。date型はそのまま、`YYYY-MM-DD...`文字列は date に、
    それ以外（None・空文字・不正形式）は None（＝順序比較不能）を返す。"""
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        m = _DATE_RE.match(value.strip())
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                return None
    return None


def _compare(op, left, right):
    if op in ("<", "<=", ">", ">="):
        # 現状の使用箇所（タスク管理.md）は due/start と today()±duration の日付順序比較のみ。
        # 日付コアース不能な値は「起きないはず」のデータ不整合として明示的にエラーにする
        # （黙って False にすると壊れたdueが気付かれないまま埋もれるため）。
        ld, rd = _to_date(left), _to_date(right)
        if ld is None or rd is None:
            raise BaseExprError(f"cannot order-compare (not a date): {left!r} {op} {right!r}")
        return {"<": ld < rd, "<=": ld <= rd, ">": ld > rd, ">=": ld >= rd}[op]
    if isinstance(right, list):
        # `area == ["ハンドボール"]` 形（リストリテラル）＝要素集合の一致（順不同）。
        # プロパティ側が単一値でも常にリスト化されている実装（vault_index）を吸収するため、
        # スカラー/None も1要素(0要素)のリストとみなして比較する（2026-07-28・Areas10ブロック実測）。
        left_list = left if isinstance(left, list) else ([] if left is None else [left])
        eq = {str(v) for v in left_list} == {str(v) for v in right}
    elif isinstance(left, list):
        eq = right in left or any(str(item) == right for item in left)
    elif isinstance(left, date) or isinstance(right, date):
        # `due == today()` 形。isEmpty ガード後に呼ばれる前提なので None は来ない想定。
        ld, rd = _to_date(left), _to_date(right)
        eq = ld is not None and rd is not None and ld == rd
    else:
        eq = (str(left) if left is not None else "") == right
    return eq if op == "==" else not eq


def _eval_add(left, right):
    """`today() + "7d"` 形の加算（date + 日数duration文字列）のみサポート。"""
    if isinstance(left, date) and isinstance(right, str):
        m = _DURATION_RE.match(right.strip())
        if m:
            return left + timedelta(days=int(m.group(1)))
    raise BaseExprError(f"unsupported '+' operands: {left!r} + {right!r}")


def _eval_call(path, method, args, record):
    if not path:
        # 素の関数呼び出し（プロパティ経由でない）。
        if method == "today":
            return date.today()
        if method == "if":
            cond = _truthy(_eval(args[0], record))
            branch = args[1] if cond else args[2]
            return _eval(branch, record)
        raise BaseExprError(f"unsupported function: {method}()")
    if path == ["file"] and method == "inFolder":
        arg = _eval(args[0], record).rstrip("/")
        p = record.get("path", "")
        return p == arg or p.startswith(arg + "/")
    value = resolve_property(path, record)
    if method == "contains":
        return _contains(value, _eval(args[0], record))
    if method == "containsAny":
        return any(_contains(value, _eval(a, record)) for a in args)
    if method == "isEmpty":
        return _is_empty(value)
    raise BaseExprError(f"unsupported method: .{method}()")


def _eval(node, record):
    kind = node[0]
    if kind == "lit":
        return node[1]
    if kind == "path":
        return resolve_property(node[1], record)
    if kind == "list":
        return [_eval(item, record) for item in node[1]]
    if kind == "not":
        return not _truthy(_eval(node[1], record))
    if kind == "add":
        return _eval_add(_eval(node[1], record), _eval(node[2], record))
    if kind == "compare":
        _, op, left, right = node
        return _compare(op, _eval(left, record), _eval(right, record))
    if kind == "call":
        _, path, method, args = node
        return _eval_call(path, method, args, record)
    raise BaseExprError(f"unknown AST node: {node}")


def eval_predicate(pred_str, record):
    """述語文字列を1件の Note レコードに対して評価し True/False を返す（filters: 用）。"""
    node = parse(pred_str)
    return _truthy(_eval(node, record))


def eval_value_expr(expr_str, record):
    """式文字列を1件の Note レコードに対して評価し、真偽値でなく生の評価結果
    （文字列・date・None等）を返す（formulas: 用。if()の分岐は文字列を返すのが実例）。"""
    node = parse(expr_str)
    return _eval(node, record)
