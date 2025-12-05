import requests, time, csv, os
from datetime import datetime, timedelta, timezone

url = "https://buscatch.jp/rt3/unko_map_simple.ajax.php"
data = {"id": "chitetsu_train", "command": "get_unko_list", "rosen_group_id": "2235"}
headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}

id_map = {
    "5747": "10041F",
    "5760": "17485F",
    "6013": "14773F",
    "5902": "あお",
    "5883": "17481F"
}
formation_order = ["10041F", "14773F", "17481F","17485F","あお"]

JST = timezone(timedelta(hours=9))
os.makedirs("csv", exist_ok=True)

date_str = datetime.now(JST).strftime("%Y-%m-%d_%H-%M")
csv_file = f"csv/train_log_{date_str}.csv"

with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "vehicle_id", "formation_name", "headsign", "station"])

interval_minutes = 20
max_runs = 18
start_date = datetime.now(JST).date()

try:
    for run in range(max_runs):
        now = datetime.now(JST)
        if now.date() != start_date:
            print(f"[{now}] 日付が変わったため終了します")
            break

        try:
            response = requests.post(url, headers=headers, data=data, timeout=10)
            response.raise_for_status()
            trains = response.json()
        except Exception as e:
            print(f"[{now}] エラー発生: {e}")
        else:
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

        if run < max_runs - 1:
            time.sleep(interval_minutes * 60)

except KeyboardInterrupt:
    print("=== 手動終了が検出されました ===")
finally:
    print("=== 保存完了 ===")


