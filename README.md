# Proyecto IoT: Control y Monitoreo de Robot ESP32 con Node-RED

## Descripción
Este proyecto permite controlar y monitorear un robot ESP32 mediante una interfaz Node-RED que se comunica a través de un broker MQTT (Mosquitto). El sistema incluye visualización en dashboard, notificaciones de estado y control remoto.

## Estructura del Proyecto
```
.
├── docker
│   └── docker-compose.yml
├── docs
│   └── assets
│       └── nodered-palette-plugin.png
├── python
│   ├── config.py
│   ├── main.py
│   ├── README.md
│   └── requirements.txt
└── src
    ├── ESP32-flash
    │   └── ESP32_GENERIC-20250809-v1.26.0.bin
    └── nodered
        └── flows.json
```

## Requisitos Previos
- Docker y Docker Compose
- Python 3.8+
- Pip (gestor de paquetes Python)
- Terminal bash (Linux/WSL2 en Windows)
- ESP32 con puerto USB disponible

## Instalación y Configuración

### 1. Levantar infraestructura con Docker
```bash
# Navegar al directorio docker
cd docker

# Iniciar los servicios (Mosquitto + Node-RED)
docker-compose up -d

# Verificar contenedores
docker-compose ps
```

**Servicios disponibles:**
- Node-RED: http://localhost:1880
- Mosquitto MQTT: mqtt://localhost:1883

### 2. Configurar Node-RED
1. Acceder a http://localhost:1880
2. Instalar paleta de Dashboard:
   - Menú > Manage Palette > Install
   - Buscar "node-red-dashboard" e instalar
   ![Instalación Dashboard](docs/assets/nodered-palette-plugin.png)

3. Importar flujo de trabajo:
   - Menú > Import > Select file
   - Cargar `src/nodered/flows.json`
   - Hacer clic en "Deploy"

## Configuración de Direcciones IP y MQTT

### 1. Identificación de IPs en la Red Local

**Para Linux:**
```bash
# Obtener IP del host (equipo donde corre Mosquitto)
hostname -I

# Escanear dispositivos en la red (requiere nmap)
sudo apt install nmap
nmap -sn 192.168.0.0/24 | grep -i "Nmap scan report"
```

**Para Windows:**
```powershell
# Obtener IP local
ipconfig | findstr "IPv4"

# Escanear red (requiere instalación previa)
arp -a
```

### 2. Configuración de IPs en `config.py`

Edita el archivo `python/config.py` con los siguientes valores:

```python
# ========================
# CONFIGURACIÓN MQTT
# ========================
# Para Docker en Linux (usar IP del host):
MQTT_BROKER = "192.168.0.17"  # Reemplazar con IP real
# Alternativas comunes:
# - Si Mosquitto está en mismo equipo: "localhost" o "127.0.0.1"
# - Para Docker en Windows: "host.docker.internal"
MQTT_PORT = 1883
```

### 3. Configuración de Nodos MQTT en Node-RED

1. **Nodo MQTT de Entrada (Subscripción):**
   - Servidor: `mosquitto` (si usas Docker Compose)
     - O usar IP específica si es externo
   - Topic: `iot/device/status`
   - QoS: 1

2. **Nodo MQTT de Salida (Publicación):**
   - Servidor: Mismo que arriba
   - Topic: `iot/device/control`
   - QoS: 1


## Diagrama de Conexiones
```
[ESP32] --> (WiFi) --> [Router] 
                       |     |
                    [Host PC]  [Otros dispositivos]
                       |
[Docker: Mosquitto + Node-RED]
```

**Nota:** Si cambias de red, actualiza tanto `WIFI_SSID`/`WIFI_PASSWORD` como la IP del broker en `config.py`.

### 3. Preparar entorno Python para ESP32

