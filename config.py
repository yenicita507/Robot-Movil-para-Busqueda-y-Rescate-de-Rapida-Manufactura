"""
Archivo de configuración para ESP32 Robot Controller + Sensores Multi-propósito
Versión Unificada - Control de Robot con MPU6050, Ultrasónico, SCD30 y MQ-2
"""

# ========================
# CONFIGURACIÓN GENERAL
# ========================
SAFE_START = False  # True para iniciar sin ejecutar loop principal (modo seguro)
DEBUG_ENABLED = True
DEVICE_NAME = "ESP32-Robot-MultiSensor-MQ2-01"
LOCATION = "Lab-Principal"

# ========================
# CONFIGURACIÓN WIFI
# ========================
WIFI_SSID = "ROBMA"
WIFI_PASSWORD = "ROBMA2023"
WIFI_TIMEOUT = 30  # segundos

# ========================  
# CONFIGURACIÓN MQTT
# ========================
MQTT_BROKER = "192.168.2.103"
MQTT_PORT = 1883                        
MQTT_USER = None
MQTT_PASSWORD = None
MQTT_KEEPALIVE = 180  # segundos

# ========================
# TOPICS MQTT - ROBOT
# ========================
TOPIC_STATUS = "iot/device/status" 
TOPIC_COMMAND = "iot/device/control"
TOPIC_HEARTBEAT = "iot/device/heartbeat"

# ========================
# TOPICS MQTT - SENSORES
# ========================
TOPIC_ULTRASONIC = "iot/device/sensor/ultrasonic"
TOPIC_MPU_DATA = "iot/sensor/mpu6050/data"
TOPIC_MPU_STATUS = "iot/sensor/mpu6050/status"
TOPIC_MPU_HEARTBEAT = "iot/sensor/mpu6050/heartbeat"
TOPIC_SCD30_DATA = "iot/sensor/data"
TOPIC_SCD30_STATUS = "iot/sensor/status"
TOPIC_SCD30_HEARTBEAT = "iot/sensor/scd30/heartbeat"
TOPIC_MQ2_STATUS = "iot/sensor/mq2/status"
TOPIC_MQ2_DATA = "iot/sensor/mq2/data"
TOPIC_MQ2_ALERT = "iot/sensor/mq2/alert"

# ========================
# CONFIGURACIÓN HARDWARE - I2C
# ========================
# Pines I2C (compartidos entre todos los dispositivos)
I2C_SCL_PIN = 22
I2C_SDA_PIN = 21
I2C_FREQUENCY = 100000

# ========================
# CONFIGURACIÓN HARDWARE - MOTORES
# ========================
# Pines PWM de motores
MOTOR_PINS = {
    1: 16,  # Motor 1 - GPIO 16
    2: 17,  # Motor 2 - GPIO 17  
    3: 18,  # Motor 3 - GPIO 18
    4: 19   # Motor 4 - GPIO 19
}

# Frecuencia PWM
PWM_FREQUENCY = 1000

# Direcciones I2C PCF8574 (Control de dirección de motores)
PCF8574_ADDRESSES = {
    1: 0x20,  # PCF1 - Motores 1 y 2
    2: 0x21   # PCF2 - Motores 3 y 4
}

# ========================
# CONFIGURACIÓN SENSOR ULTRASÓNICO
# ========================
ULTRASONIC_ADDR = 0x23  # Dirección I2C del sensor
TRIG_BIT = 2            # Bit para el trigger
ECHO_BIT = 1            # Bit para el echo
SOUND_SPEED = 0.0343    # cm/μs
ULTRASONIC_INTERVAL = 1000  # ms entre mediciones

# ========================
# CONFIGURACIÓN SENSOR MPU6050
# ========================
MPU6050_ADDR = 0x68  # Dirección I2C del MPU6050
MPU_READ_INTERVAL = 1.0  # segundos entre lecturas del MPU6050

# ========================
# CONFIGURACIÓN SENSOR SCD30
# ========================
SCD30_ADDRESS = 0x61  # Dirección I2C del SCD30
SCD30_READ_INTERVAL = 5  # segundos entre lecturas

