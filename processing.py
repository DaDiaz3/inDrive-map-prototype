import pandas as pd
import numpy as np
import h3
import streamlit as st
import json

# Константа разрешения H3
H3_RESOLUTION = 9

# ---- Универсальная обёртка для конвертации (v3 и v4) ----
if hasattr(h3, "latlng_to_cell"):  # h3 v4+
    def latlng_to_h3(lat, lng, res):
        return h3.latlng_to_cell(lat, lng, res)
elif hasattr(h3, "geo_to_h3"):     # h3 v3.x
    def latlng_to_h3(lat, lng, res):
        return h3.geo_to_h3(lat, lng, res)
else:
    raise ImportError("В этой версии h3 нет функций latlng_to_cell или geo_to_h3")

# ---- Универсальная обёртка для границ ячейки (v3 и v4) ----
def h3_boundary(idx):
    # v4+: cell_to_boundary c geo_json=True → (lon, lat)
    if hasattr(h3, "cell_to_boundary"):
        try:
            return h3.cell_to_boundary(idx, geo_json=True)
        except TypeError:
            # сборки без geo_json: вернут (lat, lon) → перевернём
            coords = h3.cell_to_boundary(idx)
            return [(lon, lat) for lat, lon in coords]

    # v3.x: h3_to_geo_boundary, иногда умеет geo_json=True
    if hasattr(h3, "h3_to_geo_boundary"):
        try:
            return h3.h3_to_geo_boundary(idx, geo_json=True)  # (lon, lat)
        except TypeError:
            latlon = h3.h3_to_geo_boundary(idx)               # (lat, lon)
            return [(lon, lat) for lat, lon in latlon]

    raise RuntimeError("H3 boundary function not found in installed h3.")


@st.cache_data(ttl=3600)
def load_and_process_points(filepath):
    """
    Загружаем данные, чистим, находим пикапы и дропоффы, аггрегируем в H3-зоны.
    """
    # 1) Загрузка
    col_types = {
        'randomized_id': str,
        'lat': float,
        'lng': float,
        'alt': float,
        'spd': float,
        'azm': float
    }

    try:
        df = pd.read_csv(filepath, dtype=col_types, sep=',')
        st.write(f"✅ Шаг 1: Файл CSV успешно загружен. Всего строк в файле: {len(df)}")
    except FileNotFoundError:
        st.error(f"Ошибка: Файл данных не найден по пути: {filepath}")
        return None, None
    except Exception:
        try:
            df = pd.read_parquet(filepath)
            st.write(f"✅ Шаг 1: Файл Parquet успешно загружен. Всего строк: {len(df)}")
        except Exception as e_parq:
            st.error(f"Не удалось прочитать файл ни как CSV, ни как Parquet. Ошибка: {e_parq}")
            return None, None

    if df.empty:
        st.error("Файл загружен, но он пустой.")
        return None, None

    # 1.1) Чистка
    df = df.dropna(subset=['lat', 'lng'])
    st.write(f"✅ Шаг 1.1: Строки с пустыми lat/lng удалены. Осталось строк: {len(df)}")

    # 2) Пикапы (первая точка по trip-id)
    st.write("Группировка... Поиск точек СТАРТА (Пикапы)...")
    pickups_df = df.groupby('randomized_id').first().reset_index()
    st.write(f"✅ Шаг 2: Найдено Пикапов (уникальных ID поездок): {len(pickups_df)}")

    # 3) Дропоффы (последняя точка по trip-id)
    st.write("Группировка... Поиск точек ФИНИША (Дропоффы)...")
    dropoffs_df = df.groupby('randomized_id').last().reset_index()
    st.write(f"✅ Шаг 3: Найдено Дропоффов (уникальных ID поездок): {len(dropoffs_df)}")

    # 4) H3 агрегация
    st.write("Агрегация пикапов по зонам H3...")
    pickups_h3 = aggregate_points_to_h3(pickups_df)
    st.write(f"✅ Шаг 4: Пикапы сгруппированы в {len(pickups_h3)} уникальных H3-зон.")

    st.write("Агрегация дропоффов по зонам H3...")
    dropoffs_h3 = aggregate_points_to_h3(dropoffs_df)
    st.write(f"✅ Шаг 5: Дропоффы сгруппированы в {len(dropoffs_h3)} уникальных H3-зон.")

    if pickups_h3.empty or dropoffs_h3.empty:
        st.warning("⚠️ Данные обработаны, но на выходе 0 зон. Возможно, H3 не смог обработать координаты.")

    return pickups_h3, dropoffs_h3


