import streamlit as st
import folium
import processing  # наш модуль с обработкой и рисованием
import branca.colormap as cm
import pandas as pd
from streamlit_folium import folium_static

# ---------------------------------------------------------------------------------
# ШАГ ПОДКЛЮЧЕНИЯ ДАННЫХ: меняем только это
# ---------------------------------------------------------------------------------
DATASET_PATH = "data/geo_locations_astana_hackathon"

# ---------------------------------------------------------------------------------
# ------------------- ДАЛЬШЕ КОД МЕНЯТЬ НЕ НУЖНО ----------------------------------
# ---------------------------------------------------------------------------------

st.set_page_config(layout="wide", page_title="Анализ Геотреков (Прототип)")
st.title("🗺️ Прототип: Тепловые карты Пикапов и Дропоффов")
st.markdown("Анализ первых и последних точек треков для выявления зон спроса и назначения.")

# --- 1. Загрузка и базовая обработка (pickups/dropoffs -> H3-агрегация) ---
pickups_demand, dropoffs_demand = processing.load_and_process_points(DATASET_PATH)
if pickups_demand is None:
    st.error("Критическая ошибка: Загрузка данных не удалась. Останавливаем приложение.")
    st.stop()

st.success("Все данные обработаны и загружены из кэша!")
st.markdown("---")

# ----- БЛОК ОТЛАДКИ (можно скрыть позже) -----
st.subheader("ОТЛАДКА: Смотрим, что вернула обработка")
st.write("Датафрейм Пикапов (первые 5 строк):")
st.dataframe(pickups_demand.head())
st.write(f"**Всего найдено уникальных H3-зон для Пикапов: {len(pickups_demand)}**")
st.write("Датафрейм Дропоффов (первые 5 строк):")
st.dataframe(dropoffs_demand.head())
st.write(f"**Всего найдено уникальных H3-зон для Дропоффов: {len(dropoffs_demand)}**")
st.markdown("---")
# ----- КОНЕЦ БЛОКА ОТЛАДКИ -----

# --- 2. Боковая панель ---
st.sidebar.header("Управление картой")
map_type = st.sidebar.radio(
    "Выберите тип тепловой карты:",
    ('Карта Спроса (Пикапы)', 'Карта Назначений (Дропоффы)')
)

st.sidebar.markdown("---")
st.sidebar.subheader("Ценность (Value)")
st.sidebar.info(
    """
    **Проблема:** Водители не знают, где концентрируется спрос (пикапы) и куда чаще всего едут люди (дропоффы).

    **Решение:** Этот прототип агрегирует анонимные точки СТАРТА и ФИНИША всех поездок.
    """
)

# новый переключатель режима отображения
view_mode = st.sidebar.radio(
    "Режим отображения",
    ["H3 теплокарта", "Линии start→finish"],
    index=0
)