# ========================
# CALIBRACIÓN SENSOR SCD30
# ========================
SENSOR_CALIBRATION = {
    "temperature_offset": -3,
    "humidity_slope": 1.3956,
    "humidity_intercept": -22.985
}

# ========================
# CONFIGURACIÓN SENSOR MQ-2 (GAS/HUMO)
# ========================
# Configuración ADS1115 (Conversor ADC para MQ-2)
ADS1115_ADDR = 0x48
MQ2_SDA_PIN = 21  # Usa el mismo bus I2C
MQ2_SCL_PIN = 22  # Usa el mismo bus I2C
MQ2_CHANNEL = 0   # Canal del ADS1115 para el MQ-2
MQ2_GAIN = 0x0200  # GAIN_ONE (±4.096V)

# Parámetros del sensor MQ-2
MQ2_RL = 10.0  # Resistencia de carga en kilo-ohms
MQ2_RO_CLEAN_AIR = 9.8  # Relación RS/R0 en aire limpio
MQ2_VOLTAGE_SUPPLY = 5.0  # Voltaje de alimentación

# Parámetros para cálculo de humo (Smoke)
MQ2_SMOKE_M = -0.485  # Pendiente para humo
MQ2_SMOKE_B = 1.51   # Intersección para humo

# Umbrales para alertas de humo (en PPM)
SMOKE_THRESHOLDS = {
    "normal": 200,      # PPM - Aire limpio, niveles seguros
    "advertencia": 500, # PPM - Presencia detectable de humo
    "peligro": 1000,    # PPM - Concentración peligrosa
    "critico": 2000     # PPM - Nivel extremadamente peligroso
}

# Registros ADS1115
ADS1115_REG_CONFIG = 0x01
ADS1115_REG_CONVERSION = 0x00

# Configuración MUX para canales ADS1115
ADS1115_MUX_CONFIG = [0x4000, 0x5000, 0x6000, 0x7000]

# Intervalo de lectura del MQ-2
MQ2_READ_INTERVAL = 2  # segundos entre lecturas

# ========================
# BITS DE CONTROL PCF8574
# ========================
PCF_CONTROL_BITS = {
    "m1_horario": 0b11110110,           # ~0b00000101
    "m1_antihorario": 0b11111010,       # ~0b00001001
    "m2_horario": 0b11100111 ,          # ~0b00100100
    "m2_antihorario": 0b11011011,       # ~0b00011000
    "m3_horario": 0b11111010,           # ~0b00001001  
    "m3_antihorario": 0b11110110,       # ~0b00000101
    "m4_horario": 0b11011011,           # ~0b00100100
    "m4_antihorario": 0b11100111,       # ~0b00011000
}

# ========================
# CONFIGURACIÓN DE SISTEMA
# ========================
HEARTBEAT_INTERVAL = 30                 # segundos
RECONNECT_DELAY = 5                     # segundos
MAX_RECONNECT_ATTEMPTS = 10             

