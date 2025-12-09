import requests, time, csv, os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd

url = "https://buscatch.jp/rt3/unko_map_simple.ajax.php"
data = {"id": "chitetsu_train", "command": "get_unko_list", "rosen_group_id": "2235"}
headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}

id_map = {
    "5747": "10041F",
    "5742": "10033F",
    "5758": "17483F",
    "5760": "17485F",
    "6013": "14773F",
    "5902": "あお",
    "5883": "17481F"
}
formation_order = ["10033F","10041F", "14773F", "17481F","17483F" ,"17485F", "あお"]

JST = timezone(timedelta(hours=9))
os.makedirs("csv", exist_ok=True)

date_str = datetime.now(JST).strftime("%Y-%m-%d_%H-%M")
csv_file = f"csv/train_log_{date_str}.csv"

with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "vehicle_id", "formation_name", "train_number", "headsign", "station"])

interval_minutes = 20
max_runs = 18
start_date = datetime.now(JST).date()

# === 時刻表読み込み関数 ===
def load_timetable(path, line_type, direction):
    df = pd.read_csv(path)
    timetable = []
    for _, row in df.iterrows():
        station = str(row[df.columns[0]]).replace("駅", "").strip()
        for col in df.columns[1:]:
            val = row[col]
            if pd.notna(val) and val not in ["レ", "(止)"]:
                val = str(val)
                if len(val) >= 5:
                    val = val[:5]  # HH:MM に統一
                timetable.append({
                    "line": line_type,
                    "direction": direction,
                    "train_number": str(col),
                    "station": station,
                    "time": val
                })
    return timetable

# === 路線・方向判定 ===
def infer_line_and_direction(train: dict):
    keito = train.get("keito_name", "").strip()
    if "立山線" in keito:
        line = "tateyama"
    elif "本線" in keito:
        line = "honsen"
    elif "不二越・上滝線" in keito:
        line = "fuzikoshikamitaki"
    else:
        line = None
    rosen_info = train.get("rosen_name", "") + train.get("keito_rosen_name", "")
    if "上り" in rosen_info:
        direction = "up"
    elif "下り" in rosen_info:
        direction = "down"
    else:
        direction = None
    return line, direction

# === 列番照合関数 ===
def find_train_number(station, timestamp, delay_sec, line, dirn, timetable):
    ts = datetime.strptime(timestamp, "%Y-%m-%d %H:%M")
    ts_adjusted = ts - timedelta(seconds=int(delay_sec or 0))
    candidate_rows = [
        row for row in timetable
        if (line is None or row["line"] == line)
           and (dirn is None or row["direction"] == dirn)
           and row["station"] == station
    ]
    best_match = None
    min_diff = 999999
    for row in candidate_rows:
        try:
            tt = datetime.strptime(row["time"], "%H:%M").replace(
                year=ts_adjusted.year, month=ts_adjusted.month, day=ts_adjusted.day
            )
            diff = abs((ts_adjusted - tt).total_seconds())
            if diff < min_diff:
                min_diff = diff
                best_match = row["train_number"]
        except ValueError:
            continue
    if best_match and min_diff <= 900:  # ±15分以内なら採用
        return best_match
    return "合致なし"

# === 時刻表ファイル読み込み ===
year = "2025W"
base_dir = Path(f"data/{year}")
today = datetime.now(JST)
weekday = today.weekday()
is_holiday = (weekday >= 5) or (
    (today.month == 12 and today.day >= 30) or (today.month == 1 and today.day <= 3)
)
suffix = "holiday" if is_holiday else "weekday"
files = [
    (base_dir / f"timetable2025W_honsen_down_{suffix}.csv", "honsen", "down"),
    (base_dir / f"timetable2025W_honsen_up_{suffix}.csv",   "honsen", "up"),
    (base_dir / f"timetable2025W_fuzikoshikamitaki_down_{suffix}.csv", "fuzikoshikamitaki", "down"),
    (base_dir / f"timetable2025W_fuzikoshikamitaki_up_{suffix}.csv",   "fuzikoshikamitaki", "up"),
    (base_dir / f"timetable2025W_tateyama_down_{suffix}.csv", "tateyama", "down"),
    (base_dir / f"timetable2025W_tateyama_up_{suffix}.csv",   "tateyama", "up"),
]
timetable = []
for path, line_type, direction in files:
    if path.exists():
        timetable.extend(load_timetable(path, line_type, direction))

# === 車両ごとの直前headsignを保持 ===
last_headsigns = {}

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
                    station = train.get("teiryujo_name", "").replace("駅", "").strip()
                    timestamp = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
                    line, dirn = infer_line_and_direction(train)
                    delay_sec = train.get("delay_sec", 0)
                    train_number = find_train_number(station, timestamp, delay_sec, line, dirn, timetable)
                    headsign = train.get("headsign", "")

                    # === 前回と同じheadsignならスキップ ===
                    if last_headsigns.get(vid) == headsign:
                        print(f"[SKIP] {vid} の headsign が前回と同じ ({headsign}) のためスキップ")
                        continue

                    writer.writerow([
                        timestamp,
                        vid,
                        formation,
                        train_number,
                        headsign,
                        station
                    ])
                    last_headsigns[vid] = headsign

            print(f"[{now}] データを保存しました ({len(sorted_trains)}件)")

        if run < max_runs - 1:
            time.sleep(interval_minutes * 60)

except KeyboardInterrupt:
    print("=== 手動終了が検出されました ===")
finally:
    print("=== 保存完了 ===")
