from fastapi import FastAPI, Query
from fastapi.responses import Response
import subprocess
import os
import pandas as pd
import json

app = FastAPI()

@app.get("/crawl")
def crawl(stock: str = Query(...), quarter: str = Query(...)):
    subprocess.run(["python3", "crawler_api.py", stock])

    table_types = {
        "cdkt": "cdkt",
        "kqkd": "kqkd",
        "lctt_tt": "lctt_tt",
        "lctt_gt": "lctt_gt"
    }

    base_data = {}

    for root, dirs, files in os.walk("."):
        if quarter in root and stock in root:
            for file in files:
                if file.endswith(".csv"):
                    for key, keyword in table_types.items():
                        if keyword in file.lower():
                            try:
                                df = pd.read_csv(os.path.join(root, file))
                                df.dropna(how="all", inplace=True)

                                # Chuyển NaN, inf, -inf thành None
                                df = df.replace({float("nan"): None, float("inf"): None, float("-inf"): None})
                                df = df.where(pd.notnull(df), None)

                                base_data[key] = df.to_dict(orient="records")
                            except Exception as e:
                                base_data[key] = [{"error": f"Không đọc được file {file}: {e}"}]

    if base_data:
        # Dùng dumps thủ công để tránh NaN, inf bị lỗi JSON
        json_str = json.dumps(base_data, ensure_ascii=False, allow_nan=False)
        return Response(content=json_str, media_type="application/json")
    else:
        return {"message": f"Không tìm thấy dữ liệu cho mã {stock} quý {quarter}"}