# ========================
# CONFIGURACIÓN DE MOVIMIENTOS
# ========================
ROBOT_MOVEMENTS = {
    "lateral_superior_izquierda": {
        "M1": {"pwm": 1023, "direction": "horario"},
        "M2": {"pwm": 1023, "direction": "horario"}, 
        "M3": {"pwm": 420, "direction": "horario"},
        "M4": {"pwm": 420, "direction": "horario"}
    },
    "lateral_superior_derecha": {
        "M1": {"pwm": 420, "direction": "horario"},
        "M2": {"pwm": 420, "direction": "horario"},
        "M3": {"pwm": 1023, "direction": "horario"},
        "M4": {"pwm": 1023, "direction": "horario"}
    },
    "lateral_inferior_izquierda": {
        "M1": {"pwm": 1023, "direction": "antihorario"},
        "M2": {"pwm": 1023, "direction": "antihorario"},
        "M3": {"pwm": 420, "direction": "antihorario"},
        "M4": {"pwm": 420, "direction": "antihorario"}
    },
    "lateral_inferior_derecha": {
        "M1": {"pwm": 420, "direction": "antihorario"},
        "M2": {"pwm": 420, "direction": "antihorario"},
        "M3": {"pwm": 1023, "direction": "antihorario"},
        "M4": {"pwm": 1023, "direction": "antihorario"}
    },
    "adelante": {
        "M1": {"pwm": 1023, "direction": "horario"},
        "M2": {"pwm": 1023, "direction": "horario"},
        "M3": {"pwm": 1023, "direction": "horario"},
        "M4": {"pwm": 1023, "direction": "horario"}
    },
    "atras": {
        "M1": {"pwm": 1023, "direction": "antihorario"},
        "M2": {"pwm": 1023, "direction": "antihorario"},
        "M3": {"pwm": 1023, "direction": "antihorario"},
        "M4": {"pwm": 1023, "direction": "antihorario"}
    },
    "derecha": {
        "M1": {"pwm": 1023, "direction": "horario"},
        "M2": {"pwm": 1023, "direction": "horario"},
        "M3": {"pwm": 1023, "direction": "antihorario"},
        "M4": {"pwm": 1023, "direction": "antihorario"}
    },
    "izquierda": {
        "M1": {"pwm": 1023, "direction": "antihorario"},
        "M2": {"pwm": 1023, "direction": "antihorario"},
        "M3": {"pwm": 1023, "direction": "horario"},
        "M4": {"pwm": 1023, "direction": "horario"}
    },
    "stop": {
        "M1": {"pwm": 0, "direction": "horario"},
        "M2": {"pwm": 0, "direction": "horario"},
        "M3": {"pwm": 0, "direction": "horario"},
        "M4": {"pwm": 0, "direction": "horario"}
    }
}

# Mapeo de comandos alternativos
COMMAND_MAPPING = {
    "parar": "stop",
    "detener": "stop",
    "forward": "adelante",
    "backward": "atras",
    "back": "atras",
    "left": "izquierda",
    "right": "derecha"
}

# ========================
# CONFIGURACIONES DE SEGURIDAD
# ========================
SAFETY_CONFIG = {
    # Robot
    "max_pwm": 1023,
    "min_pwm": 0,
    "emergency_stop_enabled": True,
    "auto_stop_timeout": 30,
    "watchdog_enabled": False,
    "obstacle_distance": 5,  # cm - distancia mínima para detenerse automáticamente
    
    # Sensores
    "max_sensor_read_errors": 5,
    "auto_reconnect": True,
    
    # MQ-2 (Gas/Humo)
    "max_adc_value": 32767,
    "min_adc_value": -32768,
    "voltage_reference": 4.096,
    "gas_emergency_stop": True,  # Detener robot si se detecta humo crítico
    "gas_alert_threshold": "peligro"  # Nivel que activa parada de emergencia
}

# ========================
# DIRECCIONES I2C RESUMEN
# ========================
# Para referencia rápida de todos los dispositivos I2C:
I2C_DEVICES = {
    "PCF8574_1": 0x20,      # Control motores 1 y 2
    "PCF8574_2": 0x21,      # Control motores 3 y 4
    "ULTRASONIC": 0x23,     # Sensor ultrasónico
    "ADS1115": 0x48,        # Conversor ADC para sensor MQ-2
    "SCD30": 0x61,          # Sensor CO2, temperatura, humedad
    "MPU6050": 0x68         # Sensor inercial (acelerómetro/giroscopio)
}

# ========================
# CONFIGURACIÓN DE ALERTAS
# ========================
ALERT_CONFIG = {
    "gas_alert_enabled": True,
    "gas_alert_repeat_interval": 10,  # segundos entre alertas repetidas
    "obstacle_alert_enabled": True,
    "obstacle_alert_distance": 10,  # cm
    "system_alerts_enabled": True
}

# ========================
# REFERENCIAS DE NIVELES DE HUMO
# ========================
# Valores de referencia para interpretar lecturas de humo en PPM
SMOKE_REFERENCE_VALUES = {
    "aire_limpio": "0-100 PPM",
    "oficina_normal": "50-150 PPM",
    "cocina_con_tostadas": "300-600 PPM",
    "habitacion_con_fumador": "400-800 PPM",
    "incendio_electrico_inicial": "800-1500 PPM",
    "incendio_materiales": "2000+ PPM",
    "rango_minimo_deteccion": "100 PPM",
    "rango_maximo_medicion": "10000 PPM",
    "rango_optimo": "200-5000 PPM"
}