import csv
import os
import time
from datetime import datetime

import cv2 as cv
from pyModbusTCP.client import ModbusClient

# Ajustes iniciales
ip_robot = "192.168.20.128"
tiempo_entre_captura = 0.05
# Lista de angulos en los que se toma foto
lista_angulos = list(range(0, 60))


# Función para convertir valores sin signo a valores con signo
def convertir_signo(valor):
    if valor > 32767:
        return valor - 65536
    return valor


# Ajuste del cliente Modbus
client = ModbusClient(
    host=ip_robot, port=502, unit_id=255, auto_open=True, auto_close=True
)

menu = """--------------------
Ingresar
 d para posición de descanso
 i para posición de inicio
 c para capturar
 s para detener el programa: """

print("Iniciando...")
estado_actual = "descanso"
try:
    while True:
        time.sleep(4)
        accion = input(menu).strip().lower()

        if accion == "d":
            client.write_single_register(133, 1)
            estado_actual = "descanso"
            print("Posición de descanso")

        elif accion == "i":
            client.write_single_register(132, 1)
            estado_actual = "inicio"
            print("Posición de inicio")

        elif accion == "s":
            client.write_single_register(133, 1)
            print("Programa detenido")
            estado_actual = "descanso"
            break

        elif accion == "c":
            if estado_actual == "descanso":
                print(
                    "Necesita estar en la posición de inicio para iniciar a capturar."
                )
                continue

            cap = cv.VideoCapture(0)

            # Crea carpeta base
            base_path = "capturas"
            os.makedirs(base_path, exist_ok=True)

            # Encontrar el siguiente ID de la carpeta
            carpetas_existentes = [
                d
                for d in os.listdir(base_path)
                if os.path.isdir(os.path.join(base_path, d))
            ]
            ids_encontrados = [
                int(n.split("_")[0])
                for n in carpetas_existentes
                if n.split("_")[0].isdigit()
            ]

            siguiente_id = max(ids_encontrados) + 1 if ids_encontrados else 0
            ts_actual = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

            carpeta_fotos = os.path.join(base_path, f"{siguiente_id:05d}_{ts_actual}")
            os.makedirs(carpeta_fotos, exist_ok=True)

            nombre_archivo = os.path.join(carpeta_fotos, f"movimientos_{ts_actual}.csv")

            ultimo_angulo_foto = None
            contador_fotos_angulo = 0
            max_capturas_por_dato = 5
            angulo_anterior = 0
            direccion_actual = "ida"
            fase = 1

            # REORGANIZACIÓN: Variable de control para que el robot arranque una sola vez
            robot_arrancado = False

            # El bloque with cierra el archivo automáticamente al salir
            with open(nombre_archivo, mode="w", newline="") as file:
                writer = csv.writer(file, delimiter=",")
                writer.writerow(
                    ["Fecha", "Hora", "Ángulo", "Dirección", "Subtrayectoria"]
                )

                ultimo_tiempo_modbus = time.time()

                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret:
                        break

                    # REORGANIZACIÓN: El registro 128 se escribe una única vez aquí dentro
                    if not robot_arrancado:
                        client.write_single_register(128, 1)
                        robot_arrancado = True

                    # Descomenta esto si quieres ver la ventana y usar 'q' para salir
                    # cv.imshow('Mostrando imagen', frame)
                    # if cv.waitKey(1) == ord("q"):
                    #     break

                    tiempo_actual = time.time()
                    if tiempo_actual - ultimo_tiempo_modbus >= tiempo_entre_captura:
                        reg_angulo = client.read_holding_registers(129, 1)
                        reg_activar = client.read_holding_registers(128, 1)

                        if reg_angulo and reg_activar:
                            angulo_val = convertir_signo(reg_angulo[0])
                            activar = reg_activar[0]

                            # Lógica de dirección
                            nueva_direccion = direccion_actual
                            if angulo_val > angulo_anterior:
                                nueva_direccion = "ida"
                            elif angulo_val < angulo_anterior:
                                nueva_direccion = "regreso"

                            if nueva_direccion != direccion_actual:
                                fase += 1
                                direccion_actual = nueva_direccion
                                ultimo_angulo_foto = None
                                contador_fotos_angulo = 0
                                print(
                                    f"Cambio detectado: Subtrayectoria {fase:02d} ({direccion_actual})"
                                )

                            # Guardar en CSV
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

                            # Lógica de captura
                            clave_foto = (angulo_val, fase)
                            if angulo_val in lista_angulos:
                                tomar_foto = False
                                if clave_foto != ultimo_angulo_foto:
                                    ultimo_angulo_foto = clave_foto
                                    contador_fotos_angulo = 1
                                    tomar_foto = True
                                elif contador_fotos_angulo < max_capturas_por_dato:
                                    contador_fotos_angulo += 1
                                    tomar_foto = True

                                if tomar_foto:
                                    nombre_foto = os.path.join(
                                        carpeta_fotos,
                                        f"subtrayectoria{fase:02d}_ang{angulo_val:02d}_cap{contador_fotos_angulo:02d}_{ahora.strftime('%H-%M-%S')}.png",
                                    )
                                    cv.imwrite(nombre_foto, frame)
                                    print(
                                        f"FOTO: Subtrayectoria {fase:02d} | Ang {angulo_val:02d} |"
                                    )

                            elif angulo_val == 0:
                                ultimo_angulo_foto = None
                                contador_fotos_angulo = 0

                            angulo_anterior = angulo_val
                            ultimo_tiempo_modbus = tiempo_actual

                            if activar == 0:
                                estado_actual = "descanso"
                                print("Señal de detención recibida por Modbus.")
                                break

            # Liberación de recursos
            cap.release()
            cv.destroyAllWindows()
            print("Captura finalizada.")
            time.sleep(1)

        else:
            print("Ingrese una letra definida.")

except KeyboardInterrupt:
    print("\nPrograma detenido")
finally:
    cv.destroyAllWindows()