# --- 3. Ветка "Линии start→finish" (отрезки А→Б без трека) ---
if view_mode == "Линии start→finish":
    st.header("Линии от точки А (пикап) до точки Б (дропофф)")

    # Ограничитель, чтобы не повесить браузер
    max_trips = st.sidebar.number_input(
        "Сколько линий показать (первые N поездок)",
        min_value=100, max_value=10000, value=2000, step=100
    )

    seg = processing.load_start_finish_segments(DATASET_PATH, max_trips=max_trips)

    if seg.empty:
        st.warning("Нет сегментов для отображения.")
        st.stop()

    # Выбор конкретной поездки для выделения
    selected_trip = st.sidebar.selectbox(
        "Выбери поездку для выделения",
        options=seg["randomized_id"].unique()
    )

    # Центр карты вычисляем по данным (или fallback — Астана)
    try:
        map_center = [float(seg["lat_start"].mean()), float(seg["lng_start"].mean())]
        if any(pd.isna(map_center)):
            map_center = [51.12, 71.43]
    except Exception:
        map_center = [51.12, 71.43]

    # Рисуем карту
    m = folium.Map(location=map_center, zoom_start=11, tiles="CartoDB dark_matter")

    for _, r in seg.iterrows():
        start = [float(r["lat_start"]), float(r["lng_start"])]
        end   = [float(r["lat_end"]),   float(r["lng_end"])]

        if r["randomized_id"] == selected_trip:
            color = "red"
            weight = 4
            opacity = 1.0
        else:
            color = "cyan"
            weight = 2
            opacity = 0.2  # остальные бледные

        # Линия
        folium.PolyLine(
            locations=[start, end],
            color=color,
            weight=weight,
            opacity=opacity,
            tooltip=f"Trip ID: {r['randomized_id']}"
        ).add_to(m)

        # Точка А (Start) — зелёная
        folium.CircleMarker(
            location=start,
            radius=4,
            color="green",
            fill=True,
            fill_color="green",
            fill_opacity=1,
            tooltip="Start"
        ).add_to(m)

        # Точка Б (Finish) — красная
        folium.CircleMarker(
            location=end,
            radius=4,
            color="red",
            fill=True,
            fill_color="red",
            fill_opacity=1,
            tooltip="Finish"
        ).add_to(m)

    folium_static(m, width=1200, height=600)

    st.info(f"Выделена поездка: {selected_trip}. Старт = зелёная точка, финиш = красная точка.")
    st.subheader("Примеры сегментов (первые строки):")
    st.dataframe(seg.head(20))

    st.stop()

# --- 4. Ветка H3 теплокарты (твой текущий функционал) ---
# выбираем данные и заголовок
if map_type == 'Карта Спроса (Пикапы)':
    st.header("Карта Спроса (Где люди начинают поездки)")
    data_to_show = pickups_demand
    legend_title = "Кол-во Пикапов"
else:
    st.header("Карта Назначений (Куда люди чаще всего едут)")
    data_to_show = dropoffs_demand
    legend_title = "Кол-во Дропоффов"

# проверка на пустоту
if data_to_show.empty:
    st.warning(f"Данные для '{map_type}' пусты. Нечего отображать. (Это подтверждает лог отладки выше).")
    st.stop()

# рендер H3-слоя
map_center = [51.12, 71.43]  # Астана
m = folium.Map(location=map_center, zoom_start=11, tiles="CartoDB dark_matter")

# строим полигоны H3
geojson_data = processing.get_geojson_boundaries(data_to_show)
if not geojson_data.get("features"):
    st.error("Не удалось построить полигоны H3 — список features пуст. Проверь версию h3 и функции границ.")
    st.stop()

try:
    # цветовая шкала
    min_count = data_to_show['count'].min()
    max_count = data_to_show['count'].max()
    colormap = cm.linear.YlOrRd_09.scale(vmin=min_count, vmax=max_count)
    colormap.caption = legend_title

    # стиль гексагонов
    style_function = lambda x: {
        'fillColor': colormap(x['properties']['count']),
        'color': 'none',
        'fillOpacity': 0.7,
        'weight': 1,
    }

    # слой GeoJSON
    folium.GeoJson(
        data=geojson_data,
        style_function=style_function,
        tooltip=folium.GeoJsonTooltip(
            fields=['h3_index', 'count'],
            aliases=['Зона H3:', 'Кол-во:'],
            sticky=True
        )
    ).add_to(m)

    # легенда
    colormap.add_to(m)

    with st.spinner("Отрисовка карты... (Это может занять время)"):
        folium_static(m, width=1200, height=600)

except Exception as e:
    st.error(f"Ошибка при отрисовке карты (данные были загружены, но карта упала): {e}")

# таблица топ-20
st.subheader(f"Топ 20 'горячих' зон ({map_type}):")
st.dataframe(
    data_to_show[['h3_index', 'count']]
    .sort_values('count', ascending=False)
    .head(20)
    .set_index('h3_index')
)