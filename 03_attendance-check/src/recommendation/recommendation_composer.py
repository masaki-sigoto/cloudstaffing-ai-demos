"""推奨アクション文を生成（既定辞書）。"""

from __future__ import annotations

DEFAULT_ACTIONS = {
    "A-01": "スタッフ本人に退勤時刻を確認し、打刻訂正申請を起票",
    "A-02": "スタッフ本人に出勤時刻を確認し、打刻訂正申請を起票",
    "A-03": "休憩時間の実態をスタッフに確認、不足時は是正指導",
    "A-04": "シフト・打刻の再確認、労務リスク要確認（派遣元労務へエスカレーション）",
    "A-05": "分割勤務の妥当性を確認、通常運用なら据え置き",
    "A-06": "休暇取消または打刻削除／残業申請をスタッフ・派遣先承認者と調整",
    "A-07": "派遣先承認者に承認処理を督促（pending滞留）",
    "A-08": "シフト外深夜打刻の理由を確認、必要なら労務へ相談",
    "A-09": "シフト予定との乖離理由を確認、シフト修正要否を判断",
    "A-10": "どちらが正しい打刻かスタッフ本人に確認",
}


class RecommendationComposer:
    def __init__(self, use_llm: bool = False) -> None:
        self.use_llm = use_llm

    def compose(self, scored: list) -> list:
        for sf in scored:
            sf.recommended_action = DEFAULT_ACTIONS.get(
                sf.primary.pattern_id, "内容を確認のうえ対応判断"
            )
        return scored
