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

# Función auxiliar a nivel de módulo para multiprocessing
def process_node_for_centrality(args):
    """Función independiente para calcular el grado de un nodo (pickleable)"""
    node, edges_list = args
    # Crear un grafo temporal
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
        
        # Grafo dirigido (NetworkX)
        self.graph = nx.DiGraph()
        
        # Diccionario para almacenar nombres de nodos (URL -> nombre legible)
        self.node_names = {}
        
        # Estructuras para control de crawling
        self.visited = set()
        self.to_visit = deque()
        
        # Añadir la URL inicial
        self.to_visit.append((start_url, 0))
    
    def extract_h1(self, soup):
        """Extrae el texto del primer tag <h1> encontrado"""
        h1 = soup.find('h1')
        if h1:
            # Limpiar el texto: eliminar espacios extra y saltos de línea
            text = ' '.join(h1.stripped_strings)
            # Limitar longitud para nombres muy largos
            if len(text) > 50:
                text = text[:47] + "..."
            return text
        return None
    
    def extract_page_title(self, soup, url):
        """Extrae un nombre legible para la página (prioridad: h1 > title > URL)"""
        # Intentar con h1 primero
        h1_text = self.extract_h1(soup)
        if h1_text:
            return h1_text
        
        # Si no hay h1, intentar con <title>
        title = soup.find('title')
        if title and title.string:
            title_text = ' '.join(title.stripped_strings)
            if len(title_text) > 50:
                title_text = title_text[:47] + "..."
            return title_text
        
        # Si nada funciona, usar la última parte de la URL
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        if path:
            last_part = path.split('/')[-1]
            # Reemplazar guiones y guiones bajos con espacios
            last_part = re.sub(r'[-_]', ' ', last_part)
            # Capitalizar palabras
            last_part = last_part.title()
            if len(last_part) > 40:
                last_part = last_part[:37] + "..."
            return last_part or "Página principal"
        
        return "Inicio"
    
    def is_internal_link(self, url):
        """Devuelve True si la URL pertenece al mismo dominio."""
        parsed = urlparse(url)
        return parsed.netloc == self.domain or parsed.netloc == ''
    
    def normalize_url(self, base, link):
        """Convierte enlace relativo a absoluto y limpia fragmentos."""
        absolute = urljoin(base, link)
        # Eliminar fragmento (#...) y parámetros comunes
        base_url = absolute.split('#')[0].split('?')[0]
        # Eliminar barra final para consistencia
        if base_url.endswith('/') and not base_url.endswith('//'):
            base_url = base_url[:-1]
        return base_url
    
    def fetch_and_extract(self, url, depth):
        """Descarga una página, extrae enlaces internos y actualiza el grafo."""
        if url in self.visited or depth > self.max_depth:
            return []
        
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            resp = requests.get(url, timeout=10, headers=headers)
            if resp.status_code != 200:
                return []
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Extraer nombre legible para la página
            page_name = self.extract_page_title(soup, url)
            self.node_names[url] = page_name
            
            internal_links = []
            
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                full_url = self.normalize_url(url, href)
                if self.is_internal_link(full_url) and full_url != url and full_url:
                    # Añadir arista al grafo (usando URL como identificador)
                    self.graph.add_edge(url, full_url)
                    internal_links.append(full_url)
            
            # Marcar como visitada
            self.visited.add(url)
            return [(link, depth+1) for link in internal_links if link not in self.visited]
        
        except Exception as e:
            print(f"Error al procesar {url}: {e}")
            return []
    
    def crawl(self):
        """Inicia el crawling usando ThreadPoolExecutor."""
        print(f"Iniciando crawling en {self.start_url}")
        print(f"Dominio: {self.domain}, Máx páginas: {self.max_pages}")
        print(f"Profundidad máxima: {self.max_depth}")
        print("-" * 60)
        
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            futures = {}
            
            while self.to_visit and len(self.visited) < self.max_pages:
                # Extraer lotes de URLs
                batch = []
                while self.to_visit and len(batch) < self.num_threads * 2:
                    batch.append(self.to_visit.popleft())
                
                for url, depth in batch:
                    if url in self.visited or depth > self.max_depth:
                        continue
                    future = executor.submit(self.fetch_and_extract, url, depth)
                    futures[future] = (url, depth)
                
                # Recolectar resultados
                for future in as_completed(futures):
                    url, depth = futures.pop(future)
                    new_links = future.result()
                    for new_url, new_depth in new_links:
                        if new_url not in self.visited and len(self.visited) < self.max_pages:
                            self.to_visit.append((new_url, new_depth))
                    
                    # Mostrar progreso con el nombre de la página
                    page_name = self.node_names.get(url, "Desconocido")
                    print(f"✓ {page_name[:40]:40} | Nodos: {len(self.visited):3} | Cola: {len(self.to_visit):3}")
                    
                    if len(self.visited) >= self.max_pages:
                        break
        
        print("-" * 60)
        print(f"\n✓ Crawling finalizado. Total páginas únicas visitadas: {len(self.visited)}")
        print(f"✓ Aristas en el grafo: {self.graph.number_of_edges()}")
    
    def get_node_display_name(self, url):
        """Obtiene el nombre para mostrar de un nodo (usando h1 o título)"""
        return self.node_names.get(url, url.split('/')[-1] or "Página")
    
    def compute_degree_centrality_parallel(self):
        """Calcula centralidad de grado usando multiprocessing"""
        if self.graph.number_of_nodes() == 0:
            print("Grafo vacío, no se puede calcular.")
            return {}
        
        if self.graph.number_of_nodes() < 10:
            print("Grafo muy pequeño, usando método secuencial...")
            centrality = dict(self.graph.degree())
            print("\n📊 Top páginas por grado (conexiones totales):")
            for node, deg in sorted(centrality.items(), key=lambda x: x[1], reverse=True):
                display_name = self.get_node_display_name(node)
                print(f"  • {display_name} -> {deg} conexiones")
            return centrality
        
        nodes = list(self.graph.nodes())
        edges = list(self.graph.edges())
        
        print(f"\n🔄 Calculando centralidad de grado usando multiprocessing (nodos: {len(nodes)})...")
        start = time.time()
        
        # Usar multiprocessing con la función de nivel de módulo
        try:
            with Pool() as pool:
                # Preparar argumentos
                args_list = [(node, edges) for node in nodes]
                results = pool.map(process_node_for_centrality, args_list)
            
            # Convertir resultados a diccionario
            centrality = dict(results)
            
            elapsed = time.time() - start
            print(f"⏱️  Tiempo de cálculo multiproceso: {elapsed:.2f} segundos")
            
            # Mostrar top nodos con mayor centralidad
            sorted_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
            print("\n🏆 Top 10 páginas con más conexiones (grado total):")
            for i, (node, deg) in enumerate(sorted_nodes[:10], 1):
                display_name = self.get_node_display_name(node)
                url_short = node[:40] + "..." if len(node) > 40 else node
                print(f"  {i:2}. {display_name}")
                print(f"      {deg} conexiones | {url_short}")
            
            return centrality
            
        except Exception as e:
            print(f"⚠️  Error en multiprocessing: {e}")
            print("Usando método secuencial como fallback...")
            centrality = dict(self.graph.degree())
            return centrality
    
    def draw_graph(self):
        """Dibuja y muestra el grafo si tiene menos de 1500 nodos"""
        num_nodes = self.graph.number_of_nodes()
        
        if num_nodes == 0:
            print("No hay nodos para dibujar.")
            return
        
        if num_nodes > 1500:
            print(f"⚠️  El grafo tiene {num_nodes} nodos (mayor a 1500). No se mostrará para evitar saturación.")
            print("\n📊 Estadísticas del grafo:")
            print(f"  • Nodos: {num_nodes}")
            print(f"  • Aristas: {self.graph.number_of_edges()}")
            print(f"  • Densidad: {nx.density(self.graph):.6f}")
            return
        
        print(f"\n🎨 Dibujando grafo con {num_nodes} nodos...")
        
        # Configurar el tamaño de la figura según el número de nodos
        figsize = min(16, max(10, num_nodes / 15))
        plt.figure(figsize=(figsize, figsize))
        
        # Crear un grafo etiquetado con nombres legibles para visualización
        graph_with_labels = nx.DiGraph()
        
        # Añadir nodos con atributo 'label'
        for node in self.graph.nodes():
            display_name = self.get_node_display_name(node)
            graph_with_labels.add_node(node, label=display_name)
        
        # Añadir aristas
        graph_with_labels.add_edges_from(self.graph.edges())
        
        # Usar diferentes layouts según el tamaño
        if num_nodes < 50:
            pos = nx.spring_layout(graph_with_labels, k=2, iterations=50, seed=42)
            node_size = 2000
            font_size = 10
            draw_labels = True
        elif num_nodes < 200:
            pos = nx.spring_layout(graph_with_labels, k=1.5, iterations=30, seed=42)
            node_size = 1200
            font_size = 9
            draw_labels = True
        else:
            pos = nx.spring_layout(graph_with_labels, k=1, iterations=20, seed=42)
            node_size = 800
            font_size = 8
            draw_labels = num_nodes < 100  # Solo etiquetas si es manejable
        
        # Dibujar nodos y aristas
        nx.draw_networkx_nodes(graph_with_labels, pos, node_size=node_size, 
                              node_color='lightblue', alpha=0.7, edgecolors='darkblue', linewidths=1)
        nx.draw_networkx_edges(graph_with_labels, pos, alpha=0.3, 
                              arrows=True, arrowsize=10, edge_color='gray')
        
        # Dibujar etiquetas
        if draw_labels:
            labels = nx.get_node_attributes(graph_with_labels, 'label')
            nx.draw_networkx_labels(graph_with_labels, pos, labels=labels, 
                                   font_size=font_size, font_weight='bold')
        
        plt.title(f"🌐 Grafo de enlaces internos - {self.domain}\n"
                 f"({num_nodes} páginas, {self.graph.number_of_edges()} enlaces)", 
                 fontsize=14, fontweight='bold')
        plt.axis('off')
        plt.tight_layout()
        
        # Guardar la imagen
        filename = f"grafo_{self.domain.replace('.', '_')}.png"
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        print(f"💾 Grafo guardado como '{filename}'")
        
        # Mostrar la figura
        try:
            plt.show()
        except Exception as e:
            print(f"⚠️  No se pudo mostrar la figura: {e}")
            print(f"   La imagen se guardó como '{filename}'")
    
    def save_graph(self, filename="crawled_graph.gpickle"):
        """Guarda el grafo y los nombres de los nodos en disco."""
        # Guardar grafo y nombres juntos
        data = {
            'graph': self.graph,
            'node_names': self.node_names,
            'domain': self.domain,
            'start_url': self.start_url
        }
        with open(filename, 'wb') as f:
            import pickle
            pickle.dump(data, f)
        print(f"💾 Grafo y nombres guardados en {filename}")
    
    def load_graph(self, filename="crawled_graph.gpickle"):
        """Carga un grafo guardado previamente."""
        try:
            with open(filename, 'rb') as f:
                import pickle
                data = pickle.load(f)
            self.graph = data['graph']
            self.node_names = data['node_names']
            self.domain = data['domain']
            self.start_url = data['start_url']
            print(f"✓ Grafo cargado desde {filename}")
            print(f"  • Nodos: {self.graph.number_of_nodes()}")
            print(f"  • Aristas: {self.graph.number_of_edges()}")
            print(f"  • Dominio: {self.domain}")
        except Exception as e:
            print(f"Error al cargar grafo: {e}")
    
    def graph_summary(self):
        """Muestra un resumen completo del grafo con nombres legibles."""
        print("\n" + "="*70)
        print("📊 RESUMEN DEL GRAFO")
        print("="*70)
        print(f"🌐 URL inicial: {self.start_url}")
        print(f"🏠 Dominio: {self.domain}")
        print(f"📄 Nodos (páginas únicas): {self.graph.number_of_nodes()}")
        print(f"🔗 Aristas (enlaces internos): {self.graph.number_of_edges()}")
        
        if self.graph.number_of_nodes() > 0:
            print(f"📈 Densidad del grafo: {nx.density(self.graph):.6f}")
            
            # Verificar si es conexo
            if nx.is_weakly_connected(self.graph):
                print("✓ El grafo es débilmente conexo")
            else:
                num_components = nx.number_weakly_connected_components(self.graph)
                print(f"📦 El grafo tiene {num_components} componentes débilmente conexas")
            
            # Calcular grado promedio
            avg_degree = sum(dict(self.graph.degree()).values()) / self.graph.number_of_nodes()
            print(f"📊 Grado promedio: {avg_degree:.2f}")
            
            print("\n" + "="*70)
            print("🏆 TOP PÁGINAS POR RELEVANCIA")
            print("="*70)
            
            # Nodos con mayor grado de salida (más enlaces hacia otras páginas)
            out_degrees = dict(self.graph.out_degree())
            top_out = sorted(out_degrees.items(), key=lambda x: x[1], reverse=True)[:5]
            print("\n📤 Páginas con más ENLACES SALIENTES (las que más referencian):")
            for i, (node, deg) in enumerate(top_out, 1):
                display_name = self.get_node_display_name(node)
                print(f"  {i}. 🏠 {display_name}")
                print(f"     → {deg} enlaces hacia otras páginas")
                print(f"     📎 {node[:70]}...")
            
            # Nodos con mayor grado de entrada (más referenciadas)
            in_degrees = dict(self.graph.in_degree())
            top_in = sorted(in_degrees.items(), key=lambda x: x[1], reverse=True)[:5]
            print("\n📥 Páginas más ENLAZADAS (las más populares):")
            for i, (node, deg) in enumerate(top_in, 1):
                display_name = self.get_node_display_name(node)
                print(f"  {i}. ⭐ {display_name}")
                print(f"     → Recibe {deg} enlaces desde otras páginas")
                print(f"     📎 {node[:70]}...")
            
            # Si hay pocos nodos, mostrar todos
            if self.graph.number_of_nodes() <= 20:
                print("\n" + "="*70)
                print("📋 LISTA COMPLETA DE PÁGINAS")
                print("="*70)
                for i, node in enumerate(self.graph.nodes(), 1):
                    display_name = self.get_node_display_name(node)
                    out_deg = self.graph.out_degree(node)
                    in_deg = self.graph.in_degree(node)
                    print(f"{i:2}. {display_name}")
                    print(f"    📤 Salientes: {out_deg} | 📥 Entrantes: {in_deg}")
                    print(f"    🔗 {node[:80]}")
        
        print("="*70)

