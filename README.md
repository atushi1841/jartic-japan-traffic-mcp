# JARTIC Japan Traffic Volume MCP Server

![Smithery](https://smithery.ai/badge/atushi1841/jartic-japan-traffic)
![MCP Registry](https://img.shields.io/badge/MCP-Registry-orange)

**JARTIC (日本道路交通情報センター) 交通量データ — MCP サーバー**

AIエージェント（Claude, Cursor, VS Code等）から日本の国道・高速道路のリアルタイム交通量データを取得できるModel Context Protocolサーバーです。

## 特徴

- **2,600+ 地点**のリアルタイム交通量データ
- 国土交通省 xROAD 常時観測交通量（国管理道路）API連携
- 5分間/1時間単位で詳細な交通流分析が可能
- 大型/小型/判別不能車両を方向別（上り/下り）に取得

## インストール

### Smithery経由（推奨）
```bash
npx -y @smithery/cli install atushi1841/jartic-japan-traffic
```

### ローカル設定（Claude Desktop/Cursor）
```json
{
  "mcpServers": {
    "jartic-japan-traffic": {
      "command": "/mnt/d/Project2/kensho/.venv/bin/python3",
      "args": ["/path/to/jartic-japan-traffic-mcp/server.py"]
    }
  }
}
```

## Tools

### `get_traffic`
交通量データをバウンディングボックスで取得

```python
result = await mcp.call_tool("get_traffic", {
    "layer": "1h_fixed",           # 5m_fixed | 1h_fixed | 5m_cctv | 1h_cctv
    "lat_min": 35.5, "lon_min": 139.5,
    "lat_max": 35.8, "lon_max": 140.0,
    "hours_back": 24,              # 過去何時間
    "limit": 50
})
```

**戻り値例:**
```json
{
  "station_code": 3110010,
  "upbound": {
    "small": 1500,
    "large": 200,
    "unknown": 50,
    "total": 1750
  },
  "downbound": {
    "small": 800,
    "large": 150,
    "unknown": 30,
    "total": 980
  },
  "longitude": 139.7049,
  "latitude": 35.5855
}
```

### `get_traffic_station`
特定の観測地点（常時観測点コード）の時系列データを取得

```python
result = await mcp.call_tool("get_traffic_station", {
    "station_code": 3110010,
    "hours_back": 24
})
```

### `get_layer_info`
利用可能なデータレイヤのメタ情報を取得

## レイヤ説明

| レイヤ名 | 種類 | 粒度 | 保持期間 |
|---------|------|------|---------|
| `5m_fixed` | 常設トラカン | 5分間 | 過去1ヶ月 |
| `1h_fixed` | 常設トラカン | 1時間 | 過去3ヶ月 |
| `5m_cctv` | CCTVトラカン | 5分間 | 過去1ヶ月 |
| `1h_cctv` | CCTVトラカン | 1時間 | 過去3ヶ月 |

## 使用例

### ルート最適化AIエージェント向け
```python
# 東京周辺の中古車配送最適化
traffic = await mcp.call_tool("get_traffic", {
    "lat_min": 35.5, "lon_min": 139.5,
    "lat_max": 35.8, "lon_max": 140.0,
    "hours_back": 6
})
# 各地点の交通量から渋滞予測に活用
```

### 物流計画
```python
# 貨物輸送の所要時間見積もり
station_data = await mcp.call_tool("get_traffic_station", {
    "station_code": 3110010,
    "hours_back": 168  # 1週間
})
# 時間帯別の平均交通量から最適通過時間を算出
```

## 関連プロジェクト

- [Kensho](https://github.com/atushi1841/kensho) — X（Twitter）懸賞自動化
- [japan-ec-mcp](https://github.com/atushi1841/japan-ec-mcp) — 日本EC検索MCP
- [mlit-property-hazard-mcp](https://github.com/atushi1841/mlit-property-hazard-mcp) — MLIT不動産・ハザードMCP

## データソース

- **JARTIC 交通量API**: https://www.jartic-open-traffic.org/
- **xROAD 道路データプラットフォーム**: https://www.xroad.mlit.go.jp/
- **利用規約**: [JARTIC API利用規約](https://www.jartic-open-traffic.org/) を必ずご確認ください

## License

MIT License — Kensho project (atushi1841)
