"""Offline-only realized-equity performance tracking. No trading or optimization."""
from dataclasses import dataclass, field
from math import isfinite


@dataclass
class PerformanceTracker:
    initial_equity: float
    equity: float = field(init=False)
    peak: float = field(init=False)
    max_drawdown_pct: float = 0.0
    wins: int = 0
    losses: int = 0
    breakeven: int = 0
    consecutive_losses: int = 0
    longest_losing_streak: int = 0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    records: list = field(default_factory=list)

    def __post_init__(self):
        if isinstance(self.initial_equity, bool) or not isinstance(self.initial_equity, (int, float)) or not isfinite(self.initial_equity) or self.initial_equity <= 0:
            raise ValueError("initial_equity must be finite and positive")
        self.equity = float(self.initial_equity)
        self.peak = self.equity

    def record_closed_trade(self, net_pnl: float) -> None:
        """Record a fully closed trade's net realized P&L, after all fees."""
        if isinstance(net_pnl, bool) or not isinstance(net_pnl, (int, float)) or not isfinite(net_pnl):
            raise ValueError("net_pnl must be finite")
        new_equity = self.equity + net_pnl
        if not isfinite(new_equity) or new_equity < 0:
            raise ValueError("invalid resulting equity")
        self.equity = new_equity
        self.peak = max(self.peak, self.equity)
        self.max_drawdown_pct = max(self.max_drawdown_pct, 100 * (self.peak - self.equity) / self.peak)
        if net_pnl > 0:
            self.wins += 1
            self.gross_profit += net_pnl
            self.consecutive_losses = 0
        elif net_pnl < 0:
            self.losses += 1
            self.gross_loss += -net_pnl
            self.consecutive_losses += 1
            self.longest_losing_streak = max(self.longest_losing_streak, self.consecutive_losses)
        else:
            self.breakeven += 1
            self.consecutive_losses = 0
        self.records.append(float(net_pnl))

    @property
    def win_rate_pct(self) -> float:
        decisive = self.wins + self.losses
        return 100 * self.wins / decisive if decisive else 0.0

    @property
    def profit_factor(self) -> float | None:
        return self.gross_profit / self.gross_loss if self.gross_loss else None

    @property
    def return_pct(self) -> float:
        return 100 * (self.equity / self.initial_equity - 1)