```bash
# Crear y activar entorno virtual
python -m venv myenv

# Linux/macOS:
source myenv/bin/activate

# Windows:
.\myenv\Scripts\activate

# Instalar dependencias
cd python
pip install -r requirements.txt
```

### 4. Flashear firmware en ESP32

**Linux:**
```bash
# Identificar puerto del ESP32
ls /dev/ttyUSB*

# Flashear firmware
esptool.py --chip esp32 --port /dev/ttyUSB0 erase_flash
esptool.py --chip esp32 --port /dev/ttyUSB0 write_flash -z 0x1000 ../src/ESP32-flash/ESP32_GENERIC-20250809-v1.26.0.bin
```

**Windows (usando PowerShell):**
```powershell
# Identificar puerto COM (usar Administrador de Dispositivos)
$port = "COM3"  # Reemplazar con puerto correcto

# Flashear firmware
esptool --chip esp32 --port $port erase_flash
esptool --chip esp32 --port $port write_flash -z 0x1000 ..\src\ESP32-flash\ESP32_GENERIC-20250809-v1.26.0.bin
```

### 5. Subir código al ESP32
```bash
# Configurar WiFi (editar archivo)
nano python/config.py

# Modificar estas líneas:
WIFI_SSID = "TU_SSID"
WIFI_PASSWORD = "TU_PASSWORD"

# Subir código al ESP32
mpremote connect /dev/ttyUSB0 fs cp config.py :
mpremote connect /dev/ttyUSB0 fs cp main.py :

# Reiniciar ESP32
mpremote connect /dev/ttyUSB0 reset
```

## Verificación y Pruebas

### Probar comunicación MQTT
```bash
# Suscribirse a mensajes de estado
mosquitto_sub -h localhost -t "iot/device/status" -v

# Enviar comando de prueba
mosquitto_pub -h localhost -t "iot/device/control" -m '{"command":"move_forward"}'
```

### Acceder al Dashboard
1. Abrir en navegador: http://localhost:1880/ui
2. Deberías ver:
   - Panel de control del robot
   - Estado actual (conectado, moviéndose, error)
   - Última actualización
   - Notificaciones en esquina superior derecha

## Comandos Útiles

### Docker
```bash
# Iniciar servicios
docker-compose up -d

# Detener servicios
docker-compose down

# Ver logs de Node-RED
docker-compose logs -f nodered

# Ver logs de Mosquitto
docker-compose logs -f mosquitto
```

### ESP32
```bash
# Monitor serial
mpremote connect /dev/ttyUSB0 repl

# Subir archivo específico
mpremote connect /dev/ttyUSB0 fs cp main.py :

# Listar archivos en ESP32
mpremote connect /dev/ttyUSB0 fs ls

# Reiniciar dispositivo
mpremote connect /dev/ttyUSB0 reset
```

### MQTT Debugging
```bash
# Ver todos los mensajes
mosquitto_sub -h localhost -t "#" -v

# Publicar mensaje de estado manual
mosquitto_pub -h localhost -t "iot/device/status" -m '{"status":"moving","message":"Prueba manual"}'

# Publicar comando de control
mosquitto_pub -h localhost -t "iot/device/control" -m '{"command":"stop"}'
```

## Solución de Problemas Comunes

### Node-RED no muestra datos
1. Verificar conexión MQTT en Node-RED (nodo debe mostrar "connected")
2. Revisar topics en Node-RED vs config.py
3. Usar nodo Debug para ver mensajes crudos

### ESP32 no se conecta
1. Verificar credenciales WiFi en config.py
2. Revisar conexión USB y puerto
3. Probar con monitor serial: `mpremote connect /dev/ttyUSB0 repl`

### Notificaciones no aparecen
1. Asegurarse que en el nodo Notification está activado "Accept raw HTML"
2. Verificar que el dashboard tiene habilitadas notificaciones
3. Probar con mensaje simple: `mosquitto_pub -h localhost -t "iot/device/status" -m '{"status":"connected"}'`

