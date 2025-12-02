import pandas as pd
from pathlib import Path
from datetime import datetime

def load_timetable(path, line_type):
    df = pd.read_csv(path)
    timetable = []

    if line_type == "honsen":  # 駅が行方向
        for _, row in df.iterrows():
            station = row["station"]
            for col in df.columns[1:]:  # 1列目は駅名
                val = row[col]
                if pd.notna(val) and val not in ["レ", "(止)"]:
                    timetable.append({
                        "train_number": str(col),
                        "station": station,
                        "time": str(val)
                    })
    else:  # fuzikoshikamitaki, tateyama
        for _, row in df.iterrows():
            train_number = row["train_number"]
            for station in df.columns[3:]:  # 先頭列は番号や種別など
                val = row[station]
                if pd.notna(val) and val not in ["レ", "(止)"]:
                    timetable.append({
                        "train_number": str(train_number),
                        "station": station,
                        "time": str(val)
                    })
    return timetable

# === 全路線の読み込み ===
year = "2025W"
base_dir = Path(f"data/{year}")

files = [
    ("timetable2025W_honsen_down.csv", "honsen"),
    ("timetable2025W_honsen_up.csv", "honsen"),
    ("timetable2025W_fuzikoshikamitaki_down.csv", "fuzikoshikamitaki"),
    ("timetable2025W_fuzikoshikamitaki_up.csv", "fuzikoshikamitaki"),
    ("timetable2025W_tateyama_down.csv", "tateyama"),
    ("timetable2025W_tateyama_up.csv", "tateyama"),
]

timetable = []
for fname, line_type in files:
    timetable.extend(load_timetable(base_dir / fname, line_type))

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
