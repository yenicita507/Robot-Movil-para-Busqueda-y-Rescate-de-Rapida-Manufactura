"""
ESP32 Robot Controller + Multi-Sensor System + MQ-2 - MicroPython
Sistema Unificado: Robot + MPU6050 + Ultrasónico + SCD30 + MQ-2 (Gas/Humo)
Versión completa integrada con medición de humo en PPM
"""

import network
import time
import json
import gc
import struct
import math
from machine import I2C, Pin, PWM, reset, unique_id
from umqtt.simple import MQTTClient
import ubinascii

# Importar configuración
try:
    from config import *
    print("Config cargada correctamente")
except ImportError as e:
    print(f" Error importando config.py: {e}")
    SAFE_START = True

# Importar librería MPU6050
try:
    from MPU6050 import MPU6050
    MPU6050_AVAILABLE = True
    print(" Librería MPU6050 cargada")
except ImportError:
    MPU6050_AVAILABLE = False
    print(" MPU6050 no disponible")

# ========================
# CLASE ADS1115 (Para MQ-2)
# ========================
class ADS1115:
    def __init__(self, i2c, addr=None, gain=None):
        self.i2c = i2c
        self.addr = addr or ADS1115_ADDR
        self.gain = gain or MQ2_GAIN
    
    def read_adc(self, channel):
        if channel > 3:
            return 0
        
        # Configurar conversión single-shot
        config = (0x8000 | 0x0100 | self.gain | 0x0080 | 
                 ADS1115_MUX_CONFIG[channel] | 0x0003)
        
        # Escribir configuración
        self.i2c.writeto(self.addr, bytes([ADS1115_REG_CONFIG, config >> 8, config & 0xFF]))
        
        # Esperar conversión
        time.sleep(0.01)
        
        # Leer resultado
        self.i2c.writeto(self.addr, bytes([ADS1115_REG_CONVERSION]))
        data = self.i2c.readfrom(self.addr, 2)
        result = (data[0] << 8) | data[1]
        
        return result if result < 32768 else result - 65536

