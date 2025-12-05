import requests, time, csv, os
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta, timezone

# === 運行情報 API ===
url = "https://buscatch.jp/rt3/unko_map_simple.ajax.php"
data = {"id": "chitetsu_train", "command": "get_unko_list", "rosen_group_id": "2235"}
headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}

# === 編成マッピング ===
id_map = {
    "1001": "デ7011編成",
    "1002": "デ7012編成",
    "2001": "デ7021編成"
}
formation_order = ["デ7011編成", "デ7012編成", "デ7021編成"]

# === タイムゾーン ===
JST = timezone(timedelta(hours=9))

# === ディレクトリ作成 ===
os.makedirs("csv", exist_ok=True)

# === 出力ファイル名 ===
date_str = datetime.now(JST).strftime("%Y-%m-%d_%H-%M")
csv_file = f"csv/train_log_with_number_{date_str}.csv"

# === 時刻表読み込み関数 ===
def load_timetable(path, line_type):
    df = pd.read_csv(path)
    timetable = []
    if line_type == "honsen":  # 駅が行方向
        for _, row in df.iterrows():
            station = row[df.columns[0]]
            for col in df.columns[1:]:
                val = row[col]
                if pd.notna(val) and val not in ["レ", "(止)"]:
                    timetable.append({
                        "train_number": str(col),
                        "station": station,
                        "time": str(val)
                    })
    else:  # fuzikoshikamitaki, tateyama
        for _, row in df.iterrows():
            train_number = row[df.columns[0]]
            for station in df.columns[1:]:
                val = row[station]
                if pd.notna(val) and val not in ["レ", "(止)"]:
                    timetable.append({
                        "train_number": str(train_number),
                        "station": station,
                        "time": str(val)
                    })
    return timetable

# === 休日判定 ===
today = datetime.now(JST)
weekday = today.weekday()  # 0=月曜, 6=日曜
is_holiday = (weekday >= 5) or (
    (today.month == 12 and today.day >= 30) or (today.month == 1 and today.day <= 3)
)
suffix = "holiday" if is_holiday else "weekday"

# === 時刻表ファイルリスト ===
year = "2025W"
base_dir = Path(f"data/{year}")
files = [
    (f"timetable2025W_honsen_down_{suffix}.csv", "honsen"),
    (f"timetable2025W_honsen_up_{suffix}.csv", "honsen"),
    (f"timetable2025W_fuzikoshikamitaki_down_{suffix}.csv", "fuzikoshikamitaki"),
    (f"timetable2025W_fuzikoshikamitaki_up_{suffix}.csv", "fuzikoshikamitaki"),
    (f"timetable2025W_tateyama_down_{suffix}.csv", "tateyama"),
    (f"timetable2025W_tateyama_up_{suffix}.csv", "tateyama"),
]

timetable = []
for fname, line_type in files:
    path = base_dir / fname
    if path.exists():
        timetable.extend(load_timetable(path, line_type))

# === 列車番号検索関数 ===
def find_train_number(station, timestamp):
    ts = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
    for row in timetable:
        if row["station"] == station:
            try:
                tt = datetime.strptime(row["time"], "%H:%M").replace(
                    year=ts.year, month=ts.month, day=ts.day
                )
                if abs((ts - tt).total_seconds()) <= 300:  # ±5分以内
                    return row["train_number"]
            except ValueError:
                continue
    return ""

# === CSV 初期化 ===
with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "vehicle_id", "formation_name", "headsign", "station", "train_number"])

# === 車両ごとの直前列番を保持 ===
last_train_numbers = {}

# === ループ設定 ===
interval_seconds = 30 
max_runs =3
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

            # 並び替え（編成順）
            try:
                sorted_trains = sorted(
                    trains,
                    key=lambda t: formation_order.index(
                        id_map.get(str(t.get("vehicle_id")), f"ID:{t.get('vehicle_id')}")
                    )
                    if id_map.get(str(t.get("vehicle_id"))) in formation_order else len(formation_order)
                )
            except Exception as e:
                print(f"[{now}] 並び替えエラー: {e}")
                sorted_trains = trains

            with open(csv_file, "a", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                for train in sorted_trains:
                    vid = train.get("vehicle_id")
                    formation = id_map.get(str(vid), f"ID:{vid}")
                    station = train.get("teiryujo_name")
                    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
                    train_number = find_train_number(station, timestamp)

                    if last_train_numbers.get(vid) != train_number:
                        writer.writerow([
                            timestamp,
                            vid,
                            formation,
                            train.get("headsign"),
                            station,
                            train_number
                        ])
                        last_train_numbers[vid] = train_number
                        print(f"[{now}] {formation} 列番変化 → {train_number} を記録")

        except Exception as e:
            print(f"[{now}] API取得エラー: {e}")

        if run < max_runs - 1:
            time.sleep(interval_seconds)

except KeyboardInterrupt:
    print("=== 手動終了が検出されました ===")
finally:
    print("=== 保存完了 ===")
