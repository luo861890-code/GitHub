# -*- coding: utf-8 -*-
"""GeoToken 矢量要素 Token 化测试（计划 4.1）"""
from app.services.geotoken_service import GeoTokenService


def test_tokenize_features():
    svc = GeoTokenService()
    features = [
        {"coordinates": [30.59, 114.30]},
        {"geometry": {"coordinates": [[30.59, 114.30], [30.60, 114.31], [30.61, 114.32]]}},
    ]
    result = svc.tokenize_features(features)
    assert result["count"] == 2
    assert result["tokens"]
    assert result["vocab_size"] > 0
