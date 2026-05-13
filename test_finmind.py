import requests

TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiZnVuZC1hbmFseXN0IiwiZW1haWwiOiJkb3JpczA3MDcxNEBnbWFpbC5jb20iLCJ0b2tlbl92ZXJzaW9uIjowfQ.lSrR76i3BYLvAyWoXTNGRE86NP0x4_lbowZgr_ctT_c"  # ← 換這裡
BASE  = "https://api.finmindtrade.com/api/v4/data"

resp = requests.get(BASE, params={
    "dataset":    "TaiwanStockPrice",
    "data_id":    "0050",
    "start_date": "2024-01-01",
    "token":      TOKEN,
})
data = resp.json()
print("第一筆：", data["data"][0] if data.get("data") else data)