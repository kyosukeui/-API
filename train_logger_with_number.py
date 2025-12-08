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

interval_minutes = 20
max_runs = 18

# === 開始時刻リスト（JST基準） ===
start_hours = [3, 9, 15, 21]

now = datetime.now(JST)
today = now.date()

# 今日の開始候補時刻を作成
start_times = [
    datetime(today.year, today.month, today.day, h, 0, 0, tzinfo=JST)
    for h in start_hours
]

# 現在時刻以降の開始時刻を選択
next_start = None
for st in start_times:
    if now <= st:
        next_start = st
        break

if next_start is None:
    print(f"[{now}] 本日の開始時刻はすべて過ぎました。終了します。")
else:
    # 開始まで待機
    sleep_seconds = (next_start - now).total_seconds()
    if sleep_seconds > 0:
        print(f"[{now}] {next_start} まで {sleep_seconds:.0f} 秒待機します")
        time.sleep(sleep_seconds)

    # === 記録ループ ===
    for run in range(max_runs):
        now = datetime.now(JST)
        # 24時を過ぎたら終了
        if now.hour == 0 and now.date() != today:
            print(f"[{now}] JST24時を過ぎたため終了します")
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
# === 路線・方向判定（APIデータから） ===
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
        print(f"[DEBUG] 路線判定失敗: keito_name='{keito}'")

    # rosen_nameやkeito_rosen_nameから方向を判別
    rosen_info = train.get("rosen_name", "") + train.get("keito_rosen_name", "")
    if "上り" in rosen_info:
        direction = "up"
    elif "下り" in rosen_info:
        direction = "down"
    else:
        direction = None
        print(f"[DEBUG] 方向判定失敗: rosen_name='{train.get('rosen_name','')}', keito_rosen_name='{train.get('keito_rosen_name','')}'")

    return line, direction

# === 時刻表読み込み関数 ===
def load_timetable(path, line_type, direction):
    df = pd.read_csv(path)
    timetable = []

    # すべて本線仕様で処理（駅が行、列番が列）
    for _, row in df.iterrows():
        # 1列目が駅名
        station = str(row[df.columns[0]]).replace("駅", "").strip()
        # 2列目以降が列車番号
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


# === 車両ごとの直前headsignを保持 ===
last_headsigns = {}

# === 記録ループ ===
for run in range(max_runs):
    now_jst = datetime.now(JST)
    if now_jst >= end_of_day:
        print("=== JST24時を過ぎたので終了 ===")
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

        with open(csv_file, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            for train in sorted_trains:
                print("[DEBUG] rosen_name:", train.get("rosen_name", ""))
                print("[DEBUG] keito_name:", train.get("keito_name", ""))

                vid = train.get("vehicle_id")
                formation = id_map.get(str(vid), f"ID:{vid}")
                station = train.get("teiryujo_name", "").replace("駅", "").strip()
                if station.endswith("駅"):
                    station = station[:-1]

                timestamp = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
                line, dirn = infer_line_and_direction(train)
                delay_sec = train.get("delay_sec", 0)

                train_number = find_train_number(station, timestamp, delay_sec, line, dirn)
                headsign = train.get("headsign", "")

                # === 前回と同じheadsignならスキップ ===
                if last_headsigns.get(vid) == headsign:
                    print(f"[SKIP] {vid} の headsign が前回と同じ ({headsign}) のためスキップ")
                    continue

                # 書き込み
                writer.writerow([
                    timestamp,
                    vid,
                    formation,
                    train_number,
                    headsign,
                    station
                ])

                # 更新
                last_headsigns[vid] = headsign

    except Exception as e:
        print(f"[ERROR] API取得エラー: {e}")

    if run < max_runs - 1:
        time.sleep(interval_seconds)

print("=== 保存完了 ===")



print("[DEBUG] APIレスポンス:", trains)
print("[DEBUG] sorted_trains:", sorted_trains)