# Ejemplo de uso
if __name__ == "__main__":
    print("="*70)
    print("🌐 CRAWLER DE ENLACES INTERNOS CON GRAFO NOMBRADO")
    print("="*70)
    print("\n✨ Características:")
    print("  • Extrae etiquetas <h1> para nombrar páginas")
    print("  • Usa threading para descarga paralela")
    print("  • Multiprocessing para análisis")
    print("  • Visualización con NetworkX")
    print("="*70)
    
    # Configuración - puedes cambiar estas URLs
    START_URL = "https://tutorial.math.lamar.edu"  # Sitio de prueba
    # START_URL = "https://quotes.toscrape.com/"  # Otro sitio de prueba
    # START_URL = "https://example.com/"  # Sitio muy simple
    
    MAX_PAGES = 30  # Reducido para pruebas rápidas
    MAX_DEPTH = 2
    NUM_THREADS = 8
    
    print(f"\n⚙️  Configuración:")
    print(f"  • URL inicial: {START_URL}")
    print(f"  • Máx páginas: {MAX_PAGES}")
    print(f"  • Profundidad máx: {MAX_DEPTH}")
    print(f"  • Hilos: {NUM_THREADS}")
    print("\n🕷️  Iniciando crawler...\n")
    
    # Crear crawler
    crawler = InternalLinkCrawler(START_URL, max_pages=MAX_PAGES, max_depth=MAX_DEPTH, num_threads=NUM_THREADS)
    
    # Ejecutar crawling (threading)
    crawler.crawl()
    
    # Mostrar resumen del grafo
    crawler.graph_summary()
    
    # Ejemplo de multiprocessing: calcular grado en paralelo
    if crawler.graph.number_of_nodes() > 0:
        crawler.compute_degree_centrality_parallel()
    
    # Dibujar grafo si tiene menos de 1500 nodos
    crawler.draw_graph()
    
    # Guardar grafo para después
    crawler.save_graph("mi_grafo_nombrado.gpickle")
    
    print("\n✅ ¡Programa finalizado correctamente!")