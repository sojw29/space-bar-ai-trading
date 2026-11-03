"""Allowlisted venue/product provenance, carried separately from model claims."""
from datetime import datetime, timezone
SOURCES = {
    'BYBIT_USDT_PERPETUAL_5M': 'Bybit USDT 무기한 · 5분봉 · 기초자산 거래량',
    'OKX_USDT_PERPETUAL_5M': 'OKX USDT 무기한 · 5분봉 · 기초자산 거래량',
}


def with_market_source(source, output):
    if 'market_source' in source:
        value = source['market_source']
        if not isinstance(value, str) or value not in SOURCES:
            raise ValueError('INVALID_MARKET_SOURCE')
        output['market_source'] = value
    return output


def validate_candle_batch(markets, captured):
    """A marked three-symbol snapshot must share one completed, fresh UTC 5m bar."""
    if captured.tzinfo is None or not isinstance(markets, list) or len(markets) != 3:
        raise ValueError('INVALID_CANDLE_BATCH')
    stamps = []
    for market in markets:
        value = market.get('last_completed_candle_utc') if isinstance(market, dict) else None
        if not isinstance(value, str):
            raise ValueError('INVALID_CANDLE_TIMESTAMP')
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError('INVALID_CANDLE_TIMESTAMP')
        stamp = stamp.astimezone(timezone.utc)
        if stamp.microsecond or stamp.second or stamp.minute % 5:
            raise ValueError('INVALID_CANDLE_TIMESTAMP')
        if not 0 <= (captured-stamp).total_seconds()-300 <= 3600:
            raise ValueError('STALE_OR_UNFINISHED_MARKET_CANDLE')
        stamps.append(stamp)
    if len(set(stamps)) != 1:
        raise ValueError('MISALIGNED_MARKET_CANDLES')
