import requests, time, csv
from datetime import datetime
import pandas as pd
from pathlib import Path

url = "https://buscatch.jp/rt3/unko_map_simple.ajax.php"
data = {"id": "chitetsu_train", "command": "get_unko_list", "rosen_group_id": "2235"}
headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}

# 車両ID → 編成名の対応表
id_map = {
    "1001": "デ7011編成",
    "1002": "デ7012編成",
    "2001": "デ7021編成"
}

# 編成順を定義（未知IDは最後）
formation_order = ["デ7011編成", "デ7012編成", "デ7021編成"]

# === 時刻表CSVの読み込み ===
year = 2025
base_dir = Path(f"data/{year}")

# 6ファイルをまとめて読み込む
timetable = []
for csv_file in base_dir.glob("timetable2025W_*.csv"):
    df = pd.read_csv(csv_file)
    # 各行を辞書化（列名は "列1","列2",... になっている想定）
    for idx, row in df.iterrows():
        for col in df.columns:
            val = str(row[col]).strip()
            if val and val != "nan":
                timetable.append({
                    "train_number": f"{csv_file.stem}_{idx}_{col}",  # 仮の番号付与
                    "station": col,   # 列名を駅名に対応させる場合はここを調整
                    "time": val
                })

def find_train_number(station, timestamp):
    ts = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
    for row in timetable:
        if row["station"] == station:
            try:
                tt = datetime.strptime(row["time"], "%H:%M").replace(
                    year=ts.year, month=ts.month, day=ts.day
                )
                if abs((ts - tt).total_seconds()) <= 300:  # ±5分以内なら一致
                    return row["train_number"]
            except ValueError:
                continue
    return ""

date_str = datetime.now().strftime("%Y-%m-%d")
csv_file = f"train_log_with_number_test_{date_str}.csv"

# ヘッダ行
with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "vehicle_id", "formation_name", "headsign", "station", "train_number"])

# 試験用: 2〜3回だけ実行
interval_seconds = 30
max_runs = 3

for run in range(max_runs):
    now = datetime.now()
    try:
        response = requests.post(url, headers=headers, data=data, timeout=10)
        response.raise_for_status()
        trains = response.json()
    except Exception as e:
        print(f"[{now}] エラー発生: {e}")
        time.sleep(interval_seconds)
        continue

    sorted_trains = sorted(
        trains,
        key=lambda t: formation_order.index(id_map.get(str(t.get("vehicle_id")), f"ID:{t.get('vehicle_id')}"))
        if id_map.get(str(t.get("vehicle_id"))) in formation_order else len(formation_order)
    )

    with open(csv_file, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        for train in sorted_trains:
            vid = train.get("vehicle_id")
            formation = id_map.get(str(vid), f"ID:{vid}")
            timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
            train_number = find_train_number(train.get("teiryujo_name"), timestamp)
            writer.writerow([
                timestamp,
                vid,
                formation,
                train.get("headsign"),
                train.get("teiryujo_name"),
                train_number
            ])

    print(f"[{now}] データを保存しました ({len(sorted_trains)}件)")
    time.sleep(interval_seconds)

print("=== 保存結果 ===")
