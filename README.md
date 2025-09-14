# 🚖 inDrive Map Prototype

Прототип визуализации геотреков поездок для анализа **спроса (пикапы)** и **назначений (дропоффы)** на карте.  
Цель: помочь водителям видеть, где чаще всего начинаются и заканчиваются поездки.

---

## 📌 Возможности

- Построение **тепловых карт (H3 hexagons)** для старта и финиша поездок.
- Отображение **прямых линий "A → B"** между точкой пикапа и дропоффа.
- Подсветка выбранной поездки с выделением стартовой (зелёной) и конечной (красной) точек.
- Удобное переключение режимов через **Streamlit sidebar**.

---

## 🛠️ Технологии

- [Python 3.10+](https://www.python.org/)
- [Streamlit](https://streamlit.io/)
- [Folium](https://python-visualization.github.io/folium/)
- [H3](https://h3geo.org/) (hexagonal grid system)
- [Pandas](https://pandas.pydata.org/)

---

## 🚀 Запуск проекта

1. Клонировать репозиторий:
   ```bash
   git clone https://github.com/DaDiaz3/inDrive-map-prototype.git
   cd inDrive-map-prototype

2.	Создать виртуальное окружение и установить зависимости:
   python3 -m venv .venv
   source .venv/bin/activate   # для Mac/Linux
   .venv\Scripts\activate      # для Windows

   pip install -r requirements.txt

3.	Запустить Streamlit:
  streamlit run app.py

📂 Структура проекта
.
├── app.py                # основной интерфейс Streamlit
├── processing.py         # функции обработки данных и H3-агрегации
├── data/
│   ├── .gitkeep          # папка для данных (датасет не хранится в GitHub)
├── requirements.txt      # список зависимостей
└── README.md

📊 Данные

Файл с сырыми геотреками (geo_locations_astana_hackathon) не загружен в репозиторий (размер >100MB).
Его необходимо положить в папку data/ локально.

Формат: CSV или Parquet с колонками:
	•	randomized_id — ID поездки
	•	lat, lng — координаты
	•	alt, spd, azm — дополнительные параметры

⸻

📝 Пример использования
	•	Переключитесь на режим “H3 теплокарта” → увидите зоны спроса и назначения.
	•	Переключитесь на “Линии start→finish” → отобразятся прямые маршруты.
	•	В сайдбаре можно выбрать конкретную поездку для выделения.
