# -*- coding: utf-8 -*-
r"""
decisions.py — 決裁（旧・朝スタンドアップ §2）の永続ストア
(2026-07-31 新設。ブリーフィング一本化にともない散文パースから分離)

なぜ分離したか
--------------
決裁は「1日1回のブリーフィング本文」とライフサイクルが違う（3時間おきに補充される）。
散文 .md に同居させていたため、①本文の mtime が3時間ごとに変わり照合が壊れる
②押下済みの判定を LLM に毎回再構築させる（processed/ を7日分読ませる）③ダッシュボードが
番号付きリストをパースするので「N. で始めろ・太字始まり禁止」という書式指示が必要、
という3つの負債が出ていた。未決裁だけを持つローリングな JSON にすればすべて消える。

ファイル
--------
99_System/decisions/open.json          未決裁だけが入る（ここが決裁の正）
99_System/decisions/resolved/YYYY-MM.jsonl  決着したものの履歴（追記のみ）

1件の形
-------
{ "id": "d-a1b2c3d4",     # sha1(task_path|question)[:8] ＝ 同じ問いは同じ id
  "question": "見出し（何を決めるか）",
  "context":  "背景一文",
  "yes": "YES を選んだとき何をするか",
  "no":  "NO を選んだとき何をするか",
  "response_type": "yes_no" | "choice" | "text" | "datetime",  # 応答の型（旧データは自動推定）
  "options": [{"id": "a", "label": "A案"}],       # choice のときだけ
  "task_path": "04_Tasks/…/○○.md",   # 紐づくタスク（無ければ ""）
  "source": "inbox_monitor",           # 誰が積んだか
  "priority": 1,                        # 小さいほど上位。音声はこの上位3件だけ読む
  "created": "2026-07-31T07:00",
  "status": "pending" | "deferred",    # open.json に居るのはこの2つだけ
  "comment": "",                        # 💬補足コメント（本文があれば決裁済み扱い）
  "selected_option": "",                # choice の回答（resolved 時）
  "answer": "",                         # text の回答（resolved 時）
  "deferred_at": "2026-07-31" }        # 保留した日（status=deferred のとき）

status の扱い
-------------
承認 / 却下      → open.json から取り除き resolved/ へ追記する（＝二度と出ない。再掲判定が不要になる）
コメント（本文あり） → 承認/却下と同じく resolved/ へ追記して open.json から消える（status="コメント"）。
                  ユーザーにとって「コメントを書く＝その場で判断を下した」ため、承認/却下と同じ確定行為として扱う
                  （2026-08-03 /ops-review で仕様変更。従来は pending のまま残り続けていたが、
                  コメント内容の反映先（タスクファイル等）は従来どおり ui-queue 回収ステップが担う）
選択（主回答）      → selected_option / selected_label を保存して resolved/ へ追記する
回答（主回答）      → answer を保存して resolved/ へ追記する
保留            → open.json に残すが status="deferred"。翌日以降にまた前面へ出る
削除            → open.json から取り除き resolved/ へ追記する（status="deleted"）。
                  タスク完了時の自動削除またはユーザーによる手動削除。理由記録なし（2026-08-13 新設）

実際のタスクファイルへの反映は従来どおり 99_System/ui-queue/decision_results_*.json を
orchestrator が回収して行う。このモジュールは「何を聞いているか」だけを持ち、反映はしない。

response_type は、行動の承認を聞く既存の yes_no、A/B/C 等から選ぶ choice、
不足情報を自由記述で受ける text、日付と開始時刻を選ぶ datetime の4種類。
choice は画面の「その他（自由に書く）」から自由記述（回答）も受けるので、不足情報も
候補を挙げて choice で聞くのが既定。選択肢の無い text は候補を挙げられない時だけ（2026-10-09）。
旧形式の yes/no やコメントはそのまま読める。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shuki_paths  # noqa: E402  (VAULT の単一情報源。公開版はshuki_paths.jsonで差し替え)

VAULT = shuki_paths.VAULT
DEC_DIR = shuki_paths.system_dir_for(VAULT) / "decisions"
OPEN_FILE = DEC_DIR / "open.json"
RESOLVED_DIR = DEC_DIR / "resolved"

# open.json に居られる status（これ以外は resolved 行き）
OPEN_STATUS = ("pending", "deferred")
RESOLVING_CHOICES = ("承認", "却下")
RESPONSE_TYPES = ("yes_no", "choice", "text", "datetime")

# ⏸ 保留のエスカレーション（2026-09-23 新設）
# 同じ問いが繰り返し保留された場合は、「やめる」を含む選択へ作り替える。
# 個人の決裁件数や履歴はコードに含めず、保留回数は各レコードで管理する。
ESCALATE_AFTER = 3


def _explicit_response_type(raw: dict) -> str:
    """入力レコードが指定した応答型を正規化する。"""
    requested = str(raw.get("response_type") or raw.get("input_type") or "").strip().lower()
    aliases = {
        "yesno": "yes_no",
        "binary": "yes_no",
        "free_text": "text",
        "answer": "text",
        "date_time": "datetime",
        "datetime_local": "datetime",
        "datetime-local": "datetime",
        "session_datetime": "datetime",
    }
    return aliases.get(requested, requested)


def _is_session_datetime_question(raw: dict) -> bool:
    """セッション日時の旧・自由記述カードを日時選択へ移行する。"""
    explicit = _explicit_response_type(raw)
    if explicit == "datetime" or explicit not in ("", "text"):
        return False
    haystack = " ".join(str(raw.get(key) or "") for key in ("question", "context", "task_path"))
    has_session = bool(re.search(r"(セッション|session)", haystack, re.IGNORECASE))
    has_datetime = bool(re.search(
        r"(日時|開始日時|日時指定|開始日|実施日|開催日|何時|時刻|日付|date|time)",
        haystack,
        re.IGNORECASE,
    ))
    return has_session and has_datetime


def _option_id(index: int) -> str:
    """選択肢に id が無い場合の安定した短い id。"""
    if index < 26:
        return chr(ord("a") + index)
    return str(index + 1)


def _normalise_options(raw_options) -> list[dict]:
    """options を UI と履歴で扱える {id, label, detail?} の配列へ整える。"""
    if not isinstance(raw_options, list):
        return []
    out = []
    seen = set()
    for index, raw in enumerate(raw_options):
        if isinstance(raw, dict):
            option_id = raw.get("id") or raw.get("value") or raw.get("key")
            label = raw.get("label") or raw.get("text") or raw.get("name")
            detail = raw.get("detail") or raw.get("effect")
        elif isinstance(raw, str):
            option_id = None
            label = raw
            detail = ""
        else:
            continue
        label = str(label or "").strip()
        option_id = str(option_id or _option_id(index)).strip()
        if not label or not option_id or option_id in seen:
            continue
        option = {"id": option_id, "label": label}
        if detail:
            option["detail"] = str(detail).strip()
        out.append(option)
        seen.add(option_id)
    return out


def _response_type(raw: dict, options: list[dict]) -> str:
    """新旧レコードから応答型を推定する。"""
    requested = _explicit_response_type(raw)
    if requested in RESPONSE_TYPES:
        # 選択肢付きの text は choice として出す（選択式カードは「その他（自由に書く）」で
        # 自由記述も受けるため、text と分ける意味がない。2026-10-09 自由記述だけのカードを減らす）
        if requested == "text" and options:
            return "choice"
        if requested != "choice" or options:
            return requested
    if options:
        return "choice"
    if raw.get("yes") or raw.get("no"):
        return "yes_no"
    return "text"


def _escalated(item: dict) -> dict | None:
    """ESCALATE_AFTER 回以上保留されたカードを「やめる」を含む選択へ作り替える。

    元の question は escalated_from に残し、id は変えない（履歴が切れないように）。
    返り値 None は「まだ作り替えない」。
    """
    if int(item.get("deferred_count") or 0) < ESCALATE_AFTER:
        return None
    if item.get("response_type") == "choice" and item.get("escalated_from"):
        return item  # すでに作り替え済み
    n = int(item["deferred_count"])
    item = dict(item)
    item["escalated_from"] = item.get("escalated_from") or item["question"]
    item["escalated_type"] = item.get("escalated_type") or item.get("response_type", "")
    item["question"] = f"{n}回保留：{item['escalated_from']}"
    item["context"] = (
        f"このカードは{n}回先延ばされました（初回 {item.get('first_deferred_at') or item.get('created', '')[:10]}）。"
        "日時を決め直すのではなく、やるかやめるかを決めます。"
        + ("　" + item["context"] if item.get("context") else "")
    )
    item["response_type"] = "choice"
    item["options"] = [
        {"id": "a", "label": "やめる",
         "detail": "紐づくタスクを cancelled にして、この問いを閉じる"},
        {"id": "b", "label": "5分に削る",
         "detail": "「5分だけ手を付ける」に縮めて今週中のタスクとして残す"},
        {"id": "c", "label": "直近の空き枠で確定",
         "detail": "SHUKI がカレンダーの空きを見て日時を入れる（要 GCal 書き込み承認）"},
    ]
    item["priority"] = min(int(item.get("priority") or 50), 1)
    return item


def _decorate_item(item: dict) -> dict:
    """旧形式を壊さず、画面/API用の応答型を付けたコピーを返す。"""
    item = dict(item)
    options = _normalise_options(item.get("options"))
    response_type = _response_type(item, options)
    if response_type == "text" and _is_session_datetime_question(item):
        response_type = "datetime"
    item["response_type"] = response_type
    if options:
        item["options"] = options
    return _escalated(item) or item


def make_id(question: str, task_path: str = "") -> str:
    """同じ問いには同じ id を与える（重複起票をハッシュだけで弾けるようにする）。

    question は表記ゆれ（前後の空白・全角/半角スペース・末尾の句点）で別物にならないよう正規化する。
    """
    q = re.sub(r"\s+", "", question or "").strip("。.　 ")
    seed = f"{task_path or ''}|{q}"
    return "d-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8]


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def load_open() -> list[dict]:
    """未決裁の一覧を priority 昇順 → created 昇順で返す。

    削除済み（status="deleted"）のものは返さない。削除判定は apply_choice("削除")で
    open.json から消す時に行われるため、ここが呼ばれる時点でdeleted は既に resolved/ に移動済み。
    壊れていれば空リスト。
    """
    items = _read_json(OPEN_FILE, [])
    if not isinstance(items, list):
        return []
    items = [_decorate_item(d) for d in items
             if isinstance(d, dict) and d.get("id")]
    items.sort(key=lambda d: (d.get("priority", 99), d.get("created", "")))
    return items


def save_open(items: list[dict]) -> None:
    DEC_DIR.mkdir(parents=True, exist_ok=True)
    OPEN_FILE.write_text(
        json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")


def add(new_items: list[dict], source: str = "") -> tuple[int, int]:
    """未決裁を追加する。既に同じ id があれば触らない（＝再掲が構造的に起きない）。

    例外は1つだけ：選択肢の無い自由記述カード（text）と同じ id の提案が options 付きで届いたら、
    カードを増やさずその選択肢を既存カードに足して choice にする（2026-10-09 新設。
    「自由記述だけはきつい」ため、補充便が既存カードを後から選択式へ直せるようにする）。

    戻り値: (追加した件数＋選択肢を足した件数, 既存で飛ばした件数)
    """
    items = load_open()
    known = {d["id"] for d in items}
    resolved_ids = load_resolved_ids()
    added = skipped = 0
    now = datetime.now().strftime("%Y-%m-%dT%H:%M")
    for raw in new_items:
        if not isinstance(raw, dict):
            continue
        q = (raw.get("question") or "").strip()
        if not q:
            continue
        tp = (raw.get("task_path") or "").strip()
        did = raw.get("id") or make_id(q, tp)
        options = _normalise_options(raw.get("options"))
        if did in known or did in resolved_ids:
            current = next((d for d in items if d["id"] == did), None)
            if (current is not None and options and not current.get("options")
                    and current.get("response_type") == "text"):
                current["options"] = options
                current["response_type"] = "choice"
                added += 1
            else:
                skipped += 1
            continue
        yes = (raw.get("yes") or "").strip()
        no = (raw.get("no") or "").strip()
        response_type = _response_type(raw, options)
        if response_type == "text" and _is_session_datetime_question(raw):
            skipped += 1
            continue
        record = {
            "id": did,
            "question": q,
            "context": (raw.get("context") or "").strip(),
            "yes": yes,
            "no": no,
            "response_type": response_type,
            "task_path": tp,
            "source": raw.get("source") or source or "unknown",
            "priority": int(raw.get("priority") or 50),
            "created": raw.get("created") or now,
            "status": "pending",
            "comment": raw.get("comment") or "",
        }
        if options:
            record["options"] = options
        items.append(record)
        known.add(did)
        added += 1
    save_open(items)
    return added, skipped


def load_resolved_ids(months: int = 3) -> set[str]:
    """直近 months ヶ月の resolved から id を集める（同じ問いの復活を防ぐ）。

    「状況が変わって判断をやり直す」場合は question を書き直せば別 id になるので、
    ここで弾かれることはない（＝やり直し自体は禁止していない）。
    """
    ids: set[str] = set()
    if not RESOLVED_DIR.is_dir():
        return ids
    files = sorted(RESOLVED_DIR.glob("*.jsonl"), reverse=True)[:months]
    for f in files:
        try:
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    ids.add(json.loads(line)["id"])
                except (json.JSONDecodeError, KeyError):
                    continue
        except OSError:
            continue
    return ids


def _append_resolved(item: dict) -> None:
    RESOLVED_DIR.mkdir(parents=True, exist_ok=True)
    f = RESOLVED_DIR / f"{date.today().strftime('%Y-%m')}.jsonl"
    with f.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(item, ensure_ascii=False) + "\n")


# ダッシュボードUIが英語(i18n)の場合、tt()がJS内の '承認'/'却下' 等のリテラルまで
# 翻訳してしまい 'Approve'/'Reject' が届く（言語非依存の内部コードとして dashboard_decisions.py
# 側で送るよう2026-09-14に是正済みだが、念のためサーバー側でも両方を受理できるようにする）。
_CHOICE_ALIASES = {
    "approve": "承認", "reject": "却下", "hold": "保留",
    "comment": "コメント", "delete": "削除", "select": "選択", "answer": "回答",
}


def apply_choice(dec_id: str, choice: str, comment: str = "",
                 selected_option: str = "", answer: str = "") -> dict | None:
    """押下結果を open.json に反映する。戻り値は対象の1件（見つからなければ None）。

    承認/却下         → resolved/ へ移して open から消す
    コメント（本文あり） → 承認/却下と同じく resolved/ へ移す（ユーザーにとってコメント＝判断済みのため）
    選択              → options の id を selected_option に保存して resolved/ へ移す
    回答              → 自由記述を answer に保存して resolved/ へ移す
    保留              → open に残し status="deferred"
    削除              → resolved/ へ移して open から消す（status="deleted"）
    """
    choice = _CHOICE_ALIASES.get(choice, choice)
    items = load_open()
    hit = next((d for d in items if d["id"] == dec_id), None)
    if hit is None:
        return None
    if comment:
        hit["comment"] = comment.strip()
    now = datetime.now().strftime("%Y-%m-%dT%H:%M")
    if choice == "選択":
        option_id = str(selected_option or "").strip()
        option = next((o for o in hit.get("options", [])
                       if o.get("id") == option_id), None)
        if option is None:
            return None
        hit["selected_option"] = option["id"]
        hit["selected_label"] = option["label"]
        hit["status"] = "選択"
        hit["resolved"] = now
        _append_resolved(hit)
        save_open([d for d in items if d["id"] != dec_id])
    elif choice == "回答":
        answer_text = str(answer or comment or "").strip()
        if not answer_text:
            return None
        if hit.get("response_type") == "datetime":
            try:
                datetime.strptime(answer_text, "%Y-%m-%d %H:%M")
            except ValueError:
                return None
            hit["session_date"], hit["session_time"] = answer_text.split(" ", 1)
        hit["answer"] = answer_text
        hit["status"] = "回答"
        hit["resolved"] = now
        _append_resolved(hit)
        save_open([d for d in items if d["id"] != dec_id])
    else:
        is_commented = choice == "コメント" and bool(hit.get("comment"))
        if choice in RESOLVING_CHOICES or is_commented or choice == "削除":
            hit["status"] = "承認" if choice == "承認" else ("却下" if choice == "却下" else ("削除" if choice == "削除" else "コメント"))
            hit["resolved"] = now
            _append_resolved(hit)
            save_open([d for d in items if d["id"] != dec_id])
        else:
            if choice == "保留":
                hit["status"] = "deferred"
                today_s = date.today().isoformat()
                # 同じ日に2回押しても1回と数える（画面を往復しただけで加算しない）
                if hit.get("deferred_at") != today_s:
                    hit["deferred_count"] = int(hit.get("deferred_count") or 0) + 1
                hit.setdefault("first_deferred_at", today_s)
                hit["deferred_at"] = today_s
            else:
                return None
            save_open(items)
    return hit


def for_audio(limit: int = 3) -> list[dict]:
    """音声で読む決裁（確定仕様: 最大3件）。保留中のものは今日は読まない。"""
    today = date.today().isoformat()
    live = [d for d in load_open()
            if not (d.get("status") == "deferred" and d.get("deferred_at") == today)]
    return live[:limit]


def pending_count() -> int:
    """フォーカス帯に出す「⚖️ 決裁 N件」。今日保留したものは数に入れない。"""
    return len(for_audio(limit=10_000))


PROPOSED_FILE = DEC_DIR / "proposed.json"


def merge_proposed(path: Path = PROPOSED_FILE) -> tuple[int, int]:
    """3時間便の LLM が書いた提案ファイルを open.json へ取り込む。

    LLM に open.json を直接書かせない理由: 読んで→考えて→書くの間にユーザーがボタンを押すと
    その押下を巻き戻してしまう（ダッシュボードも同じファイルを書くため）。提案は別ファイルに
    出させ、採番・重複排除・マージはここ（Python）で行う。
    """
    items = _read_json(path, [])
    if not isinstance(items, list):
        print(f"[decisions] 提案ファイルが配列でない: {path}")
        return 0, 0
    added, skipped = add(items, source="inbox_monitor")
    try:
        path.unlink()  # 取り込んだら消す（次便が古い提案を再取り込みしないように）
    except OSError:
        pass
    return added, skipped


if __name__ == "__main__":
    import argparse
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="決裁ストアの確認とマージ")
    ap.add_argument("--merge", action="store_true",
                    help="proposed.json を open.json へ取り込む（3時間便から呼ばれる）")
    a = ap.parse_args()
    if a.merge:
        n_add, n_skip = merge_proposed()
        print(f"[decisions] 取り込み {n_add}件 / 既知でスキップ {n_skip}件 / "
              f"未決裁 合計 {len(load_open())}件")
    else:
        open_items = load_open()
        print(f"未決裁 {len(open_items)}件 / 音声で読む {len(for_audio())}件 / "
              f"resolved 既知 {len(load_resolved_ids())}件")
        for d in open_items:
            mark = "⏸" if d.get("status") == "deferred" else "・"
            print(f" {mark} [{d['id']}] p{d.get('priority')} {d['question'][:60]}")
