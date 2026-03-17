# Take-pictures-with-UR5-robot-via-MODBUS
Uso de la librería pyModbusTCP para enviar y recibir multiples datos de el robot UR5, recibe los ángulos para tomar fotos en ciertos ángulos usando una cámara colocada como herramienta en la punta del brazo robótico y captura los datos en un archivo .csv

# Puertos MODBUS
**Port 128** = Variable de activación del robot\
**Port 129** = Ángulo en grados desde posición inicial a posición actual\
**Port 130** = Ángulo en grados del eje X\
**Port 131** = Ángulo en grados del eje Y

# Instrucciones de código
**1. Dirigirse a la carpeta donde quieres crear el entorno virtual mediante la terminal**

**2. Crear un entorno virtual de python con permisos para acceder a las librerias del sistema:**\
python3 -m venv --system-site-packages nombre-del-entorno

**3. Entrar al entorno virtual:**\
   source nombre-del-entorno/bin/activate

**4. Instalar librerias:**\
pip install pyModbusTCP\
pip install opencv-python

**5. Modificar valores del código:**\
ip_robot = "ip asignada del robot"\
tiempo_entre_captura = "tiempo en el que se estan capturando datos"\
lista_angulos = "angulos en los que se capturan las fotos"

**6. Correr el código**
