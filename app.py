import streamlit as st
import requests
import pandas as pd
from datetime import datetime

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="PrintFarm ERP",
    page_icon="🖨️",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def api_get(path: str):
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ Нет соединения с сервером. Убедитесь, что FastAPI запущен на порту 8000.")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ Ошибка сервера: {e.response.json().get('detail', str(e))}")
        return None


def api_post(path: str, payload: dict):
    try:
        r = requests.post(f"{API_BASE}{path}", json=payload, timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ Нет соединения с сервером. Убедитесь, что FastAPI запущен на порту 8000.")
        return None
    except requests.exceptions.HTTPError as e:
        detail = e.response.json().get("detail", str(e))
        st.error(f"❌ Ошибка: {detail}")
        return None


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

st.sidebar.title("🖨️ PrintFarm ERP")
st.sidebar.markdown("---")
section = st.sidebar.radio(
    "Навигация",
    ["📦 Номенклатура", "🧪 Сырьё", "📋 Заказы и Печать", "🏭 Склад деталей"],
)
st.sidebar.markdown("---")
st.sidebar.caption(f"Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}")


# ===========================================================================
# 1. НОМЕНКЛАТУРА (Parts Catalog)
# ===========================================================================

if section == "📦 Номенклатура":
    st.title("📦 Номенклатура деталей")

    parts = api_get("/parts/")

    # --- Display existing parts ---
    st.subheader("Текущий каталог")
    if parts is not None:
        if parts:
            df = pd.DataFrame(parts)[
                ["id", "name", "material", "items_per_bed", "weight_per_item_g", "print_time_mins"]
            ]
            df.columns = ["ID", "Название", "Материал", "Шт./стол", "Вес (г/шт.)", "Время печати (мин)"]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Каталог пуст. Добавьте первую деталь ниже.")

    st.markdown("---")

    # --- Create new part form ---
    st.subheader("➕ Добавить новую деталь")
    with st.form("form_create_part", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Название детали *", placeholder="например, Крышка корпуса")
            material = st.text_input("Материал", value="PETG (Черный)")
            items_per_bed = st.number_input("Штук на стол", min_value=1, value=30, step=1)
        with col2:
            weight_per_item_g = st.number_input("Вес одной детали (г)", min_value=0.1, value=2.0, step=0.1, format="%.2f")
            print_time_mins = st.number_input("Время печати (мин)", min_value=1, value=300, step=5)
            image_path = st.text_input("Путь к изображению (необязательно)", placeholder="/images/part.png")

        submitted = st.form_submit_button("✅ Добавить деталь", use_container_width=True)
        if submitted:
            if not name.strip():
                st.warning("⚠️ Укажите название детали.")
            else:
                payload = {
                    "name": name.strip(),
                    "material": material.strip(),
                    "items_per_bed": int(items_per_bed),
                    "weight_per_item_g": float(weight_per_item_g),
                    "print_time_mins": int(print_time_mins),
                    "image_path": image_path.strip() or None,
                }
                result = api_post("/parts/", payload)
                if result:
                    st.success(f"✅ Деталь «{result['name']}» успешно добавлена (ID: {result['id']}).")
                    st.rerun()


# ===========================================================================
# 2. СЫРЬЁ (Raw Materials)
# ===========================================================================

elif section == "🧪 Сырьё":
    st.title("🧪 Склад сырья (пластик)")

    # Fetch material stock indirectly: start a fresh order to see materials
    # We display stock via parts materials; materials stock is a flat table
    # We fetch all parts to know which materials are in use
    parts = api_get("/parts/")

    st.subheader("Текущие остатки")

    # Since there's no GET /materials/ endpoint, we maintain a display hint
    st.info(
        "ℹ️ Для просмотра остатков добавьте приход ниже. "
        "Фактический остаток отображается при сборе тиража."
    )

    # Show a placeholder metric — real balance shown after operations
    st.markdown("---")

    # --- Form to add plastic ---
    st.subheader("📥 Принять пластик на склад")
    with st.form("form_add_material", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            material_options = []
            if parts:
                material_options = list({p["material"] for p in parts})
            material_name = st.text_input(
                "Наименование материала *",
                value=material_options[0] if material_options else "PETG (Черный)",
                help="Должно точно совпадать с материалом в номенклатуре.",
            )
        with col2:
            weight_to_add = st.number_input(
                "Количество (г) *",
                min_value=1.0,
                value=9000.0,
                step=500.0,
                format="%.0f",
            )

        submitted = st.form_submit_button("✅ Принять на склад", use_container_width=True)
        if submitted:
            if not material_name.strip():
                st.warning("⚠️ Укажите наименование материала.")
            else:
                payload = {
                    "material_name": material_name.strip(),
                    "weight_to_add_g": float(weight_to_add),
                }
                result = api_post("/materials/add", payload)
                if result:
                    col_a, col_b = st.columns(2)
                    col_a.metric("Материал", result["material_name"])
                    col_b.metric(
                        "Общий остаток",
                        f"{result['total_weight_g']:,.0f} г",
                        delta=f"+{weight_to_add:,.0f} г",
                    )
                    st.success(
                        f"✅ Принято {weight_to_add:,.0f} г «{result['material_name']}». "
                        f"Итого на складе: {result['total_weight_g']:,.0f} г."
                    )


# ===========================================================================
# 3. ЗАКАЗЫ И ПЕЧАТЬ (Orders & Sessions)
# ===========================================================================

elif section == "📋 Заказы и Печать":
    st.title("📋 Заказы и управление печатью")

    parts = api_get("/parts/") or []

    # -----------------------------------------------------------------------
    # 3a. Active orders list
    # -----------------------------------------------------------------------
    st.subheader("Текущие заказы")
    orders = api_get("/orders/") or []   # endpoint not yet in backend — handled gracefully

    if isinstance(orders, list) and orders:
        rows = []
        for o in orders:
            part_name = next((p["name"] for p in parts if p["id"] == o["part_id"]), "—")
            rows.append({
                "ID": o["id"],
                "Клиент": o["customer"],
                "Деталь": part_name,
                "План": o["target_quantity"],
                "Выполнено": o["completed_quantity"],
                "Статус": o["status"],
                "Дедлайн": o.get("deadline", "—"),
            })
        df_orders = pd.DataFrame(rows)
        st.dataframe(df_orders, use_container_width=True, hide_index=True)
    else:
        st.info("Нет активных заказов.")

    st.markdown("---")

    # -----------------------------------------------------------------------
    # 3b. Create order form
    # -----------------------------------------------------------------------
    st.subheader("➕ Создать новый заказ")
    if not parts:
        st.warning("⚠️ Сначала добавьте детали в номенклатуру.")
    else:
        with st.form("form_create_order", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                customer = st.text_input("Клиент *", placeholder="ООО Ромашка")
                part_options = {p["name"]: p["id"] for p in parts}
                part_name_sel = st.selectbox("Деталь *", list(part_options.keys()))
            with col2:
                target_qty = st.number_input("Количество (шт.) *", min_value=1, value=100, step=10)
                deadline_date = st.date_input("Дедлайн (необязательно)", value=None)

            submitted = st.form_submit_button("✅ Создать заказ", use_container_width=True)
            if submitted:
                if not customer.strip():
                    st.warning("⚠️ Укажите клиента.")
                else:
                    payload = {
                        "customer": customer.strip(),
                        "part_id": part_options[part_name_sel],
                        "target_quantity": int(target_qty),
                        "deadline": str(deadline_date) + "T00:00:00" if deadline_date else None,
                    }
                    result = api_post("/orders/", payload)
                    if result:
                        st.success(
                            f"✅ Заказ #{result['id']} для «{result['customer']}» создан: "
                            f"{result['target_quantity']} шт."
                        )
                        st.rerun()

    st.markdown("---")

    # -----------------------------------------------------------------------
    # 3c. Start a print session
    # -----------------------------------------------------------------------
    st.subheader("🖨️ Запустить тираж")
    active_orders = [o for o in orders if isinstance(o, dict) and o.get("status") == "В процессе"]

    if not active_orders:
        st.info("Нет активных заказов для запуска тиража.")
    else:
        with st.form("form_start_session", clear_on_submit=True):
            order_labels = {
                f"#{o['id']} — {o['customer']} ({next((p['name'] for p in parts if p['id'] == o['part_id']), '?')})"
                : o["id"]
                for o in active_orders
            }
            selected_order_label = st.selectbox("Заказ *", list(order_labels.keys()))
            col1, col2 = st.columns(2)
            with col1:
                beds_started = st.number_input("Столов запущено *", min_value=1, value=1, step=1)
            with col2:
                items_per_bed_actual = st.number_input(
                    "Фактически деталей на стол *", min_value=1, value=30, step=1
                )

            submitted = st.form_submit_button("🚀 Запустить печать", use_container_width=True)
            if submitted:
                payload = {
                    "order_id": order_labels[selected_order_label],
                    "beds_started": int(beds_started),
                    "items_per_bed_actual": int(items_per_bed_actual),
                }
                result = api_post("/sessions/start", payload)
                if result:
                    st.success(
                        f"✅ Тираж #{result['id']} запущен! "
                        f"Ожидаемое завершение: {result['expected_end_time'][:16].replace('T', ' ')}."
                    )
                    st.rerun()

    st.markdown("---")

    # -----------------------------------------------------------------------
    # 3d. Collect beds
    # -----------------------------------------------------------------------
    st.subheader("✅ Собрать тираж")
    session_id_input = st.number_input(
        "ID тиража (сессии) для сборки",
        min_value=1,
        step=1,
        value=1,
        help="Введите ID сессии, которую нужно собрать.",
    )

    with st.form("form_collect_session", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            successful_beds = st.number_input("✅ Успешных столов", min_value=0, value=1, step=1)
        with col2:
            failed_beds = st.number_input("❌ Бракованных столов", min_value=0, value=0, step=1)

        submitted = st.form_submit_button("📦 Собрать и списать материал", use_container_width=True)
        if submitted:
            if successful_beds + failed_beds == 0:
                st.warning("⚠️ Укажите хотя бы один стол (успешный или бракованный).")
            else:
                payload = {
                    "successful_beds": int(successful_beds),
                    "failed_beds": int(failed_beds),
                }
                result = api_post(f"/sessions/{int(session_id_input)}/collect", payload)
                if result:
                    st.success(f"✅ Тираж #{int(session_id_input)} успешно собран!")
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("Произведено деталей", f"{result['items_produced']} шт.")
                    col_b.metric("Списано пластика", f"{result['plastic_consumed_g']:,.1f} г")
                    col_c.metric("Остаток материала", f"{result['material_remaining_g']:,.1f} г")
                    st.info(
                        f"Заказ #{result['order_id'] if 'order_id' in result else '—'}: "
                        f"выполнено {result['order_completed_quantity']} шт. | "
                        f"Статус: {result['order_status']}"
                    )


# ===========================================================================
# 4. СКЛАД ДЕТАЛЕЙ (Finished Goods)
# ===========================================================================

elif section == "🏭 Склад деталей":
    st.title("🏭 Склад готовых деталей")

    finished = api_get("/finished-goods/") or []
    parts = api_get("/parts/") or []
    parts_map = {p["id"]: p for p in parts}

    if finished:
        rows = []
        for fg in finished:
            part = parts_map.get(fg["part_id"], {})
            rows.append({
                "ID записи": fg["id"],
                "Деталь": part.get("name", f"part_id={fg['part_id']}"),
                "Количество (шт.)": fg["quantity"],
                "Местонахождение": fg["location"],
                "Материал": part.get("material", "—"),
            })
        df_fg = pd.DataFrame(rows)

        # Summary metrics
        total_items = df_fg["Количество (шт.)"].sum()
        unique_parts = df_fg["Деталь"].nunique()
        col1, col2 = st.columns(2)
        col1.metric("Всего деталей на складе", f"{total_items:,} шт.")
        col2.metric("Уникальных позиций", unique_parts)

        st.markdown("---")
        st.subheader("Детальная таблица")
        st.dataframe(df_fg, use_container_width=True, hide_index=True)

        # -------------------------------------------------------------------
        # Weight calculator expander
        # -------------------------------------------------------------------
        st.markdown("---")
        with st.expander("⚖️ Калькулятор веса", expanded=False):
            st.markdown("Выберите деталь и количество — получите расчётный вес партии.")
            part_names = [r["Деталь"] for r in rows]
            selected_part_name = st.selectbox("Деталь", part_names, key="wc_part")

            selected_row = next((r for r in rows if r["Деталь"] == selected_part_name), None)
            if selected_row:
                part_detail = parts_map.get(
                    next((fg["part_id"] for fg in finished
                          if parts_map.get(fg["part_id"], {}).get("name") == selected_part_name), None),
                    {}
                )
                weight_per_item = part_detail.get("weight_per_item_g", 0)

                qty_calc = st.number_input(
                    "Количество для расчёта (шт.)",
                    min_value=1,
                    value=100,
                    step=10,
                    key="wc_qty",
                )
                total_weight_g = qty_calc * weight_per_item
                total_weight_kg = total_weight_g / 1000

                calc_col1, calc_col2, calc_col3 = st.columns(3)
                calc_col1.metric("Вес одной детали", f"{weight_per_item:.2f} г")
                calc_col2.metric("Расчётный вес партии", f"{total_weight_g:,.1f} г")
                calc_col3.metric("", f"{total_weight_kg:,.3f} кг")

    else:
        st.info("Склад пуст. Запустите и соберите тираж, чтобы пополнить склад.")

        # Show weight calculator even when warehouse is empty if parts exist
        if parts:
            st.markdown("---")
            with st.expander("⚖️ Калькулятор веса", expanded=False):
                st.markdown("Выберите деталь из номенклатуры и введите количество для расчёта веса.")
                part_names_all = [p["name"] for p in parts]
                selected_part_name = st.selectbox("Деталь", part_names_all, key="wc_part_empty")
                part_detail = next((p for p in parts if p["name"] == selected_part_name), None)
                if part_detail:
                    weight_per_item = part_detail["weight_per_item_g"]
                    qty_calc = st.number_input("Количество (шт.)", min_value=1, value=100, step=10, key="wc_qty_empty")
                    total_weight_g = qty_calc * weight_per_item
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Вес одной детали", f"{weight_per_item:.2f} г")
                    c2.metric("Расчётный вес партии", f"{total_weight_g:,.1f} г")
                    c3.metric("", f"{total_weight_g / 1000:,.3f} кг")