# ========================
# CLASE SENSOR MQ-2
# ========================
class MQ2Sensor:
    def __init__(self, i2c_bus):
        print(" Inicializando sensor MQ-2...")
        self.i2c = i2c_bus
        self.ads = None
        self.available = False
        self.last_reading = 0
        self.last_voltage = 0.0
        self.last_ppm = 0.0
        self.alert_status = "normal"
        self.read_errors = 0
        self.r0_calibrated = False
        self.r0_value = 1.0  # Valor por defecto, se calibrará
        
        try:
            devices = self.i2c.scan()
            
            # Verificar presencia del ADS1115
            if ADS1115_ADDR in devices:
                print(f" ADS1115 detectado en {hex(ADS1115_ADDR)}")
                self.ads = ADS1115(self.i2c)
                self.available = True
                # Calibrar R0 al iniciar
                self._calibrate_r0()
                print(" Sensor MQ-2 inicializado correctamente")
            else:
                print(f" ADS1115 NO detectado en {hex(ADS1115_ADDR)}")
                self.available = False
                
        except Exception as e:
            print(f" Error inicializando sensor MQ-2: {e}")
            self.available = False
    
    def _calibrate_r0(self):
        """Calibrar el valor R0 en aire limpio"""
        print(" Calibrando sensor MQ-2 en aire limpio...")
        try:
            samples = []
            for i in range(50):  # Tomar 50 muestras
                adc_value = self.ads.read_adc(MQ2_CHANNEL)
                if adc_value > 0:
                    voltage = (adc_value * SAFETY_CONFIG["voltage_reference"]) / 32767.0 # Calcular RS
                    rs = (MQ2_VOLTAGE_SUPPLY - voltage) / voltage
                    samples.append(rs)
                time.sleep(0.1)
            
            if samples:
                avg_rs = sum(samples) / len(samples)
                self.r0_value = avg_rs / MQ2_RO_CLEAN_AIR
                self.r0_calibrated = True
                print(f" Calibración MQ-2 completada - R0: {self.r0_value:.2f} kΩ")
            else:
                print(" Error en calibración: no se pudieron tomar muestras")
                
        except Exception as e:
            print(f" Error en calibración MQ-2: {e}")
    
    def _calculate_ppm(self, voltage):
        """Calcular PPM de humo basado en el voltaje"""
        try:
            # Calcular resistencia del sensor (RS)
            rs = (MQ2_VOLTAGE_SUPPLY - voltage) / voltage
            
            # Calcular relación RS/R0
            rs_r0_ratio = rs / self.r0_value
            
            # Aplicar fórmula logarítmica para calcular PPM de humo
            # log(y) = m * log(x) + b  =>  log(ppm) = m * log(rs_r0_ratio) + b
            # ppm = 10 ^ [(log(rs_r0_ratio) - b) / m]
            
            if rs_r0_ratio <= 0:
                return 0.0
                
            log_rs_r0 = math.log10(rs_r0_ratio)
            log_ppm = (log_rs_r0 - MQ2_SMOKE_B) / MQ2_SMOKE_M
            ppm = math.pow(10, log_ppm)
            
            return max(0.0, ppm)
            
        except Exception as e:
            print(f" Error calculando PPM: {e}")
            return 0.0
    
    def read_sensor(self):
        """Leer valor del sensor MQ-2 y convertir a PPM de humo"""
        if not self.available or not self.r0_calibrated:
            return None
            
        try:
            adc_value = self.ads.read_adc(MQ2_CHANNEL)
            voltage = (adc_value * SAFETY_CONFIG["voltage_reference"]) / 32767.0
            
            # Calcular PPM de humo
            ppm = self._calculate_ppm(voltage)
            
            self.last_reading = adc_value
            self.last_voltage = voltage
            self.last_ppm = ppm
            
            # Determinar estado de alerta basado en PPM
            if ppm >= SMOKE_THRESHOLDS["critico"]:
                self.alert_status = "critico"
            elif ppm >= SMOKE_THRESHOLDS["peligro"]:
                self.alert_status = "peligro"
            elif ppm >= SMOKE_THRESHOLDS["advertencia"]:
                self.alert_status = "advertencia"
            else:
                self.alert_status = "normal"
            
            if DEBUG_ENABLED:
                print(f" MQ-2 | ADC: {adc_value} | V: {voltage:.3f}V | PPM: {ppm:.2f} | Estado: {self.alert_status}")
            
            self.read_errors = 0
            
            return {
                "adc_value": adc_value,
                "voltage": round(voltage, 3),
                "ppm": round(ppm, 2),
                "alert_status": self.alert_status,
                "r0_calibrated": self.r0_calibrated,
                "r0_value": round(self.r0_value, 2),
                "rs_ro_ratio": round((voltage > 0) and ((MQ2_VOLTAGE_SUPPLY - voltage) / voltage / self.r0_value) or 0, 3),
                "timestamp": time.time()
            }
            
        except Exception as e:
            self.read_errors += 1
            print(f" Error leyendo sensor MQ-2: {e}")
            if self.read_errors >= 5:
                self.available = False
            return None

