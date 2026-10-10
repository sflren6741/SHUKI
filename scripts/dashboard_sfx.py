#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dashboard_sfx.py — 操作フィードバック用SE（GET /sfx.js の実体）

音源ファイルは持たない。Web Audio API のオシレーター（矩形波/正弦波）でその場に
生成する（8bit/チップチューン調・ユーザーの音楽の好みに合う・ライセンス確認が不要・
全13ページに音声ファイルを配信するコストがゼロ）。

「音を載せる価値がある操作」の判定基準・候補表は
04_Tasks/タスク管理/タスク/SHUKIダッシュボードにSE・専用BGMなど演出面の改修を検討する.md
が正（2026-08-21 ユーザー承認：1〜9番を実装、10番は見送り）。

ON/OFF は dashboard_settings.py の sfx_enabled（既定 true）。設定変更は次回ページ
読み込みから反映（/theme.css と同じ流儀・SPAでないためリアルタイム反映は不要）。
"""
import dashboard_settings


def sfx_js(settings=None):
    settings = settings or dashboard_settings.load_settings()
    enabled = "true" if settings.get("sfx_enabled", True) else "false"
    return f"""(function(){{
  const ENABLED = {enabled};
  let ctx = null;
  function ac() {{
    if (!ENABLED) return null;
    if (!ctx) {{
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return null;
      ctx = new AC();
    }}
    if (ctx.state === 'suspended') ctx.resume();
    return ctx;
  }}
  function tone(freq, dur, type, vol, delay) {{
    const c = ac();
    if (!c) return;
    try {{
      const t0 = c.currentTime + (delay || 0);
      const osc = c.createOscillator();
      const gain = c.createGain();
      osc.type = type || 'square';
      osc.frequency.setValueAtTime(freq, t0);
      gain.gain.setValueAtTime(0.0001, t0);
      gain.gain.linearRampToValueAtTime(vol, t0 + 0.012);
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
      osc.connect(gain).connect(c.destination);
      osc.start(t0);
      osc.stop(t0 + dur + 0.03);
    }} catch (e) {{ /* オーディオ不可の環境は無音のまま無視 */ }}
  }}
  window.SFX = {{
    // ① タスク完了（/board）— 達成の頂点。3音上昇
    task_complete: () => {{ tone(523.25, 0.09, 'square', 0.16, 0); tone(659.25, 0.09, 'square', 0.16, 0.08); tone(783.99, 0.18, 'square', 0.18, 0.16); }},
    // ② 対話ドックの応答完了 — 通知ベル。実用価値が最大（待ち時間が長い）
    chat_done: () => {{ tone(659.25, 0.08, 'sine', 0.14, 0); tone(880, 0.14, 'sine', 0.14, 0.08); }},
    // ③ メモ投函 — 「届いた」の単音ポップ
    memo_sent: () => {{ tone(698.46, 0.06, 'square', 0.12, 0); }},
    // ④ 決裁の承認 / 却下
    decision_approve: () => {{ tone(523.25, 0.06, 'square', 0.15, 0); tone(783.99, 0.13, 'square', 0.17, 0.06); }},
    decision_reject: () => {{ tone(392.0, 0.08, 'square', 0.13, 0); tone(261.63, 0.15, 'square', 0.13, 0.07); }},
    // ⑤ 概念カードの合成成立（/game）— 図鑑だけは盛ってよい場所。4音ファンファーレ
    fusion_success: () => {{ tone(523.25, 0.08, 'square', 0.17, 0); tone(659.25, 0.08, 'square', 0.17, 0.08); tone(783.99, 0.08, 'square', 0.17, 0.16); tone(1046.5, 0.22, 'square', 0.2, 0.24); }},
    // ⑥ 音声入力の開始 / 停止
    mic_start: () => {{ tone(440, 0.05, 'sine', 0.13, 0); tone(660, 0.07, 'sine', 0.13, 0.05); }},
    mic_stop: () => {{ tone(660, 0.05, 'sine', 0.11, 0); tone(440, 0.07, 'sine', 0.11, 0.05); }},
    // ⑦ 習慣ファネルで「集中」を選んだ時（/habit）— ①の弱いバージョン
    habit_check: () => {{ tone(587.33, 0.07, 'square', 0.12, 0); tone(880, 0.1, 'square', 0.12, 0.06); }},
    // ⑧⑨ レビュー済み・ニュース既読 — 連打されうるため極小音量の単音tick
    tick: () => {{ tone(500, 0.03, 'square', 0.05, 0); }},
    // 対話ドックの完了音等、ユーザージェスチャの時点でAudioContextを起こしておくための無音起動
    warm: () => {{ ac(); }},
  }};
}})();
"""
