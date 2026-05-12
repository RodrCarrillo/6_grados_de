import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import networkx as nx
import matplotlib.pyplot as plt
from multiprocessing import Pool
import time
from collections import deque
import re
import json
import socket
import threading

# Función auxiliar para multiprocessing
def process_node_for_centrality(args):
    node, edges_list = args
    temp_graph = nx.DiGraph()
    temp_graph.add_edges_from(edges_list)
    return node, temp_graph.degree(node)

class InternalLinkCrawler:
    def __init__(self, start_url, max_pages=50, max_depth=3, num_threads=10):
        self.start_url = start_url
        self.domain = urlparse(start_url).netloc
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.num_threads = num_threads
        self.graph = nx.DiGraph()
        self.node_names = {}
        self.visited = set()
        self.to_visit = deque()
        self.to_visit.append((start_url, 0))
    
    def extract_h1(self, soup):
        h1 = soup.find('h1')
        if h1:
            text = ' '.join(h1.stripped_strings)
            if len(text) > 50:
                text = text[:47] + "..."
            return text
        return None
    
    def extract_page_title(self, soup, url):
        h1_text = self.extract_h1(soup)
        if h1_text:
            return h1_text
        title = soup.find('title')
        if title and title.string:
            title_text = ' '.join(title.stripped_strings)
            if len(title_text) > 50:
                title_text = title_text[:47] + "..."
            return title_text
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        if path:
            last_part = path.split('/')[-1]
            last_part = re.sub(r'[-_]', ' ', last_part)
            last_part = last_part.title()
            if len(last_part) > 40:
                last_part = last_part[:37] + "..."
            return last_part or "Página principal"
        return "Inicio"
    
    def is_internal_link(self, url):
        parsed = urlparse(url)
        return parsed.netloc == self.domain or parsed.netloc == ''
    
    def normalize_url(self, base, link):
        absolute = urljoin(base, link)
        base_url = absolute.split('#')[0].split('?')[0]
        if base_url.endswith('/') and not base_url.endswith('//'):
            base_url = base_url[:-1]
        return base_url
    
    def fetch_and_extract(self, url, depth):
        if url in self.visited or depth > self.max_depth:
            return []
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            resp = requests.get(url, timeout=10, headers=headers)
            if resp.status_code != 200:
                return []
            soup = BeautifulSoup(resp.text, 'html.parser')
            page_name = self.extract_page_title(soup, url)
            self.node_names[url] = page_name
            internal_links = []
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                full_url = self.normalize_url(url, href)
                if self.is_internal_link(full_url) and full_url != url and full_url:
                    self.graph.add_edge(url, full_url)
                    internal_links.append(full_url)
            self.visited.add(url)
            return [(link, depth+1) for link in internal_links if link not in self.visited]
        except Exception as e:
            print(f"Error al procesar {url}: {e}")
            return []
    
    def crawl(self):
        print(f"Iniciando crawling en {self.start_url}")
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            futures = {}
            while self.to_visit and len(self.visited) < self.max_pages:
                batch = []
                while self.to_visit and len(batch) < self.num_threads * 2:
                    batch.append(self.to_visit.popleft())
                for url, depth in batch:
                    if url in self.visited or depth > self.max_depth:
                        continue
                    future = executor.submit(self.fetch_and_extract, url, depth)
                    futures[future] = (url, depth)
                for future in as_completed(futures):
                    url, depth = futures.pop(future)
                    new_links = future.result()
                    for new_url, new_depth in new_links:
                        if new_url not in self.visited and len(self.visited) < self.max_pages:
                            self.to_visit.append((new_url, new_depth))
                    print(f"✓ Procesada | Nodos: {len(self.visited):3} | Cola: {len(self.to_visit):3}")
                    if len(self.visited) >= self.max_pages:
                        break
        print(f"\n✓ Crawling finalizado. Total páginas: {len(self.visited)}")
    
    def get_graph_stats(self):
        stats = {
            'url_inicial': self.start_url,
            'dominio': self.domain,
            'num_nodos': self.graph.number_of_nodes(),
            'num_aristas': self.graph.number_of_edges(),
            'densidad': nx.density(self.graph) if self.graph.number_of_nodes() > 0 else 0,
            'grado_promedio': sum(dict(self.graph.degree()).values()) / self.graph.number_of_nodes() if self.graph.number_of_nodes() > 0 else 0,
            'paginas': []
        }
        for node in self.graph.nodes():
            stats['paginas'].append({
                'url': node,
                'nombre': self.node_names.get(node, 'Desconocido'),
                'grado_salida': self.graph.out_degree(node),
                'grado_entrada': self.graph.in_degree(node),
                'grado_total': self.graph.degree(node)
            })
        stats['paginas'].sort(key=lambda x: x['grado_total'], reverse=True)
        stats['top_10_paginas'] = stats['paginas'][:10]
        return stats

