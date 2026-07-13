import csv
import os
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, scrolledtext

import cv2 as cv
from PIL import Image, ImageTk
from pyModbusTCP.client import ModbusClient


class RobotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Control de Robot y Captura")
        self.root.geometry("1100x960")
        self.root.resizable(False, False)
        self.root.configure(bg="floralwhite")

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
        self.capturando = False

        # Variables para el control de la vista previa y cámara compartida
        self.preview_activo = False
        self.ventana_preview = None
        self.camara = None
        self.frame_actual = None
        self.lock_frame = threading.Lock()  # Para asegurar acceso correcto entre hilos
        self.hilo_camara_activo = (
            False  # NUEVO: Controla el hilo independiente de la cámara
        )

        # Variable para almacenar el nombre del paciente
        self.nombre_paciente_var = tk.StringVar()

        self.crear_interfaz()
        self.log("Iniciando aplicación. Estado actual: descanso.")

    def crear_interfaz(self):
        # Marco y texto para el nombre del paciente
        frame_paciente = tk.Frame(self.root, bg="floralwhite")
        frame_paciente.pack(pady=(15, 5))
        tk.Label(
            frame_paciente,
            text="Nombre del Paciente:",
            bg="floralwhite",
            font=("Garuda", 16),
        ).pack(side=tk.LEFT, padx=5)
        tk.Entry(
            frame_paciente,
            textvariable=self.nombre_paciente_var,
            width=50,
            font=("Garuda", 12),
        ).pack(side=tk.LEFT, padx=5)

        # Marco para los botones
        frame_botones = tk.Frame(self.root, pady=10, padx=10, bg="floralwhite")
        frame_botones.pack()
        frame_botones.rowconfigure(0, weight=1)
        frame_botones.columnconfigure(0, weight=1)
        frame_botones.columnconfigure(1, weight=1)
        frame_botones.columnconfigure(2, weight=1)

        # Botón Descanso (d)
        btn_descanso = tk.Button(
            frame_botones,
            text="Posición de Descanso",
            font=("Garuda", 20),
            width=20,
            pady=10,
            command=self.accion_descanso,
        )
        btn_descanso.grid(row=0, column=0, padx=5, pady=5)

        # Botón Inicio (i)
        btn_inicio = tk.Button(
            frame_botones,
            text="Posición de Inicio",
            font=("Garuda", 20),
            width=20,
            pady=10,
            command=self.accion_inicio,
        )
        btn_inicio.grid(row=0, column=1, padx=5, pady=5)

        # Botón Vista Previa
        self.btn_preview = tk.Button(
            frame_botones,
            text="Abrir Vista Previa",
            font=("Garuda", 20),
            width=20,
            pady=10,
            bg="lightgreen",
            command=self.toggle_preview,
        )
        self.btn_preview.grid(row=0, column=2, padx=5, pady=5)

        # Botón Capturar (c)
        btn_capturar = tk.Button(
            frame_botones,
            text="Iniciar Captura",
            font=("Garuda", 20),
            width=20,
            pady=10,
            bg="lightblue",
            command=self.accion_capturar,
        )
        btn_capturar.grid(row=1, column=0, padx=5, pady=(5, 40))

        # Botón Detener (s)
        btn_detener = tk.Button(
            frame_botones,
            text="Detener Robot",
            font=("Garuda", 20),
            width=20,
            pady=10,
            bg="indianred",
            command=self.accion_detener,
        )
        btn_detener.grid(row=1, column=1, padx=5, pady=(5, 40))

        # Caja de texto para logs
        tk.Label(
            self.root,
            text="Registro de actividad:",
            bg="floralwhite",
            font=("Garuda", 16),
        ).pack(
            anchor=tk.W,
            padx=100,
        )
        self.caja_log = scrolledtext.ScrolledText(
            self.root, width=58, height=35, state="disabled", font=("Garuda", 12)
        )
        self.caja_log.pack(padx=10, pady=5)

    def log(self, mensaje):
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

    # --- NUEVO: HILO DEDICADO A LEER LA CÁMARA CONSTANTEMENTE ---

    def asegurar_camara_encendida(self):
        """Inicia el hilo de lectura de cámara si no está corriendo ya."""
        if not self.hilo_camara_activo:
            self.hilo_camara_activo = True
            threading.Thread(target=self.bucle_lectura_camara, daemon=True).start()

    def bucle_lectura_camara(self):
        """Este hilo mantiene la cámara abierta mientras haya vista previa O captura."""
        self.camara = cv.VideoCapture(0)
        self.camara.set(cv.CAP_PROP_FRAME_WIDTH, 1280)
        self.camara.set(cv.CAP_PROP_FRAME_HEIGHT, 720)

        if not self.camara.isOpened():
            self.log("ERROR: No se pudo abrir la cámara de video.")
            self.hilo_camara_activo = False
            return

        self.log("Cámara iniciada correctamente en segundo plano.")

        # Mantener el bucle si necesitamos la cámara para algo
        while self.preview_activo or self.capturando:
            ret, frame = self.camara.read()
            if ret:
                with self.lock_frame:
                    self.frame_actual = frame.copy()
            else:
                time.sleep(0.01)  # Espera breve si falla el frame

        # Si llegamos aquí, ni la vista previa ni la captura la necesitan. Apagamos.
        self.camara.release()
        self.camara = None
        with self.lock_frame:
            self.frame_actual = None
        self.hilo_camara_activo = False
        self.log("Cámara liberada y apagada.")

    # --- FUNCIONES DE VISTA PREVIA ---

    def toggle_preview(self):
        if self.preview_activo:
            self.detener_preview()
        else:
            self.iniciar_preview()

    def iniciar_preview(self):
        if self.preview_activo:
            return

        self.preview_activo = True
        self.btn_preview.config(text="Cerrar Vista Previa", bg="khaki")
        self.log("Abriendo ventana de vista previa...")

        self.ventana_preview = tk.Toplevel(self.root)
        self.ventana_preview.title("Vista Previa (HD)")
        self.ventana_preview.geometry("1280x720")
        self.ventana_preview.resizable(False, False)
        self.ventana_preview.protocol("WM_DELETE_WINDOW", self.detener_preview)

        self.lbl_video = tk.Label(self.ventana_preview, bg="black")
        self.lbl_video.pack(fill=tk.BOTH, expand=True)

        # Nos aseguramos de que el hilo que lee la cámara esté corriendo
        self.asegurar_camara_encendida()

        self.actualizar_frame_preview()

    def actualizar_frame_preview(self):
        # Si la ventana se cerró, detenemos este bucle visual
        if not self.preview_activo or not self.ventana_preview.winfo_exists():
            return

        frame = None
        with self.lock_frame:
            if self.frame_actual is not None:
                frame = self.frame_actual.copy()

        if frame is not None:
            frame_rgb = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            imgtk = ImageTk.PhotoImage(image=img)

            self.lbl_video.imgtk = imgtk
            self.lbl_video.configure(image=imgtk)

        # Actualizar la interfaz a ~30 FPS
        self.ventana_preview.after(33, self.actualizar_frame_preview)

    def detener_preview(self):
        self.preview_activo = False
        self.btn_preview.config(text="Abrir Vista Previa", bg="lightgreen")

        if self.ventana_preview and self.ventana_preview.winfo_exists():
            self.ventana_preview.destroy()

        self.log("Ventana de vista previa cerrada.")
        # OJO: Ya no liberamos self.camara aquí. El hilo "bucle_lectura_camara"
        # se dará cuenta y la liberará automáticamente SOLAMENTE si self.capturando es False.

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
        self.client.write_single_register(134, 1)
        self.estado_actual = "descanso"
        self.capturando = False
        self.log("Programa de captura y robot detenidos.")

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

        # Iniciamos bandera de captura
        self.capturando = True

        # Nos aseguramos de que el hilo de cámara esté corriendo,
        # sin importar si la vista previa está abierta o cerrada.
        self.asegurar_camara_encendida()

        hilo = threading.Thread(target=self.proceso_captura_hilo, daemon=True)
        hilo.start()

    def proceso_captura_hilo(self):
        self.log("Iniciando recolección de datos e imágenes...")

        # Esperar brevemente a que la cámara entregue el primer frame si recién se encendió
        timeout = 100
        while self.frame_actual is None and timeout > 0 and self.capturando:
            time.sleep(0.05)
            timeout -= 1

        if self.frame_actual is None:
            self.log("ERROR: La cámara no está enviando fotogramas.")
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

        nombre_paciente = self.nombre_paciente_var.get().strip()
        archivo_maestro_pacientes = os.path.join(base_path, "registro_pacientes.csv")
        archivo_existe = os.path.exists(archivo_maestro_pacientes)

        try:
            with open(
                archivo_maestro_pacientes, mode="a", newline="", encoding="utf-8"
            ) as f_maestro:
                writer_maestro = csv.writer(f_maestro, delimiter=",")
                if not archivo_existe:
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

                while self.capturando:
                    # Pausa pequeña para no saturar el CPU
                    time.sleep(0.01)

                    # Obtener el último frame disponible de manera segura
                    with self.lock_frame:
                        if self.frame_actual is None:
                            continue
                        frame = self.frame_actual.copy()

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
            self.capturando = False
            self.log("Captura finalizada.")


if __name__ == "__main__":
    root = tk.Tk()
    app = RobotGUI(root)

    def on_closing():
        app.capturando = False
        app.preview_activo = False
        if app.ventana_preview and app.ventana_preview.winfo_exists():
            app.ventana_preview.destroy()
        app.client.close()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
