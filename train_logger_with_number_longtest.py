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
formation_order = ["10041F", "14773F", "17481F", "17485F", "あお"]

JST = timezone(timedelta(hours=9))
os.makedirs("csv", exist_ok=True)

date_str = datetime.now(JST).strftime("%Y-%m-%d_%H-%M")
csv_file = f"csv/train_log_{date_str}.csv"

with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "vehicle_id", "formation_name", "headsign", "station"])

# === 記録設定 ===
interval_minutes = 20
max_runs = 18

# UTC基準の開始時刻リスト
UTC = timezone.utc
start_hours = [3, 9, 15, 21]

# 次の開始時刻を決定
now_utc = datetime.now(UTC)
next_start = None
for h in start_hours:
    candidate = now_utc.replace(hour=h, minute=0, second=0, microsecond=0)
    if candidate > now_utc:
        next_start = candidate
        break
if next_start is None:
    # 翌日の3時に設定
    next_start = (now_utc + timedelta(days=1)).replace(hour=3, minute=0, second=0, microsecond=0)

print(f"次の記録開始時刻(UTC): {next_start}")

# === 待機 ===
sleep_seconds = (next_start - now_utc).total_seconds()
time.sleep(sleep_seconds)

# === 記録ループ ===
for run in range(max_runs):
    now = datetime.now(JST)
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
        except Exception:
            sorted_trains = trains

        with open(csv_file, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            for train in sorted_trains:
                vid = train.get("vehicle_id")
                formation = id_map.get(str(vid), f"ID:{vid}")
                station = train.get("teiryujo_name", "")
                if station.endswith("駅"):
                    station = station[:-1]

                writer.writerow([
                    now.strftime("%Y-%m-%d %H:%M:%S"),
                    vid,
                    formation,
                    train.get("headsign", ""),
                    station
                ])

    except Exception as e:
        print(f"[ERROR] API取得エラー: {e}")

    if run < max_runs - 1:
        time.sleep(interval_minutes * 60)

print("=== 保存完了 ===")
# === 路線・方向判定（APIデータから） ===
def infer_line_and_direction(train: dict):
    rosen = train.get("rosen_name", "")
    if "本線" in rosen:
        line = "honsen"
    elif "立山線" in rosen:
        line = "tateyama"
    elif "不二越" in rosen or "上滝" in rosen:
        line = "fuzikoshikamitaki"
    else:
        line = None

    dir_flag = train.get("direction") or train.get("updown")
    if str(dir_flag) == "0":
        direction = "up"
    elif str(dir_flag) == "1":
        direction = "down"
    else:
        direction = None

    return line, direction

# === 時刻表読み込み関数 ===
def load_timetable(path, line_type, direction):
    df = pd.read_csv(path)
    timetable = []
    if line_type == "honsen":  # 駅が行方向
        for _, row in df.iterrows():
            station = row[df.columns[0]]
            for col in df.columns[1:]:
                val = row[col]
                if pd.notna(val) and val not in ["レ", "(止)"]:
                    timetable.append({
                        "line": line_type,
                        "direction": direction,
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
                        "line": line_type,
                        "direction": direction,
                        "train_number": str(train_number),
                        "station": station,
                        "time": str(val)
                    })
    return timetable

# === 休日判定 ===
today = datetime.now(JST)
weekday = today.weekday()
is_holiday = (weekday >= 5) or (
    (today.month == 12 and today.day >= 30) or (today.month == 1 and today.day <= 3)
)
suffix = "holiday" if is_holiday else "weekday"

# === 時刻表ファイルリスト ===
year = "2025W"
base_dir = Path(f"data/{year}")
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

# === 列番照合関数 ===
def find_train_number(station, timestamp, delay_sec, line, dirn):
    ts = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
    ts_adjusted = ts - timedelta(seconds=int(delay_sec or 0))

    # 方向一致を追加
    candidate_rows = [
        row for row in timetable
        if (line is None or row["line"] == line)
           and (dirn is None or row["direction"] == dirn)
           and row["station"] == station
    ]

    print(f"[DEBUG] API方向={dirn}, CSV方向候補={[row['direction'] for row in candidate_rows]}")

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

    print(f"[DEBUG] 候補={len(candidate_rows)} 最小差分={min_diff}秒 駅={station}, 路線={line}, 方向={dirn}")
    return ""

# === CSV 初期化 ===
with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow([
        "timestamp", "vehicle_id", "formation_name", "headsign", "station", "delay_seconds", "train_number"
    ])

# === 車両ごとの直前列番を保持 ===
last_train_numbers = {}

# === ループ設定 ===
interval_seconds = 30   # 30秒ごと
max_runs = 3            # 3回実行
start_date = datetime.now(JST).date()

try:
    for run in range(max_runs):
        now = datetime.now(JST)
        if now.date() != start_date:
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
            except Exception:
                sorted_trains = trains

            # === ここから正しいインデント ===
            with open(csv_file, "a", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                for train in sorted_trains:
                    vid = train.get("vehicle_id")
                    formation = id_map.get(str(vid), f"ID:{vid}")

                    # 駅名揺れ対策：「駅」が付いている場合は削除
                    station = train.get("teiryujo_name", "")
                    if station.endswith("駅"):
                        station = station[:-1]

                    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
                    delay_sec = int(train.get("delay_sec") or 0)
                    line, dirn = infer_line_and_direction(train)
                    train_number = find_train_number(station, timestamp, delay_sec, line, dirn)

                    # 常に追記する
                    writer.writerow([
                        timestamp,
                        vid,
                        formation,
                        train.get("headsign", ""),
                        station,
                        delay_sec,
                        train_number
                    ])
                    # last_train_numbers は保持してもよいが、追記制御には使わない
                    last_train_numbers[vid] = train_number

        except Exception as e:
            print(f"[ERROR] API取得エラー: {e}")

        if run < max_runs - 1:
            time.sleep(interval_seconds)

except KeyboardInterrupt:
    print("=== 手動終了 ===")
finally:
    print("=== 保存完了 ===")
