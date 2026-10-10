#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai_lane.py — タスクの「AIレーン」を毎回導出する（保存しない）判定エンジン。

2026-09-04 新設。それまでの `ai_judgment_ok`（frontmatter に固定保存する真偽値）を置き換える。

■ なぜ保存をやめたか
  旧 `ai_judgment_ok` は 2026-08-06 に定義が「判断を任せてよいか（許可）」から
  「AIが単独で完了まで持っていけるか（能力）」へ変わっていた。能力は状況で変わる
  （下ごしらえが済めば次の一手は変わる／Tier A の顔ぶれが変われば変わる）ため、
  ファイルに固定値で書くと必ず陳腐化する。実際 2026-08-06 に12件の一括修正が発生した。
  さらに「ユーザーが意識しないところでAIが書き換える値」になっており、ユーザーの意思表示と
  混同されていた（2026-09-04 ユーザーの指摘）。

■ 分けたもの
  許可（ユーザーだけが決める・保存する）   … frontmatter `human_only: true` の1個だけ。
                                        未記入がデフォルト＝AIが進めてよい（オプトアウト方式）。
  能力（AIが決める・保存しない）     … 本モジュールが毎回導出する lane / runner。

■ オプトアウトを安全にするための自動ガード
  「拒否だけマークする」方式は、マークを忘れた時に事故る。そこでフラグに依存せず
  非公開Area・内省・物理行動・お金/健康/外部送信の最終アクションを機械判定で常に止める。
  ユーザーが `human_only` を手で立てるのは、この網から漏れた例外だけでよい。
  （AGENTS.md §📜 ルール2「代筆禁止ゾーン」・3「お金・健康・外部送信は人間確認必須」を
   フラグではなく実装で担保する、という位置づけ）

■ 返す値
  lane   : 'ai'    🤖 AIが完了まで持っていける
           'prep'  🤝 下ごしらえはAI・最終判断はユーザー（お金/健康/外部送信の直前で止める）
           'human' 🧠 ユーザーしかできない（AIは触らない）
  runner : lane が 'ai'/'prep' のときの実行主体
           'dispatch' … 12:30 ディスパッチ便が実行できる（Tier A エージェントが担当に入っている）
           'session'  … 本体セッションで拾う（実装・インフラ系。Tier A に実装担当がいないため）
           ''         … lane が 'human' のとき
  reason : なぜそのレーンになったかの一言（画面にそのまま出す）

使い方:
    import ai_lane
    r = ai_lane.classify(fm)          # fm は frontmatter の dict
    r["lane"], r["runner"], r["reason"]

CLI:
    python ai_lane.py --report        # 活きているタスクのレーン内訳を出す（検証用・書き込みなし）
    python ai_lane.py --list ai       # 指定レーンのタスクを一覧
    python ai_lane.py --migrate       # ai_judgment_ok → human_only 移行（--apply で実書き込み）