# ============ SERVIDOR SOCKET ============
def iniciar_servidor(puerto=9999, max_paginas=50, profundidad=3):
    """Inicia el servidor que espera conexiones de clientes"""
    
    def manejar_cliente(cliente_socket, direccion):
        print(f"📡 Cliente conectado desde {direccion}")
        try:
            # Recibir URL del cliente
            url = cliente_socket.recv(4096).decode('utf-8').strip()
            print(f"📥 URL recibida: {url}")
            
            # Ejecutar crawling
            crawler = InternalLinkCrawler(url, max_pages=max_paginas, max_depth=profundidad, num_threads=8)
            crawler.crawl()
            stats = crawler.get_graph_stats()
            
            # Enviar resultados
            respuesta = json.dumps(stats, ensure_ascii=False)
            cliente_socket.send(respuesta.encode('utf-8'))
            print(f"📤 Resultados enviados a {direccion}")
            
        except Exception as e:
            error_msg = json.dumps({'error': str(e)})
            cliente_socket.send(error_msg.encode('utf-8'))
            print(f"❌ Error: {e}")
        finally:
            cliente_socket.close()
    
    # Crear socket del servidor
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind(('0.0.0.0', puerto))
    servidor.listen(5)
    
    print("="*60)
    print("🚀 SERVIDOR CRAWLER INICIADO")
    print("="*60)
    print(f"📡 Escuchando en el puerto: {puerto}")
    print(f"🌐 Accesible desde: tu IP local o 0.0.0.0:{puerto}")
    print(f"📊 Máximo páginas por análisis: {max_paginas}")
    print(f"🔍 Profundidad máxima: {profundidad}")
    print("="*60)
    print("Esperando conexiones de clientes...")
    print("Presiona Ctrl+C para detener el servidor\n")
    
    try:
        while True:
            cliente, direccion = servidor.accept()
            hilo = threading.Thread(target=manejar_cliente, args=(cliente, direccion))
            hilo.daemon = True
            hilo.start()
    except KeyboardInterrupt:
        print("\n🛑 Servidor detenido")
        servidor.close()

# ============ PUNTO DE ENTRADA ============
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔧 CONFIGURACIÓN DEL SERVIDOR")
    print("="*60)
    
    # Configuración - ¡PUEDES CAMBIAR ESTOS VALORES!
    PUERTO = 9999  # Puerto por defecto (puedes cambiarlo: 8080, 8888, etc.)
    MAX_PAGINAS = 50  # Máximo de páginas a scrapear por URL
    PROFUNDIDAD = 3   # Profundidad de crawling
    
    print(f"\n⚙️  Configuración actual:")
    print(f"   • Puerto: {PUERTO}")
    print(f"   • Máx páginas: {MAX_PAGINAS}")
    print(f"   • Profundidad: {PROFUNDIDAD}")
    
    cambiar = input("\n¿Quieres cambiar la configuración? (s/n): ").strip().lower()
    if cambiar == 's':
        nuevo_puerto = input(f"Nuevo puerto (Enter para {PUERTO}): ").strip()
        if nuevo_puerto:
            PUERTO = int(nuevo_puerto)
        
        nuevas_paginas = input(f"Nuevo máximo de páginas (Enter para {MAX_PAGINAS}): ").strip()
        if nuevas_paginas:
            MAX_PAGINAS = int(nuevas_paginas)
        
        nueva_profundidad = input(f"Nueva profundidad (Enter para {PROFUNDIDAD}): ").strip()
        if nueva_profundidad:
            PROFUNDIDAD = int(nueva_profundidad)
    
    # Iniciar servidor
    iniciar_servidor(puerto=PUERTO, max_paginas=MAX_PAGINAS, profundidad=PROFUNDIDAD)