def aggregate_points_to_h3(df):
    """
    Агрегируем точки в H3-зоны.
    """
    def geo_to_h3_func(row):
        try:
            lat_f = float(row['lat'])
            lng_f = float(row['lng'])
            return latlng_to_h3(lat_f, lng_f, H3_RESOLUTION)
        except Exception as e:
            if not hasattr(st.session_state, 'h3_error_shown'):
                st.error(f"КРИТИЧЕСКАЯ ОШИБКА H3: {e}. Строка: lat={row.get('lat')}, lng={row.get('lng')}")
                st.session_state.h3_error_shown = True
            return None

    df['h3_index'] = df.apply(geo_to_h3_func, axis=1)
    df = df.dropna(subset=['h3_index'])

    if df.empty:
        return pd.DataFrame(columns=['h3_index', 'count'])

    demand_count = df.groupby('h3_index').size().reset_index(name='count')
    return demand_count


def get_geojson_boundaries(h3_df):
    """
    Получаем полигоны H3 для отображения на карте. Совместимо с h3 v3 и v4.
    """
    if h3_df is None or h3_df.empty:
        return {"type": "FeatureCollection", "features": []}

    features = []
    for _, row in h3_df.iterrows():
        try:
            coords = h3_boundary(row['h3_index'])   # список точек в (lon, lat)
            geometry = {'type': 'Polygon', 'coordinates': [coords]}
            feature = {
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "h3_index": str(row['h3_index']),
                    "count": int(row['count'])
                }
            }
            features.append(feature)
        except Exception as e:
            if not hasattr(st.session_state, 'boundary_error_shown'):
                st.error(f"ОШИБКА РИСОВАНИЯ ГРАНИЦ: {e}. Индекс: {row.get('h3_index')}")
                st.session_state.boundary_error_shown = True
            continue

    return {"type": "FeatureCollection", "features": features}

@st.cache_data(ttl=3600)
def load_start_finish_segments(filepath, max_trips: int | None = None):
    """
    Готовит таблицу отрезков start→finish по каждой поездке.
    Возвращает столбцы: randomized_id, lat_start, lng_start, lat_end, lng_end.
    max_trips — опционально ограничить число линий (чтоб не повесить карту).
    """
    col_types = {
        'randomized_id': str,
        'lat': float,
        'lng': float,
        'alt': float,
        'spd': float,
        'azm': float
    }
    try:
        df = pd.read_csv(filepath, dtype=col_types, sep=',')
    except Exception:
        df = pd.read_parquet(filepath)

    df = df.dropna(subset=['lat', 'lng'])

    # Берём первую и последнюю точки в исходном порядке файла
    # (как ты делал для pickups/dropoffs)
    pickups_df  = df.groupby('randomized_id').first().reset_index()
    dropoffs_df = df.groupby('randomized_id').last().reset_index()

    seg = pickups_df.merge(
        dropoffs_df, on='randomized_id', suffixes=('_start', '_end')
    )[["randomized_id", "lat_start", "lng_start", "lat_end", "lng_end"]]

    if max_trips is not None and max_trips > 0:
        seg = seg.head(int(max_trips))

    return seg

def draw_start_finish_lines(map_center, segments_df):
    """
    Рисует на Folium прямые отрезки start→finish.
    map_center = [lat, lng] для начального центра карты.
    """
    import folium

    m = folium.Map(location=map_center, zoom_start=11, tiles="CartoDB dark_matter")

    for _, r in segments_df.iterrows():
        start = [float(r["lat_start"]), float(r["lng_start"])]
        end   = [float(r["lat_end"]),   float(r["lng_end"])]

        folium.PolyLine(
            locations=[start, end],
            weight=2, opacity=0.7
        ).add_to(m)

        # маркеры начала/конца (необязательно)
        folium.CircleMarker(start, radius=3, color="green", fill=True).add_to(m)
        folium.CircleMarker(end,   radius=3, color="red",   fill=True).add_to(m)

    return m