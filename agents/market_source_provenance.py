"""Allowlisted venue/product provenance, carried separately from model claims."""
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
