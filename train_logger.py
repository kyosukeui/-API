import requests, time, csv
from datetime import datetime, timedelta

url = "https://buscatch.jp/rt3/unko_map_simple.ajax.php"
data = {"id": "chitetsu_train", "command": "get_unko_list", "rosen_group_id": "2235"}
headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}

# 車両ID → 編成名の対応表（未知IDは "ID:xxxx" として出力）
id_map = {
    "1001": "デ7011編成",
    "1002": "デ7012編成",
    "2001": "デ7021編成"
}

# 編成順を定義（未知IDは最後）
formation_order = ["デ7011編成", "デ7012編成", "デ7021編成"]

date_str = datetime.now().strftime("%Y-%m-%d")
csv_file = f"train_log_{date_str}.csv"

# ヘッダ行（utf-8-sigで保存 → Excel対応）
with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "vehicle_id", "formation_name", "headsign", "station"])

interval_minutes = 20  # 20分ごと

# 開始・終了時刻を決定
now = datetime.now()
today = now.date()
tomorrow = today + timedelta(days=1)

if 0 <= now.hour < 5:
    # 午前0時〜午前5時に起動した場合 → 当日5:00〜24:00
    start = datetime.combine(today, datetime.strptime("05:00", "%H:%M").time())
    end   = datetime.combine(today, datetime.strptime("24:00", "%H:%M").time())
else:
    # それ以外 → 翌日5:00〜24:00
    start = datetime.combine(tomorrow, datetime.strptime("05:00", "%H:%M").time())
    end   = datetime.combine(tomorrow, datetime.strptime("24:00", "%H:%M").time())

# 開始時刻まで待機
if now < start:
    wait_seconds = (start - now).total_seconds()
    print(f"Waiting until {start} to start collection...")
    time.sleep(wait_seconds)

# 20分ごとに収集
current = start
while current <= end:
    now = datetime.now()
    try:
        response = requests.post(url, headers=headers, data=data, timeout=10)
        response.raise_for_status()
        trains = response.json()
    except Exception as e:
        print(f"[{now}] エラー発生: {e}")
        time.sleep(interval_minutes * 60)
        continue

    # formation_name順にソート（未知IDは最後）
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
            writer.writerow([
                now.strftime("%Y-%m-%d %H:%M:%S"),
                vid,
                formation,
                train.get("headsign"),
                train.get("teiryujo_name")
            ])

    print(f"[{now}] データを保存しました ({len(sorted_trains)}件)")

    current += timedelta(minutes=interval_minutes)
    if current <= end:
        time.sleep(interval_minutes * 60)

print("=== 保存完了 ===")
