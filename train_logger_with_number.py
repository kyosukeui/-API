import requests, time, csv, os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd
import jpholiday

url = "https://buscatch.jp/rt3/unko_map_simple.ajax.php"
data = {"id": "chitetsu_train", "command": "get_unko_list", "rosen_group_id": "2235"}
headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}

id_map = {
    "5741": "16011F",
    "5742": "16013F",
    "5743": "10031F(HM)",
    "5744": "10033F?",
    "5746": "10039F(HM)",
    "5747": "10041F",
    "5748": "10043F",
    "5749": "10045F",
    "5754": "14769F赤?",
    "5755": "14771F?",
    "5883": "17481F",
    "5758": "17483F",
    "5884": "17485F",
    "5760": "17487F",
    "5761": "20021F",
    "6013": "14773F(HM)",
    "5902": "14767F青",
    
}


JST = timezone(timedelta(hours=9))
os.makedirs("csv", exist_ok=True)

date_str = datetime.now(JST).strftime("%Y-%m-%d_%H-%M")
csv_file = f"csv/train_log_{date_str}.csv"

with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow([
        "operation",       # 運用
        "formation",       # 編成名
        "headsign",        # 行先
        "train_number",    # 列車番号
        "station",
        "timetable_file",
        "timestamp",
        "vehicle_id"
    ])
interval_minutes = 10
max_runs = 36
start_date = datetime.now(JST).date()

# === 運用表読み込み ===
def load_unyo_table(path):
    weekday_ops = {}
    holiday_ops = {}
    current = None  # "weekday" or "holiday"

    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue

            # セクション切り替え
            if line.lower() == "[weekday]":
                current = "weekday"
                continue
            if line.lower() == "[holiday]":
                current = "holiday"
                continue

            # セクション外 or 不正行は無視
            if "=" not in line or current is None:
                continue

            op, nums = line.split("=", 1)
            nums = [n.strip() for n in nums.split(",") if n.strip()]

            if current == "weekday":
                weekday_ops[op] = nums
            elif current == "holiday":
                holiday_ops[op] = nums

    return weekday_ops, holiday_ops
# === 逆引き辞書 ===
def build_reverse_map(op_table):
    rev = {}
    for op, nums in op_table.items():
        for n in nums:
            rev[n] = op
    return rev

# === 運用表読み込み（ここに追加） ===
weekday_ops, holiday_ops = load_unyo_table("data/2025W/2025Wunyo.txt")
weekday_map = build_reverse_map(weekday_ops)
holiday_map = build_reverse_map(holiday_ops)
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
                    "time": val,
                    "source_file": path.name   # ←追加
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
    source_file = None
    for row in candidate_rows:
        try:
            tt = datetime.strptime(row["time"], "%H:%M").replace(
                year=ts_adjusted.year, month=ts_adjusted.month, day=ts_adjusted.day
            )
            diff = abs((ts_adjusted - tt).total_seconds())
            if diff < min_diff:
                min_diff = diff
                best_match = row["train_number"]
                source_file = row["source_file"]
        except ValueError:
            continue
    if best_match and min_diff <= 900:  # ±15分以内なら採用
        return best_match, source_file
    return "合致なし", None

# === 時刻表ファイル読み込み ===
year = "2025W"
base_dir = Path(f"data/{year}")
today = datetime.now(JST).date()

# 土日 or 祝日 を「holiday」扱いにする
is_holiday = (today.weekday() >= 5) or jpholiday.is_holiday(today)

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
used_files = []
for path, line_type, direction in files:
    if path.exists():
        timetable.extend(load_timetable(path, line_type, direction))
        used_files.append(path.name)   # ファイル名だけ記録
# === 車両ごとの直前記録を保持 ===
# vehicle_id → (headsign, train_number)
last_records = {}
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
            sorted_trains = trains  # 並び替え不要ならそのまま

            with open(csv_file, "a", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                for train in sorted_trains:
                    vid = train.get("vehicle_id")
                    formation = id_map.get(str(vid), f"ID:{vid}")
                    station = str(train.get("teiryujo_name") or "").replace("駅", "").strip()
                    timestamp = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
                    line, dirn = infer_line_and_direction(train)
                    delay_sec = train.get("delay_sec", 0)
                    train_number, timetable_file = find_train_number(
                        station, timestamp, delay_sec, line, dirn, timetable
                    )
                    headsign = train.get("headsign", "")

                    # === スキップ判定 ===
                    prev = last_records.get(vid)
                    if prev and prev[0] == headsign and prev[1] != "合致なし":
                        print(f"[SKIP] {vid} の headsign が前回と同じ ({headsign}) "
                              f"かつ列番合致ありのためスキップ")
                        continue
                        
                    # 平日 or 休日で切り替え
                    op_map = weekday_map if suffix == "weekday" else holiday_map
                    operation = op_map.get(str(train_number), "不明")
                    
                    # === CSV書き込み ===
                    writer.writerow([
                        operation,#運用
                        formation,#編成名
                        headsign,#行先
                        train_number,#列車番号
                        station,
                        timetable_file or "未使用",
                        timestamp,
                        vid
                    ])

                    # === 記録更新 ===
                    last_records[vid] = (headsign, train_number)

            print(f"[{now}] データを保存しました ({len(sorted_trains)}件)")

        if run < max_runs - 1:
            time.sleep(interval_minutes * 60)

except KeyboardInterrupt:
    print("=== 手動終了が検出されました ===")
finally:
    print("=== 保存完了 ===")
