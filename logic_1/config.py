"""バックテストで共有する設定と銘柄一覧。"""

from dataclasses import dataclass, field
from datetime import date
from math import isfinite


SECTORS: dict[str, str] = {
    "1617.T": "食品",
    "1618.T": "エネルギー資源",
    "1619.T": "建設・資材",
    "1620.T": "素材・化学",
    "1621.T": "医薬品",
    "1622.T": "自動車・輸送機",
    "1623.T": "鉄鋼・非鉄",
    "1624.T": "機械",
    "1625.T": "電機・精密",
    "1626.T": "情報通信・サービスその他",
    "1627.T": "電力・ガス",
    "1628.T": "運輸・物流",
    "1629.T": "商社・卸売",
    "1630.T": "小売",
    "1631.T": "銀行",
    "1632.T": "金融（除く銀行）",
    "1633.T": "不動産",
}
BENCHMARK = "^N225"


@dataclass(frozen=True)
class BacktestConfig:
    """戦略パラメータと対象期間を一か所で保持する。"""

    start: date | None = None
    end: date | None = None
    initial_cash: float = 500_000.0
    top_n: int = 3
    momentum_weights: dict[int, float] = field(
        default_factory=lambda: {3: 0.50, 6: 0.30, 12: 0.20}
    )

    def validate(self) -> None:
        """計算不能な設定値を実行前に拒否する。"""
        if self.start and self.end and self.start > self.end:
            raise ValueError("--start は --end 以前に指定してください")
        if not isfinite(self.initial_cash) or self.initial_cash <= 0:
            raise ValueError("--initial-cash は正の値にしてください")
        if not 1 <= self.top_n <= len(SECTORS):
            raise ValueError(f"--top-n は1から{len(SECTORS)}の範囲にしてください")
        if not self.momentum_weights or any(
            months <= 0 or not isfinite(weight) or weight < 0
            for months, weight in self.momentum_weights.items()
        ):
            raise ValueError("モメンタム期間とウェイトを確認してください")
        if abs(sum(self.momentum_weights.values()) - 1.0) > 1e-9:
            raise ValueError("モメンタムウェイトの合計は1にしてください")
