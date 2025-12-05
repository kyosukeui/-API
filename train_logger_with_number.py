import pandas as pd
from pathlib import Path
from datetime import datetime

def load_timetable(path, line_type):
    df = pd.read_csv(path)
    timetable = []

    if line_type == "honsen":  # 駅が行方向
        for _, row in df.iterrows():
            station = row[df.columns[0]]  # 1列目は駅名
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
            train_number = row[df.columns[0]]  # 先頭列は列車番号
            for station in df.columns[1:]:
                val = row[station]
                if pd.notna(val) and val not in ["レ", "(止)"]:
                    timetable.append({
                        "train_number": str(train_number),
                        "station": station,
                        "time": str(val)
                    })
    return timetable


# === 年度・休日判定 ===
year = "2025W"
base_dir = Path(f"data/{year}")

today = datetime.now()
weekday = today.weekday()  # 0=月曜, 6=日曜

# 休日判定: 土日 or 年末年始(12/30〜1/3)
is_holiday = (weekday >= 5) or (
    (today.month == 12 and today.day >= 30) or (today.month == 1 and today.day <= 3)
)

if is_holiday:
    suffix = "holiday"
else:
    suffix = "weekday"

# === ファイルリスト ===
files = [
    (f"timetable2025W_honsen_down_{suffix}.csv", "honsen"),
    (f"timetable2025W_honsen_up_{suffix}.csv", "honsen"),
    (f"timetable2025W_fuzikoshikamitaki_down_{suffix}.csv", "fuzikoshikamitaki"),
    (f"timetable2025W_fuzikoshikamitaki_up_{suffix}.csv", "fuzikoshikamitaki"),
    (f"timetable2025W_tateyama_down_{suffix}.csv", "tateyama"),
    (f"timetable2025W_tateyama_up_{suffix}.csv", "tateyama"),
]

# === 全路線読み込み ===
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
                continue  # ← except と同じインデントに修正
    return ""
                continue
    return ""
