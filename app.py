import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="PrintFarm ERP",
    page_icon="🖨️",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def api_get(path: str):
    """GET request — returns parsed JSON or None on error."""
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ Нет соединения с сервером. Убедитесь, что FastAPI запущен на localhost:8000.")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ Ошибка сервера: {e.response.json().get('detail', str(e))}")
        return None


def api_post(path: str, payload: dict):
    """POST request — returns parsed JSON or None on error."""
    try:
        r = requests.post(f"{API_BASE}{path}", json=payload, timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ Нет соединения с сервером. Убедитесь, что FastAPI запущен на localhost:8000.")
        return None
    except requests.exceptions.HTTPError as e:
        detail = ""
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        st.error(f"❌ Ошибка: {detail}")
        return None


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

st.sidebar.image(
    "https://cdn-icons-png.flaticon.com/512/2920/2920277.png",
    width=80,
)
st.sidebar.title("🖨️ PrintFarm ERP")
st.sidebar.markdown("---")

section = st.sidebar.radio(
    "Навигация",
    options=[
        "📦 Номенклатура",
        "🧪 Сырье",
        "📋 Заказы и Печать",
        "🏭 Склад деталей",
    ],
)

st.sidebar.markdown("---")
st.sidebar.caption(f"Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}")


# ===========================================================================
# 1. НОМЕНКЛАТУРА
# ===========================================================================

if section == "📦 Номенклатура":
    st.title("📦 Номенклатура деталей")
    st.markdown("Справочник всех деталей, доступных для печати.")

    parts = api_get("/parts/")

    # --- Catalog table ---
    if parts is not None:
        if parts:
            df = pd.DataFrame(parts)[
                ["id", "name", "material", "items_per_bed", "weight_per_item_g", "print_time_mins"]
            ]
            df.columns = ["ID", "Название", "Материал", "Шт. на столе", "Вес (г/шт)", "Время печати (мин)"]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("ℹ️ Каталог пуст. Добавьте первую деталь ниже.")

    st.markdown("---")

    # --- Create part form ---
    st.subheader("➕ Добавить новую деталь")
    with st.form("form_create_part", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            p_name = st.text_input("Название детали *", placeholder="Например: Кронштейн А")
            p_material = st.text_input("Материал", value="PETG (Черный)")
        with col2:
            p_items_per_bed = st.number_input("Шт. на столе (items_per_bed)", min_value=1, value=30)
            p_weight = st.number_input("Вес одной детали (г)", min_value=0.01, value=2.0, step=0.1, format="%.2f")
            p_print_time = st.number_input("Время печати (мин)", min_value=1, value=300)

        submitted = st.form_submit_button("💾 Создать деталь", use_container_width=True)
        if submitted:
            if not p_name.strip():
                st.warning("⚠️ Укажите название детали.")
            else:
                result = api_post("/parts/", {
                    "name": p_name.strip(),
                    "material": p_material.strip(),
                    "items_per_bed": p_items_per_bed,
                    "weight_per_item_g": p_weight,
                    "print_time_mins": p_print_time,
                })
                if result:
                    st.success(f"✅ Деталь «{result['name']}» (ID {result['id']}) успешно добавлена!")
                    st.rerun()


# ===========================================================================
# 2. СЫРЬЕ
# ===========================================================================

elif section == "🧪 Сырье":
    st.title("🧪 Управление сырьём (пластик)")

    # Try to fetch all materials — there's no GET /materials/ endpoint,
    # so we show the info from the add-response cached in session_state.
    # We surface a helpful note and a metric card if we have data.

    st.info(
        "ℹ️ Для просмотра остатков сырья после получения партии данные отображаются автоматически. "
        "Для первоначального ввода остатка — введите текущий вес как приход.",
        icon="ℹ️",
    )

    # --- Display cached stock from last add operation ---
    if "last_material_response" in st.session_state:
        lm = st.session_state["last_material_response"]
        col1, col2 = st.columns([1, 3])
        with col1:
            st.metric(
                label=f"🧱 {lm['material_name']}",
                value=f"{lm['total_weight_g']:,.0f} г",
                help="Актуальный остаток после последней операции",
            )

    st.markdown("---")
    st.subheader("📥 Оприходовать пластик")

    with st.form("form_add_material", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            mat_name = st.text_input("Тип материала", value="PETG (Черный)")
        with col2:
            mat_weight = st.number_input(
                "Вес партии (г) *",
                min_value=1.0,
                value=9000.0,
                step=100.0,
                format="%.0f",
                help="Введите граммы принятого пластика",
            )

        submitted = st.form_submit_button("➕ Добавить на склад", use_container_width=True)
        if submitted:
            result = api_post("/materials/add", {
                "material_name": mat_name.strip(),
                "weight_to_add_g": mat_weight,
            })
            if result:
                st.session_state["last_material_response"] = result
                st.success(
                    f"✅ Принято **{mat_weight:,.0f} г** материала «{result['material_name']}». "
                    f"Итого на складе: **{result['total_weight_g']:,.0f} г**."
                )
                st.rerun()

    # Quick reference metric cards
    st.markdown("---")
    st.caption("💡 Подсказка: 1 стандартная катушка = 1 000 г | 1 пакет = 9 000 г")


# ===========================================================================
# 3. ЗАКАЗЫ И ПЕЧАТЬ
# ===========================================================================

elif section == "📋 Заказы и Печать":
    st.title("📋 Заказы и управление печатью")

    # Fetch supporting data
    parts = api_get("/parts/") or []

    # -----------------------------------------------------------------------
    # 3a. Active orders
    # -----------------------------------------------------------------------
    st.subheader("📑 Активные заказы")

    orders = api_get("/orders/") if False else None  # no GET /orders/ endpoint
    # Since the API has no GET /orders/ endpoint, show a note and rely on session_state.
    if "orders_list" not in st.session_state:
        st.session_state["orders_list"] = []

    orders_list = st.session_state["orders_list"]

    if orders_list:
        df_orders = pd.DataFrame(orders_list)
        # Friendly column mapping
        display_cols = {
            "id": "ID",
            "customer": "Заказчик",
            "part_id": "ID детали",
            "target_quantity": "Кол-во (план)",
            "completed_quantity": "Кол-во (факт)",
            "status": "Статус",
            "deadline": "Дедлайн",
        }
        df_orders = df_orders[[c for c in display_cols if c in df_orders.columns]].rename(columns=display_cols)
        st.dataframe(df_orders, use_container_width=True, hide_index=True)
    else:
        st.info("ℹ️ Нет сохранённых заказов в текущей сессии. Создайте заказ ниже.")

    st.markdown("---")

    # -----------------------------------------------------------------------
    # 3b. Create order
    # -----------------------------------------------------------------------
    st.subheader("➕ Создать новый заказ")

    if not parts:
        st.warning("⚠️ Сначала добавьте детали в номенклатуру.")
    else:
        part_options = {f"[{p['id']}] {p['name']} ({p['material']})": p["id"] for p in parts}

        with st.form("form_create_order", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                customer = st.text_input("Заказчик *", placeholder="ООО Ромашка")
                selected_part_label = st.selectbox("Деталь *", options=list(part_options.keys()))
            with col2:
                qty = st.number_input("Количество деталей *", min_value=1, value=100)
                deadline_input = st.date_input("Дедлайн (необязательно)", value=None)

            sub_order = st.form_submit_button("📋 Создать заказ", use_container_width=True)
            if sub_order:
                if not customer.strip():
                    st.warning("⚠️ Укажите заказчика.")
                else:
                    payload = {
                        "customer": customer.strip(),
                        "part_id": part_options[selected_part_label],
                        "target_quantity": qty,
                        "deadline": deadline_input.isoformat() if deadline_input else None,
                    }
                    result = api_post("/orders/", payload)
                    if result:
                        st.session_state["orders_list"].append(result)
                        st.success(
                            f"✅ Заказ №{result['id']} для «{result['customer']}» создан! "
                            f"Требуется: {result['target_quantity']} шт."
                        )
                        st.rerun()

    st.markdown("---")

    # -----------------------------------------------------------------------
    # 3c. Start print session
    # -----------------------------------------------------------------------
    st.subheader("🚀 Запустить сеанс печати")

    active_orders = [o for o in st.session_state.get("orders_list", []) if o.get("status") == "В процессе"]

    if not active_orders:
        st.info("ℹ️ Нет активных заказов для запуска печати.")
    else:
        order_labels = {f"Заказ №{o['id']} — {o['customer']}": o["id"] for o in active_orders}

        with st.form("form_start_session", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                sel_order_label = st.selectbox("Заказ *", options=list(order_labels.keys()))
            with col2:
                beds_started = st.number_input("Кол-во столов (beds)", min_value=1, value=1)
            with col3:
                # Pre-fill items_per_bed from the part linked to the selected order
                sel_order_id = order_labels.get(sel_order_label)
                sel_order = next((o for o in active_orders if o["id"] == sel_order_id), None)
                default_ipb = 30
                if sel_order:
                    part_info = next((p for p in parts if p["id"] == sel_order.get("part_id")), None)
                    if part_info:
                        default_ipb = part_info["items_per_bed"]
                items_per_bed = st.number_input("Деталей на стол *", min_value=1, value=default_ipb)

            sub_session = st.form_submit_button("▶️ Запустить печать", use_container_width=True)
            if sub_session:
                result = api_post("/sessions/start", {
                    "order_id": sel_order_id,
                    "beds_started": beds_started,
                    "items_per_bed_actual": items_per_bed,
                })
                if result:
                    if "sessions_list" not in st.session_state:
                        st.session_state["sessions_list"] = []
                    st.session_state["sessions_list"].append(result)
                    end_time = result.get("expected_end_time", "")
                    try:
                        end_dt = datetime.fromisoformat(end_time)
                        end_str = end_dt.strftime("%d.%m.%Y %H:%M")
                    except Exception:
                        end_str = end_time
                    st.success(
                        f"✅ Сеанс №{result['id']} запущен! "
                        f"Ожидаемое окончание: **{end_str}**."
                    )
                    st.rerun()

    st.markdown("---")

    # -----------------------------------------------------------------------
    # 3d. Collect beds
    # -----------------------------------------------------------------------
    st.subheader("✅ Собрать столы (завершить сеанс)")

    sessions_list = st.session_state.get("sessions_list", [])
    active_sessions = [s for s in sessions_list if s.get("status") == "Печатается"]

    if not active_sessions:
        st.info("ℹ️ Нет активных сеансов печати.")
    else:
        session_labels = {
            f"Сеанс №{s['id']} (Заказ №{s['order_id']}) — {s['beds_started']} стол(ов)": s["id"]
            for s in active_sessions
        }

        with st.form("form_collect_beds", clear_on_submit=True):
            sel_sess_label = st.selectbox("Выберите сеанс *", options=list(session_labels.keys()))
            col1, col2 = st.columns(2)
            with col1:
                successful_beds = st.number_input("✅ Успешных столов", min_value=0, value=1)
            with col2:
                failed_beds = st.number_input("❌ Бракованных столов (скрап)", min_value=0, value=0)

            sel_sess_id = session_labels.get(sel_sess_label)

            # Preview calculation
            sel_sess = next((s for s in active_sessions if s["id"] == sel_sess_id), None)
            if sel_sess:
                ipb = sel_sess.get("items_per_bed_actual", 0)
                expected_good = successful_beds * ipb
                expected_scrap = failed_beds * ipb
                total_beds_collect = successful_beds + failed_beds
                st.caption(
                    f"📊 Предварительный расчёт: "
                    f"**{expected_good} шт.** годных | "
                    f"**{expected_scrap} шт.** брак | "
                    f"Всего столов: **{total_beds_collect}**"
                )

            sub_collect = st.form_submit_button("📦 Собрать и записать результат", use_container_width=True)
            if sub_collect:
                if successful_beds + failed_beds == 0:
                    st.warning("⚠️ Укажите хотя бы один стол (успешный или бракованный).")
                else:
                    result = api_post(
                        f"/sessions/{sel_sess_id}/collect",
                        {"successful_beds": successful_beds, "failed_beds": failed_beds},
                    )
                    if result:
                        # Update session status in local cache
                        for s in st.session_state["sessions_list"]:
                            if s["id"] == sel_sess_id:
                                s["status"] = "Собрано"
                        # Update order status in local cache
                        for o in st.session_state["orders_list"]:
                            if o["id"] == result.get("order_id") or True:
                                if o["id"] == sel_sess.get("order_id"):
                                    o["completed_quantity"] = result["order_completed_quantity"]
                                    o["status"] = result["order_status"]

                        st.success(
                            f"✅ Сеанс №{sel_sess_id} собран! "
                            f"Произведено: **{result['items_produced']} шт.** | "
                            f"Израсходовано пластика: **{result['plastic_consumed_g']:,.1f} г** | "
                            f"Остаток пластика: **{result['material_remaining_g']:,.1f} г**"
                        )
                        st.rerun()


# ===========================================================================
# 4. СКЛАД ДЕТАЛЕЙ
# ===========================================================================

elif section == "🏭 Склад деталей":
    st.title("🏭 Склад готовых деталей")

    parts = api_get("/parts/") or []
    parts_map = {p["id"]: p for p in parts}

    # Since the API has no GET /finished_goods/, we track locally in session_state
    # from collect results. Show a helpful message alongside any cached data.

    st.info(
        "ℹ️ Данные склада формируются на основе операций текущей сессии. "
        "Перезапустите приложение для актуализации с базой данных.",
        icon="ℹ️",
    )

    # Build finished goods table from sessions
    fg_data: dict[int, dict] = {}  # part_id -> {name, material, quantity, location, weight_per_item_g}

    for s in st.session_state.get("sessions_list", []):
        if s.get("status") == "Собрано":
            order_id = s.get("order_id")
            order = next(
                (o for o in st.session_state.get("orders_list", []) if o["id"] == order_id),
                None,
            )
            if not order:
                continue
            part_id = order.get("part_id")
            part = parts_map.get(part_id)
            if not part:
                continue

            items_produced = s.get("items_per_bed_actual", 0) * s.get("beds_started", 0)
            # Use collected qty if stored in session
            if part_id not in fg_data:
                fg_data[part_id] = {
                    "Название": part["name"],
                    "Материал": part["material"],
                    "Количество (шт)": 0,
                    "Вес (г/шт)": part["weight_per_item_g"],
                    "Локация": "Главный склад",
                }
            fg_data[part_id]["Количество (шт)"] += items_produced

    # Merge completed_quantity from orders (more accurate)
    for order in st.session_state.get("orders_list", []):
        part_id = order.get("part_id")
        part = parts_map.get(part_id)
        if not part:
            continue
        cq = order.get("completed_quantity", 0)
        if cq > 0:
            if part_id not in fg_data:
                fg_data[part_id] = {
                    "Название": part["name"],
                    "Материал": part["material"],
                    "Количество (шт)": cq,
                    "Вес (г/шт)": part["weight_per_item_g"],
                    "Локация": "Главный склад",
                }
            else:
                # Use order's completed_quantity as source of truth
                fg_data[part_id]["Количество (шт)"] = cq

    if fg_data:
        df_fg = pd.DataFrame(list(fg_data.values()))
        df_fg["Общий вес (г)"] = (df_fg["Количество (шт)"] * df_fg["Вес (г/шт)"]).round(1)

        # Summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📦 Позиций на складе", len(df_fg))
        with col2:
            st.metric("🔢 Всего деталей", f"{df_fg['Количество (шт)'].sum():,}")
        with col3:
            st.metric("⚖️ Общий вес", f"{df_fg['Общий вес (г)'].sum():,.0f} г")

        st.markdown("---")
        st.dataframe(df_fg, use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ Склад пуст. Выполните сбор столов в разделе «Заказы и Печать».")

    # -----------------------------------------------------------------------
    # Weight calculator expander
    # -----------------------------------------------------------------------
    st.markdown("---")
    with st.expander("⚖️ Калькулятор веса", expanded=False):
        st.markdown("Рассчитайте ожидаемый вес партии деталей.")

        if not parts:
            st.warning("Нет деталей в номенклатуре.")
        else:
            part_options_wc = {f"[{p['id']}] {p['name']} — {p['weight_per_item_g']} г/шт": p for p in parts}
            sel_part_label = st.selectbox(
                "Выберите деталь",
                options=list(part_options_wc.keys()),
                key="wc_part",
            )
            qty_calc = st.number_input(
                "Количество деталей",
                min_value=1,
                value=100,
                key="wc_qty",
            )

            sel_part_wc = part_options_wc[sel_part_label]
            total_weight = qty_calc * sel_part_wc["weight_per_item_g"]

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📦 Деталей", f"{qty_calc:,} шт.")
            with col2:
                st.metric("⚖️ Вес на штуку", f"{sel_part_wc['weight_per_item_g']:.2f} г")
            with col3:
                st.metric("🏋️ Итоговый вес", f"{total_weight:,.1f} г")

            if total_weight >= 1000:
                st.info(f"ℹ️ Это примерно **{total_weight / 1000:.2f} кг** или **{total_weight / 9000:.1f}** стандартных пакетов.")
