# Instrucciones de código
**1. Dirigirse a la carpeta donde quieres crear el entorno virtual mediante la terminal**

**2. Crear un entorno virtual de python con permisos para acceder a las librerias del sistema:**\
python -m venv --system-site-packages nombre-del-entorno

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