# ========================
# CLASE SCD30
# ========================
class SCD30:
    CMD_CONTINUOUS_MEASUREMENT = 0x0010
    CMD_SET_MEASUREMENT_INTERVAL = 0x4600
    CMD_GET_DATA_READY = 0x0202
    CMD_READ_MEASUREMENT = 0x0300
    CMD_SOFT_RESET = 0xD304
    
    def __init__(self, i2c, address=None):
        self.i2c = i2c
        self.address = address or 0x61
        self.CO2 = 0
        self.temperature = 0
        self.relative_humidity = 0
        
    def _crc8(self, data):
        crc = 0xFF
        polynomial = 0x31
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = (crc << 1) ^ polynomial
                else:
                    crc <<= 1
                crc &= 0xFF
        return crc
    
    def _send_command(self, command, argument=None):
        if argument is None:
            cmd_bytes = bytearray([(command >> 8) & 0xFF, command & 0xFF])
            return self.i2c.writeto(self.address, cmd_bytes)
        else:
            cmd_bytes = bytearray([
                (command >> 8) & 0xFF, command & 0xFF,
                (argument >> 8) & 0xFF, argument & 0xFF
            ])
            crc = self._crc8(cmd_bytes[2:4])
            cmd_bytes.append(crc)
            return self.i2c.writeto(self.address, cmd_bytes)
    
    def _read_register(self, command, length=2):
        cmd_bytes = bytearray([(command >> 8) & 0xFF, command & 0xFF])
        self.i2c.writeto(self.address, cmd_bytes)
        time.sleep_ms(4)
        data = self.i2c.readfrom(self.address, length + (length // 2))
        return data
    
    def begin(self):
        try:
            self._send_command(self.CMD_SOFT_RESET)
            time.sleep(0.1)
            self._send_command(self.CMD_CONTINUOUS_MEASUREMENT, 0)
            self._send_command(self.CMD_SET_MEASUREMENT_INTERVAL, 2)
            return True
        except Exception as e:
            print(f"Error inicializando SCD30: {e}")
            return False
    
    def data_ready(self):
        try:
            data = self._read_register(self.CMD_GET_DATA_READY, 2)
            if len(data) >= 2:
                return (data[0] << 8 | data[1]) == 1
            return False
        except:
            return False
    
    def read(self):
        try:
            self._send_command(self.CMD_READ_MEASUREMENT)
            time.sleep_ms(4)
            data = self.i2c.readfrom(self.address, 18)
            
            for i in range(0, 18, 3):
                if self._crc8(data[i:i+2]) != data[i+2]:
                    return False
            
            co2_bytes = bytes([data[0], data[1], data[3], data[4]])
            temp_bytes = bytes([data[6], data[7], data[9], data[10]])
            hum_bytes = bytes([data[12], data[13], data[15], data[16]])
            
            self.CO2 = struct.unpack('>f', co2_bytes)[0]
            self.temperature = struct.unpack('>f', temp_bytes)[0]
            self.relative_humidity = struct.unpack('>f', hum_bytes)[0]
            return True
        except Exception as e:
            print(f"Error leyendo SCD30: {e}")
            return False

# ========================
# CLASE SENSOR ULTRASÓNICO
# ========================
class UltrasonicSensor:
    def __init__(self, i2c_bus, address=None, trig_bit=2, echo_bit=1):
        self.i2c = i2c_bus
        self.address = address or 0x23
        self.trig_bit = trig_bit
        self.echo_bit = echo_bit
        self.pcf_state = 0xFF
        self.last_measure = 0
        self.sound_speed = 0.0343
        self.measure_interval = 1000
        
    def write_pcf(self, data):
        try:
            self.i2c.writeto(self.address, bytes([data]))
            time.sleep_us(10)
            return True
        except:
            return False
    
    def read_pcf(self):
        try:
            data = self.i2c.readfrom(self.address, 1)
            return data[0]
        except:
            return 0xFF
    
    def measure_distance(self):
        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, self.last_measure) < self.measure_interval:
            return None
        
        self.pcf_state &= ~(1 << self.trig_bit)
        if not self.write_pcf(self.pcf_state):
            return None
        time.sleep_us(4)
        
        self.pcf_state |= (1 << self.trig_bit)
        if not self.write_pcf(self.pcf_state):
            return None
        time.sleep_us(10)
        
        self.pcf_state &= ~(1 << self.trig_bit)
        if not self.write_pcf(self.pcf_state):
            return None

        timeout = time.ticks_us() + 5000
        while not (self.read_pcf() & (1 << self.echo_bit)):
            if time.ticks_us() > timeout:
                self.last_measure = time.ticks_ms()
                return None

        start = time.ticks_us()
        timeout = start + 30000
        
        while True:
            if not (self.read_pcf() & (1 << self.echo_bit)):
                break
            if time.ticks_us() > timeout:
                self.last_measure = time.ticks_ms()
                return None

        duration = time.ticks_diff(time.ticks_us(), start)
        distance = max(0, duration * self.sound_speed / 2)
        self.last_measure = time.ticks_ms()
        return distance if distance >= 1 else 0

# ========================
# CLASE MPU6050 MANAGER
# ========================
class MPU6050Manager:
    def __init__(self, i2c_bus):
        print(" Inicializando MPU6050...")
        self.i2c = i2c_bus
        self.mpu = None
        self.read_errors = 0
        self.available = False
        
        try:
            if MPU6050_AVAILABLE:
                devices = self.i2c.scan()
                if 0x68 in devices:
                    self.mpu = MPU6050(bus=self.i2c)
                    self.available = True
                    print(" MPU6050 inicializado")
                else:
                    print(" MPU6050 no detectado")
            else:
                print(" Librería MPU6050 no disponible")
        except Exception as e:
            print(f" Error MPU6050: {e}")
            self.available = False

    def read_sensor_data(self):
        if not self.available:
            return None
            
        try:
            accel = self.mpu.read_accel_data()
            gyro = self.mpu.read_gyro_data()
            temp = self.mpu.read_temperature()
            angle = self.mpu.read_angle()
            abs_accel = self.mpu.read_accel_abs(g=False)
            
            if DEBUG_ENABLED:
                print(f"MPU - Accel: X:{accel['x']:.2f} Y:{accel['y']:.2f} Z:{accel['z']:.2f}")
            
            self.read_errors = 0
            return {
                "accelerometer": {"x": accel["x"], "y": accel["y"], "z": accel["z"]},
                "gyroscope": {"x": gyro["x"], "y": gyro["y"], "z": gyro["z"]},
                "temperature": {"value": temp, "unit": "C"},
                "orientation": {"roll": angle["x"], "pitch": angle["y"]},
                "absolute_acceleration": abs_accel
            }
            
        except Exception as e:
            self.read_errors += 1
            print(f" Error MPU6050: {e}")
            if self.read_errors >= 5:
                self.available = False
            return None

# ========================
# CLASE SCD30 MANAGER
# ========================
class SCD30Manager:
    def __init__(self, i2c_bus):
        print(" Inicializando SCD30...")
        self.i2c = i2c_bus
        self.sensor = None
        self.available = False
        
        try:
            devices = self.i2c.scan()
            if SCD30_ADDRESS in devices:
                self.sensor = SCD30(self.i2c, SCD30_ADDRESS)
                if self.sensor.begin():
                    self.available = True
                    print(" SCD30 inicializado")
                else:
                    print(" Error inicializando SCD30")
            else:
                print(" SCD30 no detectado")
        except Exception as e:
            print(f" Error SCD30: {e}")
            self.available = False

    def read_sensor_data(self):
        if not self.available:
            return None
            
        try:
            if not self.sensor.data_ready():
                return None
                
            if self.sensor.read():
                temp = self.sensor.temperature + SENSOR_CALIBRATION["temperature_offset"]
                humidity = (self.sensor.relative_humidity * SENSOR_CALIBRATION["humidity_slope"] + 
                           SENSOR_CALIBRATION["humidity_intercept"])
                
                if DEBUG_ENABLED:
                    print(f" SCD30 - CO2:{self.sensor.CO2:.0f}ppm Temp:{temp:.1f}C Hum:{humidity:.1f}%")
                
                return {
                    "co2": round(self.sensor.CO2, 1),
                    "temperature": round(temp, 2),
                    "humidity": round(humidity, 2)
                }
            return None
        except Exception as e:
            print(f" Error SCD30: {e}")
            return None

# ========================
# CLASE WIFI MANAGER
# ========================
class WiFiManager:
    def __init__(self):
        self.wlan = network.WLAN(network.STA_IF)
        self.connection_attempts = 0
        
    def connect(self, ssid, password, timeout=30):
        print(f" Conectando WiFi: {ssid}")
        self.wlan.active(True)
        
        if self.wlan.isconnected():
            print(" WiFi ya conectado")
            return True
            
        self.wlan.connect(ssid, password)
        self.connection_attempts += 1
        
        start_time = time.time()
        while not self.wlan.isconnected() and (time.time() - start_time) < timeout:
            time.sleep(0.5)
            print(".", end="")
            
        if self.wlan.isconnected():
            print(f"\n WiFi conectado: {self.wlan.ifconfig()[0]}")
            return True
        else:
            print("\n Error WiFi")
            return False
    
    def get_ip(self):
        return self.wlan.ifconfig()[0] if self.wlan.isconnected() else None
    
    def is_connected(self):
        return self.wlan.isconnected()

# ========================
# CLASE MOTOR CONTROLLER
# ========================
class MotorController:
    def __init__(self, i2c_bus):
        print(" Inicializando motores...")
        self.current_movement = "stop"
        self.last_movement_time = time.time()
        self.i2c = i2c_bus
        self.emergency_stop_active = False
        
        devices = self.i2c.scan()
        for pcf_num, addr in PCF8574_ADDRESSES.items():
            if addr in devices:
                print(f" PCF8574 #{pcf_num} en {hex(addr)}")
            else:
                raise RuntimeError(f" PCF8574 #{pcf_num} no encontrado")

        self.motors = {}
        for motor_num, pin in MOTOR_PINS.items():
            self.motors[motor_num] = PWM(Pin(pin), freq=PWM_FREQUENCY)
            self.motors[motor_num].duty(0)

        self.stop_all_motors()
        print(" Motores inicializados")

    def set_motor_speed_direction(self, motor_num, pwm_value, direction):
        if motor_num not in [1, 2, 3, 4]:
            raise ValueError(f"Motor inválido: {motor_num}")
        if not 0 <= pwm_value <= 1023:
            raise ValueError(f"PWM fuera de rango: {pwm_value}")
        if direction not in ["horario", "antihorario"]:
            raise ValueError(f"Dirección inválida: {direction}")

        self.motors[motor_num].duty(pwm_value)
        pcf_num = 1 if motor_num <= 2 else 2
        addr = PCF8574_ADDRESSES[pcf_num]
        control_key = f"m{motor_num}_{direction}"
        bits = PCF_CONTROL_BITS.get(control_key)
        
        if bits is None:
            raise ValueError(f"Comando no encontrado: {control_key}")
        
        self.i2c.writeto(addr, bytes([bits]))

    def execute_movement(self, movement_name):
        if self.emergency_stop_active:
            print(" Parada de emergencia activa - movimiento bloqueado")
            return False
            
        if movement_name not in ROBOT_MOVEMENTS:
            print(f" Movimiento no definido: {movement_name}")
            return False
            
        try:
            current_time = time.time()
            if SAFETY_CONFIG["auto_stop_timeout"] > 0 and \
               (current_time - self.last_movement_time) > SAFETY_CONFIG["auto_stop_timeout"]:
                print("Auto-stop por inactividad")
                self.stop_all_motors()
            
            print(f" Movimiento: {movement_name}")
            movement = ROBOT_MOVEMENTS[movement_name]
            
            if movement_name != self.current_movement:
                self.stop_all_motors()
                time.sleep(0.1)
            
            for motor_num in range(1, 5):
                motor_key = f"M{motor_num}"
                if motor_key in movement:
                    config = movement[motor_key]
                    self.set_motor_speed_direction(motor_num, config["pwm"], config["direction"])
            
            self.current_movement = movement_name
            self.last_movement_time = current_time
            return True
            
        except Exception as e:
            print(f" Error movimiento: {e}")
            self.stop_all_motors()
            return False

    def emergency_stop(self, reason="Humo crítico detectado"):
        """Parada de emergencia del robot"""
        print(f" PARADA DE EMERGENCIA: {reason}")
        self.emergency_stop_active = True
        self.stop_all_motors()

    def reset_emergency_stop(self):
        """Resetear parada de emergencia"""
        print(" Parada de emergencia reseteada")
        self.emergency_stop_active = False

    def stop_all_motors(self):
        try:
            for motor_num in [1, 2, 3, 4]:
                self.motors[motor_num].duty(0)
            for addr in PCF8574_ADDRESSES.values():
                self.i2c.writeto(addr, bytes([0xFF]))
            self.current_movement = "stop"
            self.last_movement_time = time.time()
        except Exception as e:
            print(f" Error crítico deteniendo motores: {e}")
            raise

# ========================
# CLASE MQTT CLIENT UNIFICADO
# ========================
class UnifiedMQTTClient:
    def __init__(self, motor_controller, wifi_manager, ultrasonic, mpu_manager, scd30_manager, mq2_sensor):
        self.motor_controller = motor_controller
        self.wifi_manager = wifi_manager
        self.ultrasonic_sensor = ultrasonic
        self.mpu6050_manager = mpu_manager
        self.scd30_manager = scd30_manager
        self.mq2_sensor = mq2_sensor
        self.client = None
        self.client_id = self._generate_client_id()
        self.connected = False
        self.last_heartbeat = 0
        self.last_command_time = 0
        self.last_ultrasonic_read = 0
        self.last_mpu_read = 0
        self.last_scd30_read = 0
        self.last_mq2_read = 0
        self.command_timeout = 0.5

    def _generate_client_id(self):
        machine_id = ubinascii.hexlify(unique_id()).decode()
        return f"{DEVICE_NAME}_{machine_id[-6:]}"

    def connect(self):
        try:
            print(f" Conectando MQTT: {MQTT_BROKER}:{MQTT_PORT}")
            self.client = MQTTClient(
                self.client_id, MQTT_BROKER, port=MQTT_PORT,
                user=MQTT_USER, password=MQTT_PASSWORD, keepalive=MQTT_KEEPALIVE
            )
            self.client.set_callback(self._on_message)
            self.client.connect()
            self.client.subscribe(TOPIC_COMMAND)
            self.connected = True
            print(f" MQTT conectado: {self.client_id}")
            self._publish_status("connected", f"{DEVICE_NAME} conectado")
            return True
        except Exception as e:
            print(f" Error MQTT: {e}")
            self.connected = False
            return False

    def _on_message(self, topic, msg):
        try:
            topic_str = topic.decode('utf-8')
            msg_str = msg.decode('utf-8')
            
            if topic_str == TOPIC_COMMAND:
                current_time = time.time()
                if current_time - self.last_command_time > self.command_timeout:
                    self.last_command_time = current_time
                    self._process_command(msg_str)
        except Exception as e:
            print(f" Error mensaje: {e}")

    def _process_command(self, msg_str):
        try:
            data = json.loads(msg_str)
            command = data.get("command", "").lower().strip()
            device_id = data.get("device_id", "").strip()
            
            if device_id and device_id not in [self.client_id, "all"]:
                return
                
            command = COMMAND_MAPPING.get(command, command)
            
            # Verificar obstáculos para movimiento adelante
            if command == "adelante" and SAFETY_CONFIG["emergency_stop_enabled"]:
                distance = self.ultrasonic_sensor.measure_distance()
                if distance is not None and distance < SAFETY_CONFIG["obstacle_distance"]:
                    print(f" Obstáculo: {distance:.2f}cm")
                    self._publish_status("blocked", f"Obstáculo a {distance:.2f}cm")
                    return
            
            if command in ROBOT_MOVEMENTS:
                if self.motor_controller.execute_movement(command):
                    self._publish_status("moving", f"Ejecutando: {command}")
                else:
                    self._publish_status("error", f"Error: {command}")
                
        except json.JSONDecodeError:
            print(" JSON inválido")
        except Exception as e:
            print(f" Error comando: {e}")

    def _publish_status(self, status, message):
        try:
            if not self.connected:
                return
            status_data = {
                "device_id": self.client_id,
                "device_name": DEVICE_NAME,
                "location": LOCATION,
                "status": status,
                "message": message,
                "current_movement": self.motor_controller.current_movement,
                "emergency_stop": self.motor_controller.emergency_stop_active,
                "timestamp": time.time(),
                "ip": self.wifi_manager.get_ip()
            }
            self.client.publish(TOPIC_STATUS, json.dumps(status_data))
        except Exception as e:
            print(f" Error publicando estado: {e}")
            self.connected = False

    def _publish_ultrasonic_data(self, distance):
        try:
            if not self.connected:
                return
            sensor_data = {
                "device_id": self.client_id,
                "distance_cm": distance,
                "timestamp": time.time()
            }
            self.client.publish(TOPIC_ULTRASONIC, json.dumps(sensor_data))
        except Exception as e:
            print(f" Error ultrasónico: {e}")

    def _publish_mpu_data(self, sensor_data):
        try:
            if not self.connected or sensor_data is None:
                return
            mqtt_data = {
                "device_id": self.client_id,
                "device_name": DEVICE_NAME,
                "location": LOCATION
            }
            mqtt_data.update(sensor_data)
            mqtt_data["timestamp"] = time.time()
            self.client.publish(TOPIC_MPU_DATA, json.dumps(mqtt_data))
        except Exception as e:
            print(f" Error MPU: {e}")

    def _publish_scd30_data(self, sensor_data):
        try:
            if not self.connected or sensor_data is None:
                return
            mqtt_data = {
                "device_id": self.client_id,
                "device_name": DEVICE_NAME,
                "location": LOCATION
            }
            mqtt_data.update(sensor_data)
            mqtt_data["timestamp"] = time.time()
            self.client.publish(TOPIC_SCD30_DATA, json.dumps(mqtt_data))
        except Exception as e:
            print(f" Error SCD30: {e}")

    def _publish_mq2_data(self, sensor_data):
        """Publicar datos del sensor MQ-2 con valores de humo en PPM"""
        try:
            if not self.connected or sensor_data is None:
                return
                
            # Publicar datos del sensor
            data_payload = {
                "device_id": self.client_id,
                "device_name": DEVICE_NAME,
                "location": LOCATION,
                "sensor_data": sensor_data,
                "ip": self.wifi_manager.get_ip(),
                "timestamp": time.time()
            }
            self.client.publish(TOPIC_MQ2_DATA, json.dumps(data_payload))
            
            # Publicar alerta si es necesario
            if sensor_data["alert_status"] != "normal":
                alert_payload = {
                    "device_id": self.client_id,
                    "device_name": DEVICE_NAME,
                    "location": LOCATION,
                    "alert_level": sensor_data["alert_status"],
                    "ppm_value": sensor_data["ppm"],
                    "adc_value": sensor_data["adc_value"],
                    "voltage": sensor_data["voltage"],
                    "r0_value": sensor_data["r0_value"],
                    "timestamp": time.time(),
                    "message": f"Alerta de humo: {sensor_data['alert_status']} - {sensor_data['ppm']} PPM"
                }
                self.client.publish(TOPIC_MQ2_ALERT, json.dumps(alert_payload))
                print(f" Alerta MQ-2 publicada: {sensor_data['alert_status']} - {sensor_data['ppm']} PPM")
                
                # Activar parada de emergencia si está configurado
                if (SAFETY_CONFIG.get("gas_emergency_stop", False) and 
                    sensor_data["alert_status"] in ["peligro", "critico"]):
                    self.motor_controller.emergency_stop(
                        f"Humo {sensor_data['alert_status']} detectado: {sensor_data['ppm']} PPM"
                    )
            else:
                # Resetear parada de emergencia si el nivel vuelve a normal
                if self.motor_controller.emergency_stop_active:
                    self.motor_controller.reset_emergency_stop()
                    self._publish_status("recovered", "Nivel de humo normalizado")
                    
        except Exception as e:
            print(f" Error publicando MQ-2: {e}")

    def send_heartbeat(self):
        current_time = time.time()
        if current_time - self.last_heartbeat > HEARTBEAT_INTERVAL:
            try:
                if not self.connected:
                    return
                heartbeat_data = {
                    "device_id": self.client_id,
                    "device_name": DEVICE_NAME,
                    "status": "alive",
                    "free_memory": gc.mem_free(),
                    "mpu6050_available": self.mpu6050_manager.available,
                    "scd30_available": self.scd30_manager.available,
                    "mq2_available": self.mq2_sensor.available,
                    "mq2_r0_calibrated": self.mq2_sensor.r0_calibrated,
                    "timestamp": current_time
                }
                self.client.publish(TOPIC_HEARTBEAT, json.dumps(heartbeat_data))
                self.last_heartbeat = current_time
            except Exception as e:
                print(f" Error heartbeat: {e}")
                self.connected = False

    def check_sensors(self):
        current_time = time.time()
        
        # Leer sensor ultrasónico
        if current_time - self.last_ultrasonic_read > 5:
            distance = self.ultrasonic_sensor.measure_distance()
            if distance is not None:
                self._publish_ultrasonic_data(distance)
            self.last_ultrasonic_read = current_time
        
        # Leer MPU6050
        if self.mpu6050_manager.available and current_time - self.last_mpu_read > MPU_READ_INTERVAL:
            mpu_data = self.mpu6050_manager.read_sensor_data()
            if mpu_data:
                self._publish_mpu_data(mpu_data)
            self.last_mpu_read = current_time
        
        # Leer SCD30
        if self.scd30_manager.available and current_time - self.last_scd30_read > SCD30_READ_INTERVAL:
            scd30_data = self.scd30_manager.read_sensor_data()
            if scd30_data:
                self._publish_scd30_data(scd30_data)
            self.last_scd30_read = current_time
        
        # Leer MQ-2 (Gas/Humo)
        if self.mq2_sensor.available and current_time - self.last_mq2_read > MQ2_READ_INTERVAL:
            mq2_data = self.mq2_sensor.read_sensor()
            if mq2_data:
                self._publish_mq2_data(mq2_data)
            self.last_mq2_read = current_time

    def check_messages(self):
        try:
            if self.connected and self.client:
                self.client.check_msg()
                return True
            return False
        except Exception as e:
            print(f" Error check_messages: {e}")
            self.connected = False
            return False

# ========================
# CLASE SISTEMA UNIFICADO ESP32
# ========================
class ESP32UnifiedSystem:
    def __init__(self):
        print(f" Iniciando {DEVICE_NAME}")
        print(f" Ubicación: {LOCATION}")
        
        try:
            self.i2c = I2C(0, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN), freq=I2C_FREQUENCY)
            devices = self.i2c.scan()
            print(f" I2C: {[hex(x) for x in devices]}")
        except Exception as e:
            print(f" Error I2C: {e}")
            raise
        
        self.wifi = WiFiManager()
        self.motor_controller = MotorController(self.i2c)
        self.ultrasonic_sensor = UltrasonicSensor(self.i2c)
        self.mpu6050_manager = MPU6050Manager(self.i2c)
        self.scd30_manager = SCD30Manager(self.i2c)
        self.mq2_sensor = MQ2Sensor(self.i2c)
        self.mqtt_client = None
        self.running = True
        
    def start(self):
        if SAFE_START:
            print(" Modo seguro activado")
            return
            
        print(" Iniciando sistema...")
        
        wifi_connected = False
        for attempt in range(MAX_RECONNECT_ATTEMPTS):
            if self.wifi.connect(WIFI_SSID, WIFI_PASSWORD):
                wifi_connected = True
                break
            time.sleep(RECONNECT_DELAY)
        
        if not wifi_connected:
            print(" WiFi falló. Reiniciando...")
            time.sleep(5)
            reset()
            
        self.mqtt_client = UnifiedMQTTClient(
            self.motor_controller, self.wifi, self.ultrasonic_sensor,
            self.mpu6050_manager, self.scd30_manager, self.mq2_sensor
        )
        
        mqtt_connected = False
        for attempt in range(MAX_RECONNECT_ATTEMPTS):
            if self.mqtt_client.connect():
                mqtt_connected = True
                break
            time.sleep(RECONNECT_DELAY)
        
        if not mqtt_connected:
            print(" MQTT falló. Reiniciando...")
            time.sleep(5)
            reset()
        
        print("=" * 50)
        print(" Sistema listo")
        print(f" MPU6050: {'Sí' if self.mpu6050_manager.available else 'No'}")
        print(f" SCD30: {'Sí' if self.scd30_manager.available else 'No'}")
        print(f" MQ-2: {'Sí' if self.mq2_sensor.available else 'No'}")
        print(f" MQ-2 Calibrado: {'Sí' if self.mq2_sensor.r0_calibrated else 'No'}")
        if self.mq2_sensor.r0_calibrated:
            print(f" MQ-2 R0: {self.mq2_sensor.r0_value:.2f} kΩ")
        print("=" * 50)
        
        self._main_loop()
    
    def _main_loop(self):
        print(" Loop principal iniciado")
        last_status_time = time.time()
        
        while self.running:
            try:
                current_time = time.time()
                
                # Verificar conexión WiFi
                if not self.wifi.is_connected():
                    print(" WiFi caído")
                    if not self.wifi.connect(WIFI_SSID, WIFI_PASSWORD):
                        time.sleep(RECONNECT_DELAY)
                        continue
                
                # Verificar conexión MQTT
                if not self.mqtt_client.check_messages():
                    print(" MQTT caído")
                    if not self.mqtt_client.connect():
                        time.sleep(RECONNECT_DELAY)
                        continue
                
                # Leer todos los sensores
                self.mqtt_client.check_sensors()
                
                # Publicar estado periódico
                if current_time - last_status_time > 10:
                    self.mqtt_client._publish_status("connected", "Sistema operativo")
                    last_status_time = current_time
                
                # Enviar heartbeat
                self.mqtt_client.send_heartbeat()
                
                # Liberar memoria si es necesario
                if gc.mem_free() < 10000:
                    gc.collect()
                    if DEBUG_ENABLED:
                        print(f"🧹 Memoria liberada: {gc.mem_free()} bytes")
                
                time.sleep(0.1)
                
            except KeyboardInterrupt:
                print("\n Interrupción")
                self.stop()
                break
            except Exception as e:
                print(f" Error loop: {e}")
                time.sleep(1)
    
    def stop(self):
        print(" Deteniendo sistema...")
        self.running = False
        self.motor_controller.stop_all_motors()
        if self.mqtt_client:
            self.mqtt_client._publish_status("disconnected", "Desconectado")
            time.sleep(1)
        print(" Sistema detenido")

# ========================
# FUNCIÓN PRINCIPAL
# ========================
def main():
    print("=" * 50)
    print(f" ESP32 Robot Controller + Multi-Sensor + MQ-2")
    print(f" Device: {DEVICE_NAME}")
    print(f" Location: {LOCATION}")
    print(f" MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f" WiFi SSID: {WIFI_SSID}")
    print("=" * 50)
    
    try:
        system = ESP32UnifiedSystem()
        system.start()
    except Exception as e:
        print(f" Error crítico: {e}")
        print(" Reiniciando en 5 segundos...")
        time.sleep(5)
        reset()

if __name__ == "__main__":
    main()