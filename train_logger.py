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

date_str = datetime.now().strftime("%Y-%m-%d")
csv_file = f"train_log_{date_str}.csv"

# ヘッダ行（utf-8-sigで保存 → Excel対応）
with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "vehicle_id", "formation_name", "headsign", "station"])

# 30秒ごとに3回保存
for i in range(3):
    now = datetime.now()
    try:
        response = requests.post(url, headers=headers, data=data, timeout=10)
        response.raise_for_status()
        trains = response.json()
    except Exception as e:
        print(f"[{now}] エラー発生: {e}")
        time.sleep(30)
        continue

    # vehicle_id を数値に変換して昇順ソート
    sorted_trains = sorted(trains, key=lambda t: int(t.get("vehicle_id", 0)))

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
    time.sleep(30)

# 保存結果を表示（読み取り専用 → データ損失なし）
print("=== 保存結果 ===")
with open(csv_file, "r", encoding="utf-8-sig") as f:
    for line in f:
        print(line.strip())
print("================")