"""

import argparse
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shuki_paths  # noqa: E402
import shuki_profile  # noqa: E402  (非公開Area・呼び名などの個人の値。2026-09-27)

VAULT = shuki_paths.VAULT  # 絶対パスの直書きをやめた（2026-09-27）
TASK_PREFIX = "04_Tasks/タスク管理/タスク/"

# Tier A（自律実行できるエージェント）。orchestrator.md §🚚 が正。
TIER_A = ("finance", "knowledge", "english", "researcher")

# 旧 `agent: 人間（ユーザー）` は human_only へ移行した後も互換のため人間指定として読む。
HUMAN_AGENT_VALUES = ("人間（ユーザー）", "人間(ユーザー)", "ユーザー", "人間")


def _norm(v):
    """frontmatter値を判定用の1本の文字列に潰す（リストも連結する）。"""
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return " ".join(str(x) for x in v)
    return str(v)


# ── 自動ガード（フラグ非依存・常に効く） ─────────────────────────
# 並び順が優先順。上にあるものほど強い。

# 🧠 human 直行：AIが関与すべきでない／関与しても完了に近づかないもの
GUARD_HUMAN = [
    # 非公開Area（profile.json で private:true）は代筆禁止ゾーン（AGENTS.md §📜 ルール2）。
    # 事実整理でも本人の言葉が要るためレーンとしては human に置き、必要なら /scan・/cbt 等の
    # 対話スキルで進める。**値は profile.json 側**（2026-09-27）。
    *[(re.escape(a), "area", f"{a}（代筆禁止ゾーン）") for a in shuki_profile.private_areas()],
    # 内省・言語化。完了条件が「ユーザーが自分の言葉で書いた状態」なのでAIでは完了不能。
    (r"深掘りする|リフレクション|自分の言葉|内省|言語化|反省タイム|CBT|自己理解する",
     "text", "ユーザーの内省・言語化が完了条件"),
    # 物理行動・本人確認。AIの下ごしらえが実質ゼロ（2026-08-06 に12件を false へ戻した判断）。
    (r"来店|店舗で|対面|受験|受診|通院|面接|訪問|撮影|録画|参加する|行ってくる",
     "text", "ユーザーの身体・対面が要る行動"),
    # 学習・訓練。教材調査はAIが手伝えるが「習得した状態」はAIでは作れない。
    # 「読了・読む」は 2026-09-04 の12:30便が取りこぼしを報告して追加（小説『誰が勇者を殺したか』が
    # ai レーンに入った。next_action が「読了して感想をメモする」＝読むこと自体が完了条件）。
    (r"学習|勉強|習得|練習|トレーニング|を学ぶ|覚える|読了|読む|読書|視聴", "text", "ユーザー自身の学習・訓練"),
    # ユーザーの記憶を引き出す仕事（/recall・/scan の領分）。AIは素材を持っていない。
    (r"思い出|回想|記憶を", "text", "ユーザーの記憶の想起が要る"),
]

# 🤝 prep：下ごしらえはAIが進めてよいが、最終アクションの直前で止める
# （orchestrator.md §🚚 2026-08-07 の例外条項をそのまま実装に落としたもの）
GUARD_PREP = [
    (r"購入|買う|発注|注文|送金|振込|解約|契約|申し込|支払|課金|入金",
     "text", "お金の最終アクションを含む（下ごしらえまで）"),
    (r"投稿|送信|連絡する|催促|メール|DM|カレンダーに|GCal|公開する|申請",
     "text", "外部送信を含む（下ごしらえまで）"),
    (r"服薬|診断|健康診断|検査", "text", "健康ゾーン（下ごしらえまで）"),
    (None, "area_money_health", "お金・健康Area（下ごしらえまで）"),
]

# 本体セッションで拾う仕事（Tier A に実装担当がいないため便に載せられない）。
# orchestrator.md §🧱（2026-08-06）と §Tier B 担当タスクの完了経路（2026-08-30 決裁）が正。
IMPL_RE = re.compile(
    r"実装|スクリプト|リファクタ|バグ|不具合|修正する|移行する|配線|コード|"
    r"ダッシュボード|サーバー|API|デバッグ|原因を調査|セットアップ|構成に移行|削除する|試作する"
)


def _hit(patterns, text, area):
    """ガード表を順に当てる。ヒットしたら理由を返す。"""
    for pat, scope, reason in patterns:
        if scope == "area":
            if re.search(pat, area):
                return reason
        elif scope == "area_money_health":
            if re.search(r"お金|健康", area):
                return reason
        else:  # text（タイトル＋next_action＋completion_criteria）
            if re.search(pat, text):
                return reason
    return None


def classify(fm, title=None):
    """frontmatter dict から lane / runner / reason を導出する。副作用なし。

    fm に期待するキー: title / next_action / completion_criteria / area / agent / human_only
    （どれも欠けていてよい。欠けていれば空として扱う）
    """
    title = title or _norm(fm.get("title"))
    area = _norm(fm.get("area"))
    agent = _norm(fm.get("agent")).strip().strip('"')
    text = " ".join([title,
                     _norm(fm.get("next_action")),
                     _norm(fm.get("completion_criteria"))])

    human_only = fm.get("human_only")
    if isinstance(human_only, str):
        human_only = human_only.strip().strip('"').lower() == "true"

    # ① ユーザーの明示指定が最優先（オプトアウト）
    if human_only is True:
        return {"lane": "human", "runner": "", "reason": "ユーザーが「自分でやる」を指定"}

    # ② 自動ガード（マークし忘れても止まる）
    r = _hit(GUARD_HUMAN, text, area)
    if r:
        return {"lane": "human", "runner": "", "reason": r}

    # ③ 旧データ互換：agent: 人間（ユーザー）は人間指定として尊重する。
    #    移行後は human_only へ寄せるが、書き換え前でも誤ってAIに流れないようにする。
    if agent in HUMAN_AGENT_VALUES:
        return {"lane": "human", "runner": "", "reason": "agent が人間指定（旧形式）"}

    prep = _hit(GUARD_PREP, text, area)
    lane = "prep" if prep else "ai"
    reason = prep or "AIが完了まで進められる"

    # ④ 実行主体。Tier A が担当に入っていれば 12:30 便が拾える。
    if agent in TIER_A:
        runner = "dispatch"
    elif IMPL_RE.search(text):
        runner = "session"
        reason += "（実装系＝本体セッションで実行）"
    else:
        # 担当未定。便は agent を見て拾うので、このままでは誰も実行しない。
        runner = "session"
        reason += "（担当未定＝本体セッションで実行）"

    return {"lane": lane, "runner": runner, "reason": reason}


LANE_LABEL = {"ai": "🤖 AIが進める", "prep": "🤝 下ごしらえはAI", "human": "🧠 ユーザーのみ"}
RUNNER_LABEL = {"dispatch": "12:30便", "session": "本体セッション", "": ""}


# ── CLI（検証・移行用。ライブラリとして使う分にはここから下は不要） ──────────

def _load_tasks():
    """活きているタスク（todo / in-progress）を [(path, fm, name)] で返す。"""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import vault_index
    idx = vault_index.VaultIndex()
    idx.refresh()
    out = []
    for rec in idx.notes():
        if not rec["path"].startswith(TASK_PREFIX):
            continue
        fm = rec["fm"]
        if _norm(fm.get("status")).strip().strip('"') not in ("todo", "in-progress"):
            continue
        out.append((rec["path"], fm, rec["name"]))
    return out


def cmd_report():
    from collections import Counter
    tasks = _load_tasks()
    c = Counter()
    for path, fm, name in tasks:
        r = classify(fm, title=name)
        c[(r["lane"], r["runner"])] += 1
    print("活きているタスク: %d件" % len(tasks))
    for lane in ("ai", "prep", "human"):
        total = sum(v for (l, _), v in c.items() if l == lane)
        detail = ["%s:%d" % (RUNNER_LABEL[rn], v)
                  for (l, rn), v in sorted(c.items()) if l == lane and rn]
        tail = ("   [" + " / ".join(detail) + "]") if detail else ""
        print("  %-14s %3d件%s" % (LANE_LABEL[lane], total, tail))
    return 0


def runnable(kind="dispatch"):
    """今すぐ実行できるタスクを [(path, title, lane, agent)] で返す。

    条件（12:30便の手順1と同じ）:
      - lane が ai / prep（human は除く）
      - runner が指定の kind（既定 dispatch＝Tier A が担当に入っていて便が実行できる）
      - start が未来日でない（意図的な先延ばしを尊重・フォーカス・ファネル原則）
    定期便の起動判定（キューが空なら claude を起動しない）と補充判定に使う。
    """
    from datetime import date as _date
    today = _date.today().isoformat()
    out = []
    for path, fm, name in _load_tasks():
        r = classify(fm, title=name)
        if r["lane"] == "human" or r["runner"] != kind:
            continue
        start = _norm(fm.get("start")).strip().strip('"')[:10]
        if start and start > today:
            continue
        out.append((path, name, r["lane"], _norm(fm.get("agent")).strip().strip('"')))
    return out


def cmd_queue(kind, as_json):
    q = runnable(kind)
    if as_json:
        import json
        print(json.dumps([{"path": p, "title": t, "lane": l, "agent": a} for p, t, l, a in q],
                         ensure_ascii=False))
    else:
        print("実行可能（runner=%s）: %d件" % (kind, len(q)))
        for p, t, l, a in q:
            print("  %-5s %-11s %s" % (l, a or "(担当未定)", t))
    return 0


def cmd_list(lane):
    for path, fm, name in sorted(_load_tasks()):
        r = classify(fm, title=name)
        if lane != "all" and r["lane"] != lane:
            continue
        print("%-5s %-7s %s  <- %s" % (r["lane"], RUNNER_LABEL[r["runner"]], name, r["reason"]))
    return 0


def cmd_migrate(apply_):
    """ai_judgment_ok と `agent: 人間（ユーザー）` を落とす。human_only は立てない。

    活きているタスクだけが対象（done/archived は歴史なので触らない）。

    ■ human_only を機械的に立てない理由（2026-09-04 ユーザーの設計判断）
      旧 `agent: 人間（ユーザー）` は「AIが完了まで持っていけない（＝能力）」の意味で付いた
      ものが大半で、ユーザーの「やってほしくない」という意思表示ではない。これを一括で
      human_only へ写すと、55件中25件に手動マークが付いた状態から始まる＝オプトアウト
      方式にした意味が消える。よってここでは落とすだけにして、止めるべきものは
      自動ガード（GUARD_HUMAN / GUARD_PREP）に任せ、ガードから漏れた例外だけを
      ユーザーが /board のAIレーン画面で「🧠 自分でやる」を押して立てる。

    ■ 開放しても実行が暴走しない理由
      12:30 ディスパッチ便が拾うのは `agent:` に Tier A が入っているものだけ。
      本移行で agent を空にしたタスクは runner='session'（本体セッション待ち）となり、
      便の対象にはならない。つまり本移行で変わるのは「画面での見え方」であって、
      無人実行の範囲は変わらない。
    """
    changed = []
    for path, fm, name in _load_tasks():
        p = VAULT / path
        text = io.open(p, encoding="utf-8").read()
        m = re.match(r"^---\n(.*?)\n---", text, re.S)
        if not m:
            continue
        fm_text = m.group(1)
        if not re.search(r"^ai_judgment_ok:", fm_text, re.M):
            continue

        agent = _norm(fm.get("agent")).strip().strip('"')
        area = _norm(fm.get("area"))
        body_text = " ".join([name, _norm(fm.get("next_action")),
                              _norm(fm.get("completion_criteria"))])
        guarded = _hit(GUARD_HUMAN, body_text, area) is not None

        new_fm = re.sub(r"^ai_judgment_ok:.*\n", "", fm_text + "\n", flags=re.M).rstrip("\n")
        # agent の人間指定は「担当」ではなく「AIにやらせない」の代用として使われていた。
        # その役割は human_only とガードへ移したので落とす（agent は AI 側の担当指定に純化）。
        if agent in HUMAN_AGENT_VALUES:
            new_fm = re.sub(r"^agent:.*\n", "", new_fm + "\n", flags=re.M).rstrip("\n")

        changed.append((path, guarded))
        if apply_:
            io.open(p, "w", encoding="utf-8").write(
                text[:m.start()] + "---\n" + new_fm + "\n---" + text[m.end():])

    print(("適用" if apply_ else "ドライラン") + ": %d件" % len(changed))
    print("  ガードで自動的に human … %d件（ユーザーのマーク不要）" % sum(1 for _, g in changed if g))
    print("  AI側へ開放             … %d件" % sum(1 for _, g in changed if not g))
    if not apply_:
        print("\n--apply を付けると実際に書き込みます")
    return 0


def main():
    ap = argparse.ArgumentParser(description="タスクのAIレーンを導出する")
    ap.add_argument("--report", action="store_true", help="レーン内訳を出す")
    ap.add_argument("--list", metavar="LANE", help="ai / prep / human / all の一覧")
    ap.add_argument("--queue", metavar="RUNNER", nargs="?", const="dispatch",
                    help="今すぐ実行できるタスク（dispatch / session）")
    ap.add_argument("--json", action="store_true", help="--queue の出力をJSONにする")
    ap.add_argument("--migrate", action="store_true", help="ai_judgment_ok → human_only 移行")
    ap.add_argument("--apply", action="store_true", help="--migrate を実際に書き込む")
    a = ap.parse_args()
    if a.report:
        return cmd_report()
    if a.queue:
        return cmd_queue(a.queue, a.json)
    if a.list:
        return cmd_list(a.list)
    if a.migrate:
        return cmd_migrate(a.apply)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
