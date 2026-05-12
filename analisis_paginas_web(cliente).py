

import socket
import json

def analizar_url(host, puerto, url):
    """
    Envía una URL al servidor y recibe los resultados
    
    Parámetros:
    - host: dirección IP del servidor (ej: "192.168.1.100" o "localhost")
    - puerto: puerto donde escucha el servidor (ej: 9999)
    - url: URL a analizar (ej: "https://wikipedia.org")
    """
    
    try:
        # Conectar al servidor
        print(f"🔌 Conectando a {host}:{puerto}...")
        cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cliente.connect((host, puerto))
        
        # Enviar URL
        print(f"📤 Enviando URL: {url}")
        cliente.send(url.encode('utf-8'))
        
        # Recibir resultados
        print("⏳ Esperando resultados del servidor...")
        respuesta = cliente.recv(1048576).decode('utf-8')  # 1MB buffer
        stats = json.loads(respuesta)
        
        # Mostrar resultados
        if 'error' in stats:
            print(f"\n❌ Error del servidor: {stats['error']}")
        else:
            print("\n" + "="*60)
            print("📊 RESULTADOS DEL ANÁLISIS")
            print("="*60)
            print(f"🌐 URL analizada: {stats['url_inicial']}")
            print(f"🏠 Dominio: {stats['dominio']}")
            print(f"📄 Páginas encontradas: {stats['num_nodos']}")
            print(f"🔗 Enlaces internos: {stats['num_aristas']}")
            print(f"📈 Densidad del grafo: {stats['densidad']:.6f}")
            print(f"⭐ Grado promedio: {stats['grado_promedio']:.2f}")
            
            print(f"\n🏆 TOP 10 PÁGINAS MÁS CONECTADAS:")
            print("-"*60)
            for i, pagina in enumerate(stats['top_10_paginas'], 1):
                print(f"\n{i}. {pagina['nombre']}")
                print(f"   📎 URL: {pagina['url'][:80]}...")
                print(f"   🔄 Conexiones totales: {pagina['grado_total']}")
                print(f"   📤 Enlaces salientes: {pagina['grado_salida']}")
                print(f"   📥 Enlaces entrantes: {pagina['grado_entrada']}")
            
            # Guardar resultados en archivo
            archivo_salida = f"resultado_{stats['dominio'].replace('.', '_')}.json"
            with open(archivo_salida, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Resultados guardados en: {archivo_salida}")
        
        cliente.close()
        
    except ConnectionRefusedError:
        print(f"\n❌ ERROR: No se pudo conectar a {host}:{puerto}")
        print("   Verifica que:")
        print("   1. El servidor esté ejecutándose")
        print("   2. El puerto sea correcto")
        print("   3. No haya un firewall bloqueando")
    except Exception as e:
        print(f"\n❌ Error: {e}")

# ============ INTERFAZ DE USUARIO ============
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🌐 CLIENTE PARA ANÁLISIS DE WEBSITES")
    print("="*60)
    
    # Configuración del servidor
    print("\n🔧 CONFIGURACIÓN DEL SERVIDOR:")
    print("-"*40)
    
    # ¿Cómo saber qué puerto usar?
    print("\n📌 ¿CÓMO SABER QUÉ PUERTO USAR?")
    print("   El puerto debe ser el MISMO que configuraste en el servidor.")
    print("   Por defecto, el servidor usa el puerto 9999.")
    print("   Pregúntale a la persona que ejecuta el servidor qué puerto usó.")
    print("\n   Puertos comunes:")
    print("   • 9999 - Puerto por defecto de este programa")
    print("   • 8080 - Puerto alternativo común")
    print("   • 8888 - Otro puerto común")
    print("   • 5000 - Puerto para desarrollo")
    
    # Solicitar datos del servidor
    host = input("\n🌍 IP del servidor (ej: 192.168.1.100 o 'localhost'): ").strip()
    if not host:
        host = "localhost"
    
    puerto_input = input(f"🔌 Puerto del servidor (por defecto 9999): ").strip()
    puerto = int(puerto_input) if puerto_input else 9999
    
    print(f"\n📡 Conectando a {host}:{puerto}...")
    
    # Bucle para enviar múltiples URLs
    while True:
        print("\n" + "-"*60)
        url = input("\n🔗 URL a analizar (o 'salir' para terminar): ").strip()
        
        if url.lower() == 'salir':
            print("👋 ¡Hasta luego!")
            break
        
        if not url.startswith('http'):
            url = 'https://' + url
        
        print()  # Línea en blanco
        analizar_url(host, puerto, url)