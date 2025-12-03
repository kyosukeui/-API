import requests, time, csv
from datetime import datetime, timedelta

url = "https://buscatch.jp/rt3/unko_map_simple.ajax.php"
data = {"id": "chitetsu_train", "command": "get_unko_list", "rosen_group_id": "2235"}
headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}

# 車両ID → 編成名の対応表
id_map = {
    "1001": "デ7011編成",
    "1002": "デ7012編成",
    "2001": "デ7021編成"
}
formation_order = ["デ7011編成", "デ7012編成", "デ7021編成"]

# CSVファイル名
date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
csv_file = f"train_log_{date_str}.csv"

# ヘッダ行
with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "vehicle_id", "formation_name", "headsign", "station"])

# 収集条件
interval_minutes = 20
duration_minutes = 5 * 60 + 40   # 5時間40分 = 340分
end_time = datetime.now() + timedelta(minutes=duration_minutes)

# ループ開始
while datetime.now() <= end_time:
    now = datetime.now()
    try:
        response = requests.post(url, headers=headers, data=data, timeout=10)
        response.raise_for_status()
        trains = response.json()
    except Exception as e:
        print(f"[{now}] エラー発生: {e}")
    else:
        # CSV追記処理...
        print(f"[{now}] データを保存しました ({len(trains)}件)")

    # 必ず待機する
    time.sleep(interval_minutes * 60)

print("=== 収集完了 ===")

    # 編成順にソート
    sorted_trains = sorted(
        trains,
        key=lambda t: formation_order.index(id_map.get(str(t.get("vehicle_id")), f"ID:{t.get('vehicle_id')}"))
        if id_map.get(str(t.get("vehicle_id"))) in formation_order else len(formation_order)
    )

    # CSVに追記
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

    # 次の収集まで待機
    if datetime.now() + timedelta(minutes=interval_minutes) <= end_time:
        time.sleep(interval_minutes * 60)

print("=== 収集完了 ===")

print("=== 保存完了 ===")



