import csv
import os
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, scrolledtext

import cv2 as cv
from pyModbusTCP.client import ModbusClient


class RobotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Control de Robot y Captura")
        self.root.geometry("900x960")
        self.root.resizable(False, False)
        self.root.configure(bg="antiquewhite1")

        # Configuración inicial
        self.ip_robot = "192.168.20.142"
        self.tiempo_entre_captura = 0.05
        self.lista_angulos = list(range(0, 60))

        # Cliente Modbus
        self.client = ModbusClient(
            host=self.ip_robot, port=502, unit_id=255, auto_open=True, auto_close=True
        )

        # Variables de estado
        self.estado_actual = "descanso"
        self.capturando = False  # Bandera para controlar el hilo de captura

        # Variable para almacenar el nombre del paciente
        self.nombre_paciente_var = tk.StringVar()

        self.crear_interfaz()
        self.log("Iniciando aplicación. Estado actual: descanso.")

    def crear_interfaz(self):
        # Marco y texto para el nombre del paciente
        frame_paciente = tk.Frame(self.root, bg="antiquewhite1")
        frame_paciente.pack(pady=(15, 5))
        tk.Label(
            frame_paciente,
            text="Nombre del Paciente:",
            bg="antiquewhite1",
            font=("FreeSerif", 16),
        ).pack(side=tk.LEFT, padx=5)
        tk.Entry(
            frame_paciente,
            textvariable=self.nombre_paciente_var,
            width=50,
            font=("FreeSerif", 12),
        ).pack(side=tk.LEFT, padx=5)

        # Marco para los botones
        frame_botones = tk.Frame(self.root, pady=10, padx=10, bg="antiquewhite1")
        frame_botones.pack()
        frame_botones.rowconfigure(0, weight=1)
        frame_botones.columnconfigure(0, weight=1)

        # Botón Descanso (d)
        btn_descanso = tk.Button(
            frame_botones,
            text="Posición de Descanso",
            font=("FreeSerif", 20),
            width=20,
            pady=10,
            command=self.accion_descanso,
        )
        btn_descanso.grid(row=0, column=0, padx=5, pady=5)

        # Botón Inicio (i)
        btn_inicio = tk.Button(
            frame_botones,
            text="Posición de Inicio",
            font=("FreeSerif", 20),
            width=20,
            pady=10,
            command=self.accion_inicio,
        )
        btn_inicio.grid(row=0, column=1, padx=5, pady=5)

        # Botón Capturar (c)
        btn_capturar = tk.Button(
            frame_botones,
            text="Iniciar Captura",
            font=("FreeSerif", 20),
            width=20,
            pady=10,
            bg="lightblue",
            command=self.accion_capturar,
        )
        btn_capturar.grid(row=1, column=0, padx=5, pady=(5, 60))

        # Botón Detener (s)
        btn_detener = tk.Button(
            frame_botones,
            text="Detener Programa",
            font=("FreeSerif", 20),
            width=20,
            pady=10,
            bg="indianred",
            command=self.accion_detener,
        )
        btn_detener.grid(row=1, column=1, padx=5, pady=(5, 60))

        # Caja de texto para logs (reemplaza a los prints)
        tk.Label(
            self.root,
            text="Registro de actividad:",
            bg="antiquewhite1",
            font=("FreeSerif", 16),
        ).pack(
            anchor=tk.W,
            padx=100,
        )
        self.caja_log = scrolledtext.ScrolledText(
            self.root, width=58, height=35, state="disabled", font=("FreeSerif", 12)
        )
        self.caja_log.pack(padx=10, pady=5)

    def log(self, mensaje):
        """
        Recibe el mensaje desde cualquier hilo, pero le pide al hilo principal (root)
        que sea él quien actualice la interfaz de forma segura.
        """
        self.root.after(0, lambda: self._escribir_en_interfaz(mensaje))

    def _escribir_en_interfaz(self, mensaje):

        self.caja_log.config(state="normal")
        self.caja_log.insert(
            tk.END, f"{datetime.now().strftime('%H:%M:%S')} - {mensaje}\n"
        )
        self.caja_log.see(tk.END)
        self.caja_log.config(state="disabled")

    def convertir_signo(self, valor):
        if valor > 32767:
            return valor - 65536
        return valor

    # --- FUNCIONES DE LOS BOTONES ---

    def accion_descanso(self):
        self.client.write_single_register(133, 1)
        self.estado_actual = "descanso"
        self.log("Posición de descanso.")

    def accion_inicio(self):
        self.client.write_single_register(132, 1)
        self.estado_actual = "inicio"
        self.log("Posición de inicio.")

    def accion_detener(self):
        self.client.write_single_register(133, 1)
        self.estado_actual = "descanso"
        self.capturando = False  # Detiene el hilo de captura
        self.log("Programa detenido. Cerrando interfaz...")

        # Espera 1.5 segundos para que alcances a leer el log y luego cierra la ventana
        self.root.after(1500, self.root.destroy)

    def accion_capturar(self):
        if not self.nombre_paciente_var.get().strip():
            messagebox.showwarning(
                "Advertencia",
                "Por favor, ingrese el nombre del paciente antes de capturar.",
            )
            return

        if self.estado_actual == "descanso":
            messagebox.showwarning(
                "Advertencia", "Necesita estar en la posición de inicio para capturar."
            )
            return

        if self.capturando:
            self.log("La captura ya está en proceso.")
            return

        # Iniciar el proceso en un hilo separado
        self.capturando = True
        hilo = threading.Thread(target=self.proceso_captura_hilo, daemon=True)
        hilo.start()

    def proceso_captura_hilo(self):
        """Esta función se ejecuta en segundo plano para no congelar la GUI."""
        self.log("Iniciando cámara y proceso de captura...")
        cap = cv.VideoCapture(0)

        if not cap.isOpened():
            self.log("ERROR: No se pudo abrir la cámara.")
            self.capturando = False
            return

        # Configuración de carpetas
        base_path = "capturas"
        os.makedirs(base_path, exist_ok=True)
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

        # NUEVO: Guardar el registro en el CSV maestro de pacientes
        nombre_paciente = self.nombre_paciente_var.get().strip()
        archivo_maestro_pacientes = os.path.join(base_path, "registro_pacientes.csv")
        archivo_existe = os.path.exists(archivo_maestro_pacientes)

        try:
            with open(
                archivo_maestro_pacientes, mode="a", newline="", encoding="utf-8"
            ) as f_maestro:
                writer_maestro = csv.writer(f_maestro, delimiter=",")
                if not archivo_existe:
                    # Escribir cabecera si el archivo se acaba de crear
                    writer_maestro.writerow(
                        ["ID_Carpeta", "Nombre_Paciente", "Fecha_Hora"]
                    )

                writer_maestro.writerow(
                    [f"{siguiente_id:05d}", nombre_paciente, ts_actual]
                )
            self.log(
                f"Paciente '{nombre_paciente}' registrado con ID {siguiente_id:05d}."
            )
        except Exception as e:
            self.log(f"Error guardando registro maestro: {e}")

        nombre_archivo = os.path.join(carpeta_fotos, f"movimientos_{ts_actual}.csv")

        # Variables lógicas
        ultimo_angulo_foto = None
        contador_fotos_angulo = 0
        max_capturas_por_dato = 5
        angulo_anterior = 0
        direccion_actual = "ida"
        fase = 1
        robot_arrancado = False

        try:
            with open(nombre_archivo, mode="w", newline="") as file:
                writer = csv.writer(file, delimiter=",")
                writer.writerow(
                    ["Fecha", "Hora", "Ángulo", "Dirección", "Subtrayectoria"]
                )

                ultimo_tiempo_modbus = time.time()

                # Bucle principal de captura (depende de self.capturando)
                while cap.isOpened() and self.capturando:
                    ret, frame = cap.read()
                    if not ret:
                        self.log("Error al leer frame de la cámara.")
                        break

                    if not robot_arrancado:
                        self.client.write_single_register(128, 1)
                        robot_arrancado = True
                        self.log("Robot arrancado (Reg 128=1).")

                    tiempo_actual = time.time()
                    if (
                        tiempo_actual - ultimo_tiempo_modbus
                        >= self.tiempo_entre_captura
                    ):
                        reg_angulo = self.client.read_holding_registers(129, 1)
                        reg_activar = self.client.read_holding_registers(128, 1)

                        if reg_angulo and reg_activar:
                            angulo_val = self.convertir_signo(reg_angulo[0])
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
                                self.log(
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

                            # Lógica de captura de foto
                            clave_foto = (angulo_val, fase)
                            if angulo_val in self.lista_angulos:
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
                                    self.log(
                                        f"FOTO: Subtrayectoria {fase:02d} | Ang {angulo_val:02d}"
                                    )

                            elif angulo_val == 0:
                                ultimo_angulo_foto = None
                                contador_fotos_angulo = 0

                            angulo_anterior = angulo_val
                            ultimo_tiempo_modbus = tiempo_actual

                            if activar == 0:
                                self.estado_actual = "descanso"
                                self.log("Señal de detención recibida por Modbus.")
                                self.capturando = False
                                break

        except Exception as e:
            self.log(f"Error en captura: {e}")
        finally:
            cap.release()
            self.capturando = False
            self.log("Captura finalizada y recursos liberados.")


if __name__ == "__main__":
    root = tk.Tk()
    app = RobotGUI(root)

    # Manejar el cierre seguro de la ventana
    def on_closing():
        app.capturando = False
        app.client.close()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
