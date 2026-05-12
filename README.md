1) En el ordenador SERVIDOR (el que hace el scraping potente)
Instala las dependencias:pip install requests beautifulsoup4 networkx matplotlib
2) Ejecuta el servidor:
3) LLenar la configuración:
  Puerto: escribe 9999 (o el que quieras)
  Máx páginas: 50 (o más si quieres)
  Profundidad: 3 (o más)
4) Si todo va bien verás algo como:
   🚀 SERVIDOR CRAWLER INICIADO
   📡 Escuchando en el puerto: 9999
     Esperando conexiones de clientes...
5) Anota tu DIRECCIÓN IP (para que los clientes se conecten):
  En Windows: abre cmd y escribe ipconfig → busca "IPv4"
  En Linux/Mac: abre terminal y escribe ifconfig o ip addr
6) En el ordenador del cliente no se necesita instalar las librerias anteriores, solo ingresar datos
    Ingresa los datos del servidor:
    IP del servidor: la IP que anotaste antes (ej: 192.168.1.100)
    Puerto: 9999 (el mismo que configuraste en el servidor)
7) Ingresa las URLs que quieres analizar:
8) Espera a recibir los datos del servidor
