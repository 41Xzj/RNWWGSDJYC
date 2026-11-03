# -*- coding: utf-8 -*-
"""甘肃电力日前节点电价预测系统 - 网页版"""
import streamlit as st
import pandas as pd
import numpy as np
import requests
import datetime
import time as time_lib
import io
import os

# 页面配置
st.set_page_config(
    page_title="润能（武威）公司甘肃省电价预测系统",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ 润能（武威）公司甘肃省电价预测系统")

# 节点配置
NODES = [
    ("参考点", None, None),
    ("瓜州", 40.52, 95.78),
    ("酒泉", 39.73, 98.49),
    ("张掖", 38.93, 100.45),
    ("金昌", 38.49, 102.19),
    ("武威", 37.93, 102.63),
    ("九甸峡", 34.58, 103.18),
    ("洛大", 33.98, 103.88),
    ("平凉", 35.54, 106.66),
    ("庆阳", 35.71, 107.64),
    ("临江", 33.33, 104.95),
]

# 河西组和河东组
HEXI = ["瓜州", "酒泉", "张掖", "金昌", "武威"]
HEDONG = ["平凉", "庆阳", "九甸峡", "洛大", "临江"]

WEATHER_FILE = "weather_data.xlsx"

@st.cache_data(ttl=3600)
def fetch_weather_node(lat, lon, start_date, end_date, is_history):
    """爬取单个节点天气"""
    if is_history:
        url = "https://archive-api.open-meteo.com/v1/archive"
    else:
        url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": "wind_speed_10m,shortwave_radiation",
        "wind_speed_unit": "ms",
        "start_date": start_date, "end_date": end_date,
        "timezone": "Asia/Shanghai",
    }
    for i in range(3):
        try:
            r = requests.get(url, params=params, timeout=15)
            d = r.json()
            if d and "hourly" in d and d["hourly"]:
                return d
        except:
            time_lib.sleep(1)
    return None

def update_weather_web(progress_bar):
    """更新天气数据"""
    today = datetime.date.today()
    history_end = today.strftime("%Y-%m-%d")
    forecast_start = today.strftime("%Y-%m-%d")
    forecast_end = (today + datetime.timedelta(days=4)).strftime("%Y-%m-%d")
    
    all_rows = []
    
    # 历史天气（从d-2到d）
    history_start = (today - datetime.timedelta(days=2)).strftime("%Y-%m-%d")
    progress_bar.progress(0.1, text="爬取历史天气...")
    
    for idx, (name, lat, lon) in enumerate(NODES[1:]):
        if lat is None: continue
        d = fetch_weather_node(lat, lon, history_start, history_end, True)
        if d and "hourly" in d:
            times = d["hourly"]["time"]
            w = d["hourly"]["wind_speed_10m"]
            rad = d["hourly"]["shortwave_radiation"]
            for i, t in enumerate(times):
                dt = pd.to_datetime(t)
                date = dt.date()
                time = dt.time()
                found = False
                for row in all_rows:
                    if row["日期"] == date and row["时间"] == time:
                        row[f"{name}_风"] = w[i]
                        row[f"{name}_辐"] = rad[i]
                        found = True
                        break
                if not found:
                    new_row = {"日期": date, "时间": time}
                    for n, _, _ in NODES[1:]:
                        new_row[f"{n}_风"] = None
                        new_row[f"{n}_辐"] = None
                    new_row[f"{name}_风"] = w[i]
                    new_row[f"{name}_辐"] = rad[i]
                    all_rows.append(new_row)
        progress_bar.progress(0.1 + 0.4 * (idx+1)/10, text=f"爬取历史天气 {name}...")
    
    # 预测天气（d到d+4）
    progress_bar.progress(0.5, text="爬取预测天气...")
    for idx, (name, lat, lon) in enumerate(NODES[1:]):
        if lat is None: continue
        d = fetch_weather_node(lat, lon, forecast_start, forecast_end, False)
        if d and "hourly" in d:
            times = d["hourly"]["time"]
            w = d["hourly"]["wind_speed_10m"]
            rad = d["hourly"]["shortwave_radiation"]
            for i, t in enumerate(times):
                dt = pd.to_datetime(t)
                date = dt.date()
                time = dt.time()
                found = False
                for row in all_rows:
                    if row["日期"] == date and row["时间"] == time:
                        row[f"{name}_风"] = w[i]
                        row[f"{name}_辐"] = rad[i]
                        found = True
                        break
                if not found:
                    new_row = {"日期": date, "时间": time}
                    for n, _, _ in NODES[1:]:
                        new_row[f"{n}_风"] = None
                        new_row[f"{n}_辐"] = None
                    new_row[f"{name}_风"] = w[i]
                    new_row[f"{name}_辐"] = rad[i]
                    all_rows.append(new_row)
        progress_bar.progress(0.5 + 0.4 * (idx+1)/10, text=f"爬取预测天气 {name}...")
    
    weather = pd.DataFrame(all_rows)
    
    # 计算河东河西平均
    weather["河西_平均风速"] = weather[[f"{n}_风" for n in HEXI]].mean(axis=1)
    weather["河西_平均辐照"] = weather[[f"{n}_辐" for n in HEXI]].mean(axis=1)
    weather["河东_平均风速"] = weather[[f"{n}_风" for n in HEDONG]].mean(axis=1)
    weather["河东_平均辐照"] = weather[[f"{n}_辐" for n in HEDONG]].mean(axis=1)
    
    # 打天气类型
    def weather_type(row):
        hw = row.get("河西_平均风速", 0) or 0
        hr = row.get("河西_平均辐照", 0) or 0
        ew = row.get("河东_平均风速", 0) or 0
        er = row.get("河东_平均辐照", 0) or 0
        hw_t = 0 if hw < 3 else (1 if hw < 5 else 2)
        hr_t = 0 if hr < 200 else (1 if hr < 600 else 2)
        ew_t = 0 if ew < 3 else (1 if ew < 5 else 2)
        er_t = 0 if er < 200 else (1 if er < 600 else 2)
        return f"{hw_t}{hr_t}{ew_t}{er_t}"
    
    weather["天气类型"] = weather.apply(weather_type, axis=1)
    progress_bar.progress(1.0, text="天气更新完成")
    return weather

