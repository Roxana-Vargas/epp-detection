# 🦺 Sistema de Detección de EPP con alertas por Telegram

Detecta Equipo de Protección Personal (casco, chaleco, guantes, gafas…) en
fotografías usando un modelo de **Roboflow**, y envía una **alerta por Telegram**
cuando una persona no lleva el EPP obligatorio.

Proyecto pensado como entregable para un curso de Machine Learning: muestra
despliegue de un modelo como **API REST**, lógica de negocio, persistencia,
métricas e integración con un servicio externo.

## Arquitectura

```
Foto → API (FastAPI) → Modelo Roboflow (REST) → Reglas EPP → ¿Falta EPP?
                                                               ├─ Sí → Alerta Telegram (imagen anotada)
                                                               └─ Historial (SQLite) + estadísticas
```

## Funcionalidades

- **API REST** documentada automáticamente (`/docs`).
- Inferencia contra **Roboflow** vía HTTP (sin instalar PyTorch).
- **Reglas configurables**: qué EPP es obligatorio.
- **Imagen anotada** con cajas de detección (verde = EPP, rojo = violación).
- **Alertas Telegram** con foto y detalle de lo que falta + anti-spam (cooldown).
- **Historial en SQLite** y endpoint `/stats` (% de cumplimiento).
- **Interfaz web** para subir fotos (`/`).
- **Procesamiento por lotes** de una carpeta (`batch.py`).
- **Detección en vivo** desde webcam o archivo de video, con cajas dibujadas en
  tiempo real sobre el video (sección "En vivo" del panel).
- **Dockerfile** y **tests**.

## Requisitos previos

1. **Cuenta Roboflow** (gratis): https://roboflow.com
   - Usa un modelo público de EPP (busca "PPE detection" en Roboflow Universe)
     o entrena el tuyo. Copia tu `API key` y el `model_id` (formato `modelo/version`).
2. **Bot de Telegram**:
   - Habla con [@BotFather](https://t.me/BotFather) → `/newbot` → copia el **token**.
   - Habla con [@userinfobot](https://t.me/userinfobot) para obtener tu **chat_id**.

## Instalación

```bash
# 1. Crear entorno virtual
python -m venv .venv
.venv\Scripts\activate        # Windows PowerShell
# source .venv/bin/activate   # Linux/Mac

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables
copy .env.example .env        # Windows
# cp .env.example .env        # Linux/Mac
# …edita .env con tus claves de Roboflow y Telegram
```

> ⚠️ **Importante:** Ajusta `PPE_CLASSES`, `REQUIRED_PPE` y `VIOLATION_CLASSES`
> en el `.env` a los **nombres exactos de las clases de tu modelo de Roboflow**
> (cada modelo usa nombres distintos, p. ej. `helmet`, `Hardhat`, `NO-Hardhat`…).

## Ejecutar

```bash
uvicorn app.main:app --reload
```

Abre:
- Interfaz web: http://localhost:8000
- Documentación API: http://localhost:8000/docs

### Probar la API con curl

```bash
curl -X POST http://localhost:8000/detect -F "file=@obrero.jpg"
```

### Procesar una carpeta

```bash
python batch.py ./imagenes
```

### Tests

```bash
pip install pytest
pytest
```

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/detect` | Sube foto, detecta EPP, alerta si falta |
| POST | `/detect/frame` | Frame de cámara/video en vivo (ligero, throttle de guardado) |
| GET | `/annotated/{id}` | Imagen anotada de una inspección |
| GET | `/history?limit=N` | Historial de inspecciones |
| GET | `/stats` | Métricas de cumplimiento |
| GET | `/health` | Estado del sistema |
| GET | `/docs` | Swagger UI |

## Docker

```bash
docker build -t epp-detection .
docker run -p 8000:8000 --env-file .env epp-detection
```

## Ideas para ampliar (subir nota)

- Autenticación por API key en los endpoints.
- Soporte de **cámara en vivo / RTSP** procesando frames.
- Dashboard con gráficas (Chart.js) de cumplimiento por día.
- Detección por persona (asociar EPP a cada trabajador detectado).
- Exportar reportes en PDF/CSV.
