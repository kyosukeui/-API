import requests, time, csv
from datetime import datetime

url = "https://buscatch.jp/rt3/unko_map_simple.ajax.php"
data = {"id": "chitetsu_train", "command": "get_unko_list", "rosen_group_id": "2235"}
headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}

# 車両ID → 編成名の対応表（未知IDは "ID:xxxx" として出力）
id_map = {
    "1001": "デ7011編成",
    "1002": "デ7012編成",
    "2001": "デ7021編成"
}

# 時刻表CSVを読み込む
timetable = []
with open("timetable.csv", "r", encoding="utf-8-sig") as tf:
    reader = csv.DictReader(tf)
    for row in reader:
        timetable.append(row)

def find_train_number(station, timestamp):
    """位置情報と時刻表を突き合わせて列車番号を返す"""
    ts = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
    for row in timetable:
        if row["station"] == station:
            tt = datetime.strptime(row["time"], "%H:%M").replace(
                year=ts.year, month=ts.month, day=ts.day
            )
            # ±5分以内なら一致とみなす
            if abs((ts - tt).total_seconds()) <= 300:
                return row["train_number"]
    return ""  # 未知なら空欄

date_str = datetime.now().strftime("%Y-%m-%d")
csv_file = f"train_log_with_number_{date_str}.csv"

# ヘッダ行（utf-8-sigで保存 → Excel対応）
with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "vehicle_id", "formation_name", "headsign", "station", "train_number"])

# 5:00〜24:00まで20分ごとに実行
start_hour, end_hour = 5, 24
interval_minutes = 20

while True:
    now = datetime.now()
    if now.hour < start_hour or now.hour >= end_hour:
        break  # 実行時間外なら終了

    try:
        response = requests.post(url, headers=headers, data=data, timeout=10)
        response.raise_for_status()
        trains = response.json()
    except Exception as e:
        print(f"[{now}] エラー発生: {e}")
        time.sleep(interval_minutes * 60)
        continue

    # formation_name順にソート（未知IDは最後）
    formation_order = ["デ7011編成", "デ7012編成", "デ7021編成"]
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
    time.sleep(interval_minutes * 60)