def time_decay_weight(target_date, hist_date):
    days = (target_date - hist_date).days
    if days < 0: return 0
    if days <= 7: return 1.0
    if days <= 30: return 0.6
    return 0.3

def sigmoid_curve(x, ratio0, k):
    return 40 + 460 / (1 + np.exp(k*(x - ratio0)))

# 侧边栏
st.sidebar.header("📁 上传数据文件")
supply_file = st.sidebar.file_uploader("供需数据汇总.xlsx", type=["xlsx"])
price_file = st.sidebar.file_uploader("节点电价统计表.xlsx", type=["xlsx"])

if supply_file and price_file:
    with st.spinner("加载数据中..."):
        # 读供需数据（宽表转长表）
        supply_raw = pd.read_excel(supply_file, sheet_name="供需汇总")
        # 第一列是分类，第二列是名称，后面都是日期列
        date_cols = [c for c in supply_raw.columns if c not in ["分类", "名称"]]
        supply_long = supply_raw.melt(id_vars=["分类","名称"], value_vars=date_cols, var_name="date", value_name="value")
        supply_long["date"] = pd.to_datetime(supply_long["date"], errors="coerce").dt.date
        supply_long = supply_long.dropna(subset=["date"])
        supply_long = supply_long.rename(columns={"分类":"category", "名称":"name"})
        supply_long = supply_long.pivot_table(index=["date","category"], columns="name", values="value", aggfunc="first").reset_index()
        supply_long["供需比"] = supply_long["新能源发电预测"] / supply_long["系统负荷-联络线(发电)"]
        supply_long["time"] = datetime.time(0,0)
        
        # 读电价数据
        price_raw = pd.read_excel(price_file, sheet_name="总表")
        price_raw["类型"] = price_raw["类型"].astype(str).str.strip()
        price_raw = price_raw[price_raw["类型"] == "日前"]
        price_raw["日期"] = pd.to_datetime(price_raw["日期"]).dt.date
        
        price_long_rows = []
        for _, row in price_raw.iterrows():
            d = row["日期"]
            for node_name, _, _ in NODES[1:]:
                if node_name in price_raw.columns:
                    price_long_rows.append({"date": d, "node": node_name, "price": row[node_name]})
        price_long = pd.DataFrame(price_long_rows)
        price_long["time"] = datetime.time(0,0)
    
    st.success("数据加载完成！")
    
    # 日期选择
    st.sidebar.header("📅 选择预测日期")
    today = datetime.date.today()
    dates = st.sidebar.date_input(
        "预测日期",
        value=[today, today + datetime.timedelta(days=1)],
        min_value=today,
        max_value=today + datetime.timedelta(days=4)
    )
    
    if st.sidebar.button("开始预测", type="primary"):
        progress_bar = st.progress(0, text="开始...")
        
        # 更新天气
        weather = update_weather_web(progress_bar)
        
        # 合并历史库
        history = supply_long[supply_long["category"] == "发布"].copy()
        history = history.merge(price_long, on=["date","time"], how="inner")
        
        # 模拟供需
        sim = supply_long[supply_long["category"] == "模拟"].copy()
        
        # 供需档位
        def ratio_type(r):
            if r < 1.18: return 0
            elif r < 1.32: return 1
            elif r < 1.50: return 2
            else: return 3
        history["供需档位"] = history["供需比"].apply(ratio_type)
        
        # 拟合回退公式
        fallback = {}
        for node_name, _, _ in NODES[1:]:
            fallback[node_name] = {}
            node_data = history[history["node"] == node_name]
            for h in range(24):
                hour_data = node_data[node_data["time"].apply(lambda x: x.hour == h)]
                if len(hour_data) > 5:
                    ratio0 = hour_data["供需比"].median()
                    fallback[node_name][h] = (ratio0, 5.0)
                else:
                    fallback[node_name][h] = (1.3, 5.0)
        
        # 开始预测
        all_results = []
        target_dates = [d for d in dates] if isinstance(dates, list) else [dates]
        
        for target_date in target_dates:
            target_date = pd.to_datetime(target_date).date()
            st.subheader(f"📊 预测结果：{target_date}")
            
            target_supply = sim[sim["date"] == target_date]
            if len(target_supply) == 0:
                st.warning(f"{target_date} 无模拟供需数据")
                continue
            
            # 当天天气
            day_weather = weather[weather["日期"] == target_date]
            weather_today = {}
            if len(day_weather) > 0:
                for col in ["河西_平均风速", "河西_平均辐照", "河东_平均风速", "河东_平均辐照", "天气类型"]:
                    if col in day_weather.columns:
                        weather_today[col] = day_weather.sort_values("时间")[col].tolist()
            
            results = []
            for _, row in target_supply.iterrows():
                t_ratio = row["供需比"]
                t_renew = row["新能源发电预测"]
                t_load = row["系统负荷-联络线(发电)"]
                idx = 0
                target_rt = 0 if t_ratio < 1.18 else (1 if t_ratio < 1.32 else (2 if t_ratio < 1.50 else 3))
                
                target_wtype = weather_today.get("天气类型", ["0000"])[idx] if "天气类型" in weather_today else None
                
                df = history[history["time"] == row["time"]].copy()
                if len(df) == 0:
                    continue
                
                # 打分
                std_ratio = df["供需比"].std() or 0.1
                std_renew = df["新能源发电预测"].std() or 500
                std_load = df["系统负荷-联络线(发电)"].std() or 1500
                df["score"] = (
                    40 * abs(df["供需比"] - t_ratio) / std_ratio +
                    25 * abs(df["新能源发电预测"] - t_renew) / std_renew +
                    20 * abs(df["系统负荷-联络线(发电)"] - t_load) / std_load
                )
                df["time_weight"] = df["date"].apply(lambda d: time_decay_weight(target_date, d))
                df["score_weighted"] = df["score"] / df["time_weight"]
                
                # 第一层
                cond1 = (df["供需档位"] == target_rt)
                if target_wtype:
                    cond1 &= (df["天气类型"] == target_wtype)
                m1 = df[cond1]
                
                if len(m1) == 0:
                    for rt_off in [-1, 1]:
                        neighbor = target_rt + rt_off
                        if 0 <= neighbor <= 3:
                            cond_w = (df["供需档位"] == neighbor)
                            if target_wtype:
                                cond_w &= (df["天气类型"] == target_wtype)
                            m1 = df[cond_w]
                            if len(m1) >= 1: break
                
                for node_name, _, _ in NODES[1:]:
                    if len(m1) >= 1:
                        best = m1[m1["node"] == node_name].sort_values("score_weighted")
                        if len(best) > 0:
                            price = best.iloc[0]["price"]
                        else:
                            h = row["time"].hour
                            ratio0, k = fallback[node_name].get(h, (1.3, 5.0))
                            price = sigmoid_curve(t_ratio, ratio0, k)
                    else:
                        h = row["time"].hour
                        ratio0, k = fallback[node_name].get(h, (1.3, 5.0))
                        price = sigmoid_curve(t_ratio, ratio0, k)
                    
                    price = min(500, max(40, price))
                    results.append({"日期": target_date, "时间": row["time"], "节点": node_name, "预测电价": round(price, 1)})
            
            result_df = pd.DataFrame(results)
            all_results.append(result_df)
            
            # 显示
            pivot = result_df.pivot(index="时间", columns="节点", values="预测电价")
            st.dataframe(pivot, use_container_width=True)
        
        # 下载
        if all_results:
            final = pd.concat(all_results, ignore_index=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                final.to_excel(writer, sheet_name="预测结果", index=False)
            st.download_button(
                "📥 下载预测结果Excel",
                data=output.getvalue(),
                file_name=f"润能武威_甘肃省电价预测_{today}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
else:
    st.info("👈 请先在左侧上传两个数据文件：")
    st.markdown("1. 供需数据汇总.xlsx")
    st.markdown("2. 节点电价统计表.xlsx")
    st.markdown("上传后就可以选择日期开始预测了。")
