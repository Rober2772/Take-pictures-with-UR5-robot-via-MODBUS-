import csv
import os
import time
from datetime import datetime

import cv2 as cv
import numpy as np
from pyModbusTCP.client import ModbusClient

# Ajustes iniciales, IP a la que se conecta el robot, tiempo entre captura
# y lista de angulos en los que se estaran tomando fotos
ip_robot = "192.168.20.142"
tiempo_entre_captura = 0.05
# lista_angulos = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60]
lista_angulos = list(range(0, 60))


# Función para convertir valores unsigned a signed para ver numeros negativos
def convertir_signo(valor):
    if valor > 32767:
        return valor - 65536
    return valor


# Ajuste del cliente, colocando la ip al cual va direccionado,
# el port y el unit_id generalmente no cambia para MODBUS
client = ModbusClient(
    host=ip_robot, port=502, unit_id=255, auto_open=True, auto_close=True
)

# Se abre el cliente y se actaliza el registro 128 a 1 para activar la
# variable de encendido y activar el movimiento del robot
# client.write_single_register(128, 1)
# print("Registro 128 actualizado a 1")

# Lee continuamente el valor de la entrada
# y espera que se actualice el registro 128 para iniciar
print("Esperando señal de inicio...")
while True:
    time.sleep(2)
    accion = input("d para descansar, i para posición de inicio y c para capturar: ")
    if accion == "d":
        client.write_single_register(133, np.uint16(1))
        print("Posición de descanso")
    elif accion == "i":
        client.write_single_register(132, np.uint16(1))
        print("Posición de inicio")
    elif accion == "c":
        # Se configura la camara que se va a utilizar
        cap = cv.VideoCapture(0)
        client.write_single_register(128, np.uint16(1))

        # Crea una carpeta para guardar las fotos y un archivo para los datos
        base_path = "capturas"
        os.makedirs(base_path, exist_ok=True)

        carpetas_existentes = [
            d
            for d in os.listdir(base_path)
            if os.path.isdir(os.path.join(base_path, d))
        ]
        ids_encontrados = []
        for nombre in carpetas_existentes:
            parte_id = nombre.split("_")[0]
            if parte_id.isdigit():
                ids_encontrados.append(int(parte_id))

        siguiente_id = max(ids_encontrados) + 1 if ids_encontrados else 0
        ts_actual = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        carpeta_fotos = os.path.join(base_path, f"{siguiente_id:03d}_{ts_actual}")
        os.makedirs(carpeta_fotos, exist_ok=True)

        nombre_archivo = os.path.join(carpeta_fotos, f"movimientos_{ts_actual}.csv")

        # Variables de estado para guardar la fase en la que se encuentra
        ultimo_angulo_foto = None
        angulo_anterior = 0
        direccion_actual = "ida"
        fase = 1

        # Configura el archivo con los datos que se va a guardar,
        # el nombre de las columnas y las especificaciones del archivo
        with open(nombre_archivo, mode="w", newline="") as file:
            writer = csv.writer(file, delimiter=",")
            writer.writerow(["Fecha", "Hora", "Ángulo", "Dirección", "Subtrayectoria"])

            # Ajusta el tiempo de captura de datos para que no se interponga
            # con el de captura de fotos y se inicializa la variable posicion en 0
            ultimo_tiempo_modbus = time.time()
            posicion = 0

            # Inicia in ciclo mientras la camara esta abierta y capturando
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                # cv.imshow('Grabando... Presiona q para salir', frame)

                # Control de la frecuencia de registros de datos
                # lectura de los puertos MODBUS
                if time.time() - ultimo_tiempo_modbus >= tiempo_entre_captura:
                    reg_angulo = client.read_holding_registers(129, 1)
                    reg_activar = client.read_holding_registers(128, 1)

                    # Cuando detecta valores en correctos en todos los registros
                    # convierte a enteros con signo los valores obtenidos
                    if reg_angulo and reg_activar:
                        angulo_val = convertir_signo(reg_angulo[0])
                        activar = reg_activar[0]

                        # Lógica de detección de fase
                        # Interpretación si va de ida o de regreso comparando el angulo anterior
                        nueva_direccion = direccion_actual
                        if angulo_val > angulo_anterior:
                            nueva_direccion = "ida"
                        elif angulo_val < angulo_anterior:
                            nueva_direccion = "regreso"

                        # Aumenta el numero de fase cada que cambia de dirección
                        # resetea la variable ultimo_angulo_foto para tomar fotos de regreso
                        if nueva_direccion != direccion_actual:
                            fase += 1  # Incrementa fase: ida (1) -> regreso (2) -> ida (3)...
                            direccion_actual = nueva_direccion
                            ultimo_angulo_foto = None  # Reset para permitir fotos en misma posición pero nueva fase
                            print(
                                f"Cambio detectado: Subtrayectoria {fase} ({direccion_actual})"
                            )

                        # Guarda el archivo de los datos y escribe el nombre con el que se guarda
                        ahora = datetime.now()
                        writer.writerow(
                            [
                                ahora.strftime("%Y-%m-%d"),
                                ahora.strftime("%H:%M:%S"),
                                angulo_val,
                                direccion_actual,
                                fase,
                            ]
                        )
                        file.flush()

                        # Determina si tomar la captura con los angulos asignados,
                        # guarda si ya tomo captura en ese angulo para solo tomar una foto y
                        # guarda la captura con un nombre asignado en la carpeta
                        clave_foto = (angulo_val, fase)
                        if angulo_val in lista_angulos:
                            if clave_foto != ultimo_angulo_foto:
                                nombre_foto = os.path.join(
                                    carpeta_fotos,
                                    f"subtrayectoria{fase}_ang{angulo_val}_{ahora.strftime('%H-%M-%S')}.png",
                                )
                                cv.imwrite(nombre_foto, frame)
                                print(
                                    f"FOTO: Subtrayectoria {fase:>2} | Ang {angulo_val:>2} |"
                                )
                                ultimo_angulo_foto = clave_foto

                        # Si el ultimo angulo guardado es 0 restaura la variable para seguir capturando
                        elif angulo_val == 0:
                            ultimo_angulo_foto = None

                        # Guarda el angulo anterior y la frecuencia de muestreo
                        angulo_anterior = angulo_val
                        ultimo_tiempo_modbus = time.time()

                        # Si se lee un 0 en la variable activar detiene la captura
                        # la variable activar es el mismo puerto que encendido del robot
                        if activar == 0:
                            print("Señal de detención recibida.")
                            break
                        # Orden para detener la grabación con la letra q
                        if cv.waitKey(1) == ord("q"):
                            break

            # Liberación de recursos y cierre del cliente
            cap.release()
            cv.destroyAllWindows()
            time.sleep(3)

    else:
        print("Ingrese una letra definida")
