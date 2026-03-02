from pyModbusTCP.client import ModbusClient
import time
import csv
from datetime import datetime
import cv2 as cv
import os

#Ajustes iniciales, IP a la que se conecta el robot, tiempo entre captura
#y lista de angulos en los que se estaran tomando fotos
ip_robot="192.168.20.130"
tiempo_entre_captura = 0.2
lista_angulos = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45]

#Función para convertir valores unsigned a signed para ver numeros negativos
def convertir_signo(valor):
    if valor > 32767:
        return valor - 65536
    return valor

#Ajuste del cliente, colocando la ip al cual va direccionado,
#el port y el unit_id generalmente no cambia para MODBUS
client = ModbusClient(host=ip_robot, port=502, unit_id=255)

#Se abre el cliente y se actaliza el registro 128 a 1 para activar la 
#variable de encendido y activar el movimiento del robot               
client.open()
client.write_single_register(128, 1)
print("Registro 128 actualizado a 1")

#Se configura la camara que se va a utilizar
cap = cv.VideoCapture(0)

#Lee continuamente el valor del angulo
#y espera a que el angulo sea igual a 0 para continuar,
#cuando el angulo es igual a 0 quiere decir que llegó a la posicion inicial
print("Esperando señal de inicio (Ángulo = 0)...")
while True:
    angulo = client.read_holding_registers(129, 1)
    cap.read()
    if angulo and angulo[0] == 0:
        print("Se ha recibido la señal para iniciar.")
        break
    time.sleep(0.1)

#Crea una carpeta para guardar las fotos y un archivo para los datos
carpeta_fotos = "capturas"
os.makedirs(carpeta_fotos, exist_ok=True)
nombre_archivo = f"movimientos_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"

# Variables de estado para guardar la fase en la que se encuentra
ultimo_angulo_foto = None
angulo_anterior = 0
direccion_actual = "ida"
fase = 1 

#Configura el archivo con los datos que se va a guardar, 
#el nombre de las columnas y las especificaciones del archivo
with open(nombre_archivo, mode='w', newline='') as file:
    writer = csv.writer(file, delimiter=',')
    writer.writerow(["Fecha", "Hora", "Ángulo", "Dirección", "Fase", "Mov X", "Mov Y", "Posición"])
    
    #Ajusta el tiempo de captura de datos para que no se interponga
    #con el de captura de fotos y se inicializa la variable posicion en 0
    ultimo_tiempo_modbus = time.time()
    posicion = 0
		
		#Inicia in ciclo mientras la camara esta abierta y capturando
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
				
				#Control de la frecuencia de registros de datos
				#lectura de los puertos MODBUS
        if time.time() - ultimo_tiempo_modbus >= tiempo_entre_captura:
            reg_angulo = client.read_holding_registers(129, 1)
            reg_movx = client.read_holding_registers(130, 1)
            reg_movy = client.read_holding_registers(131, 1)
            reg_activar = client.read_holding_registers(128, 1)
						
						#Cuando detecta valores en correctos en todos los registros
						#convierte a enteros con signo los valores obtenidos
            if reg_angulo and reg_movx and reg_movy and reg_activar:
                angulo_val = convertir_signo(reg_angulo[0])
                movx = convertir_signo(reg_movx[0])
                movy = convertir_signo(reg_movy[0])
                activar = reg_activar[0]

                # Lógica de detección de fase
                #Interpretación si va de ida o de regreso comparando el angulo anterior
                nueva_direccion = direccion_actual
                if angulo_val > angulo_anterior:
                    nueva_direccion = "ida"
                elif angulo_val < angulo_anterior:
                    nueva_direccion = "regreso"
                    
								#Aumenta el numero de fase cada que cambia de dirección
								#resetea la variable ultimo_angulo_foto para tomar fotos de regreso
                if nueva_direccion != direccion_actual:
                    fase += 1  # Incrementa fase: ida (1) -> regreso (2) -> ida (3)...
                    direccion_actual = nueva_direccion
                    ultimo_angulo_foto = None # Reset para permitir fotos en misma posición pero nueva fase
                    print(f"Cambio detectado: Fase {fase} ({direccion_actual})")

                #Detección de la posición dependiendo en que angulos se encuentra
                if(movx<-1 and -1<=movy<=1): posicion=4
                elif(movx>1 and -1<=movy<=1): posicion=2
                elif(-1<=movx<=1 and movy>1): posicion=1
                elif(-1<=movx<=1 and movy<-1): posicion=3
                elif(-1<=movx<=1 and -1<=movy<=1): posicion=0
                elif(movx>1 and movy<-1): posicion=6
                elif(movx>1 and movy>1): posicion=5
                elif(movx<-1 and movy>1): posicion=7
                elif(movx<-1 and movy<-1): posicion=8
								
								#Guarda el archivo de los datos y escribe el nombre con el que se guarda
                ahora = datetime.now()
                writer.writerow([ahora.strftime("%Y-%m-%d"), ahora.strftime("%H:%M:%S"), 
                                 angulo_val, direccion_actual, fase, movx, movy, posicion])
                file.flush()

                #Determina si tomar la captura con los angulos asignados, 
                #guarda si ya tomo captura en ese angulo para solo tomar una foto y
                #guarda la captura con un nombre asignado en la carpeta
                clave_foto = (angulo_val, fase)
                if angulo_val in lista_angulos:
                    if clave_foto != ultimo_angulo_foto:
                        nombre_foto = os.path.join(carpeta_fotos, 
                                      f"fase{fase}_ang{angulo_val}_{ahora.strftime('%H-%M-%S')}.png")
                        cv.imwrite(nombre_foto, frame)
                        print(f"FOTO: Fase {fase} | Ang {angulo_val} | Pos {posicion}")
                        ultimo_angulo_foto = clave_foto
                
                #Si el ultimo angulo guardado es 0 restaura la variable para seguir capturando
                elif angulo_val == 0:
                    ultimo_angulo_foto = None
                    
								#Gaurda el angulo anterior y la frecuencia de muestreo
                angulo_anterior = angulo_val
                ultimo_tiempo_modbus = time.time()
								
								#Si se lee un 0 en la variable activar detiene la captura
								#la variable activar es el mismo puerto que encendido del robot
                if activar == 0:
                    print("Señal de detención recibida.")
                    break
        #Orden para detener la grabación con la letra q
        if cv.waitKey(1) == ord('q'): break

#Liberación de recursos y cierre del cliente
cap.release()
cv.destroyAllWindows()
client.close()
