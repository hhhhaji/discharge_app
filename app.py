# app.py
# 出院前瞻提醒系統 Prototype（含核銷表格：診斷證明書/光碟/病歷複製份數）
# 使用方式：
#   pip install streamlit pandas
#   streamlit run app.py

import streamlit as st
import pandas as pd
from datetime import datetime

DATA_FILE = "patients.csv"

REQUIRED_COLS = [
    "PatientID",
    "Ward",
    "DischargeDate",
    "Status",        # 待處理 / 完成 / 取消
    "CreatedTime",
    "CompletedTime",
    "CertCount",     # 診斷證明書份數
    "CDCount",       # 光碟張數
    "RecordCopy",    # 病歷複製份數
    "Notes",         # 備註（可選）
]

def ensure_schema(df: pd.DataFrame) -> pd.DataFrame:
    """確保 CSV 欄位完整，避免舊檔造成欄位缺失。"""
    for col in REQUIRED_COLS:
        if col not in df.columns:
            df[col] = "" if col in ["Notes", "CompletedTime"] else 0 if col in ["CertCount", "CDCount", "RecordCopy"] else ""
    # 欄位順序固定一下（可讀性）
    df = df[REQUIRED_COLS]
    return df

def load_data() -> pd.DataFrame:
    try:
        df = pd.read_csv(DATA_FILE)
    except FileNotFoundError:
        df = pd.DataFrame(columns=REQUIRED_COLS)
        df = ensure_schema(df)
        return df

    df = ensure_schema(df)

    # 型別保護（避免 number 欄位被讀成字串）
    for col in ["CertCount", "CDCount", "RecordCopy"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    # 避免 NaN
    df["Notes"] = df["Notes"].fillna("")
    df["CompletedTime"] = df["CompletedTime"].fillna("")
    df["CreatedTime"] = df["CreatedTime"].fillna("")

    return df

def save_data(df: pd.DataFrame) -> None:
    df = ensure_schema(df)
    df.to_csv(DATA_FILE, index=False)

def make_key(row: pd.Series) -> str:
    """用可讀的 key 讓使用者挑選要標記的項目。"""
    return f'{row["PatientID"]} | {row["Ward"]} | {row["DischargeDate"]}'

st.set_page_config(page_title="出院前瞻提醒系統 Prototype", layout="wide")
st.title("出院前瞻提醒系統 Prototype（含核銷）")

df = load_data()

# ========== 新增預計出院病人 ==========
st.subheader("新增預計出院病人")
with st.form("add_patient", clear_on_submit=True):
    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        pid = st.text_input("病歷號／代碼（例如 P001）")
    with c2:
        ward = st.text_input("病房（例如 8A / 1201）")
    with c3:
        ddate = st.date_input("預計出院日")

    notes = st.text_input("備註（可留空）")
    submitted = st.form_submit_button("加入")

    if submitted:
        pid = pid.strip()
        ward = ward.strip()
        if not pid:
            st.error("請輸入病歷號／代碼")
        elif not ward:
            st.error("請輸入病房")
        else:
            new_row = {
                "PatientID": pid,
                "Ward": ward,
                "DischargeDate": str(ddate),
                "Status": "待處理",
                "CreatedTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "CompletedTime": "",
                "CertCount": 0,
                "CDCount": 0,
                "RecordCopy": 0,
                "Notes": notes.strip(),
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_data(df)
            st.success("已加入待辦清單")
            st.rerun()

st.divider()

# ========== 左側：完成標記 + 核銷 ==========
st.sidebar.header("完成標記（含核銷）")

todo = df[df["Status"] == "待處理"].copy()
todo_keys = todo.apply(make_key, axis=1).tolist()

if todo_keys:
    selected = st.sidebar.selectbox("選擇要標記完成的項目", todo_keys)

    st.sidebar.subheader("核銷表格")
    cert = st.sidebar.number_input("診斷證明書（份）", min_value=0, step=1, value=0)
    cd = st.sidebar.number_input("光碟（張）", min_value=0, step=1, value=0)
    rec = st.sidebar.number_input("病歷複製（份）", min_value=0, step=1, value=0)
    done_note = st.sidebar.text_input("完成備註（可留空）")

    if st.sidebar.button("標記為完成 ✅"):
        pid, ward, ddate = [x.strip() for x in selected.split("|")]

        mask = (
            (df["PatientID"].astype(str) == pid)
            & (df["Ward"].astype(str) == ward)
            & (df["DischargeDate"].astype(str) == ddate)
            & (df["Status"] == "待處理")
        )

        df.loc[mask, "Status"] = "完成"
        df.loc[mask, "CompletedTime"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        df.loc[mask, "CertCount"] = int(cert)
        df.loc[mask, "CDCount"] = int(cd)
        df.loc[mask, "RecordCopy"] = int(rec)

        # 合併備註：原備註 + 完成備註（不覆蓋）
        if done_note.strip():
            def merge_notes(old):
                old = "" if pd.isna(old) else str(old).strip()
                if old:
                    return f"{old} / 完成註記：{done_note.strip()}"
                return f"完成註記：{done_note.strip()}"

            df.loc[mask, "Notes"] = df.loc[mask, "Notes"].apply(merge_notes)

        save_data(df)
        st.sidebar.success("已標記完成並記錄核銷內容")
        st.rerun()

    if st.sidebar.button("取消項目 ⛔"):
        pid, ward, ddate = [x.strip() for x in selected.split("|")]
        mask = (
            (df["PatientID"].astype(str) == pid)
            & (df["Ward"].astype(str) == ward)
            & (df["DischargeDate"].astype(str) == ddate)
            & (df["Status"] == "待處理")
        )
        df.loc[mask, "Status"] = "取消"
        df.loc[mask, "CompletedTime"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_data(df)
        st.sidebar.warning("已取消該項目")
        st.rerun()
else:
    st.sidebar.info("目前沒有待處理項目。")

st.sidebar.divider()
st.sidebar.subheader("資料匯出")
csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
st.sidebar.download_button(
    label="下載 CSV（含核銷）",
    data=csv_bytes,
    file_name="discharge_prototype_export.csv",
    mime="text/csv",
)

# ========== 主畫面：清單顯示 ==========
left, right = st.columns([1.2, 1])

with left:
    st.subheader("待辦清單（待處理）")
    todo = df[df["Status"] == "待處理"].copy()
    if todo.empty:
        st.info("沒有待處理項目。")
    else:
        # 依出院日排序
        todo_sorted = todo.sort_values(by=["DischargeDate", "CreatedTime"], ascending=[True, True])
        st.dataframe(
            todo_sorted[["PatientID", "Ward", "DischargeDate", "CreatedTime", "Notes"]],
            use_container_width=True,
        )

with right:
    st.subheader("快速統計")
    st.metric("待處理數量", int((df["Status"] == "待處理").sum()))
    st.metric("已完成數量", int((df["Status"] == "完成").sum()))
    st.metric("已取消數量", int((df["Status"] == "取消").sum()))

st.divider()

with st.expander("查看已完成項目（含核銷）", expanded=True):
    done = df[df["Status"] == "完成"].copy()
    if done.empty:
        st.write("尚無完成項目。")
    else:
        done_sorted = done.sort_values(by=["CompletedTime"], ascending=False)
        st.dataframe(
            done_sorted[
                ["PatientID", "Ward", "DischargeDate", "CertCount", "CDCount", "RecordCopy", "CompletedTime", "Notes"]
            ],
            use_container_width=True,
        )

with st.expander("查看已取消項目"):
    cancelled = df[df["Status"] == "取消"].copy()
    if cancelled.empty:
        st.write("尚無取消項目。")
    else:
        cancelled_sorted = cancelled.sort_values(by=["CompletedTime"], ascending=False)
        st.dataframe(
            cancelled_sorted[["PatientID", "Ward", "DischargeDate", "CompletedTime", "Notes"]],
            use_container_width=True,
        )
