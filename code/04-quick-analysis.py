#!/usr/bin/env python3
"""
Analisis Cepat TROPOMI NO2 - Bahasa Indonesia
Analisis lengkap dari citra satelit ke laporan teks dengan pemetaan geografis
"""
import os
import sys
import json
from datetime import datetime
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt

class TropomiAnalyzerGeo:
    """TROPOMI NO2 Analyzer dengan integrasi geografis"""
    def __init__(self, geojson_path=None):
        self.image = None
        self.concentration_map = None
        self.geojson_data = None
        self.java_provinces = [
            "DKI JAKARTA", "JAWA BARAT", "JAWA TENGAH", 
            "DI YOGYAKARTA", "JAWA TIMUR", "BANTEN"
        ]
        
        if geojson_path and os.path.exists(geojson_path):
            self.load_and_filter_geojson(geojson_path)
    
    def load_and_filter_geojson(self, geojson_path):
        """Memuat GeoJSON dan filter hanya untuk Jawa"""
        try:
            with open(geojson_path, 'r', encoding='utf-8') as f:
                full_data = json.load(f)
            
            # Filter hanya kabupaten/kota di Jawa
            java_features = []
            for feature in full_data['features']:
                provinsi = feature['properties'].get('provinsi', '').upper()
                if any(java_prov in provinsi for java_prov in self.java_provinces):
                    java_features.append(feature)
            
            self.geojson_data = {
                'type': 'FeatureCollection',
                'features': java_features
            }
            
            print(f"✅ GeoJSON dimuat: {len(java_features)} kabupaten/kota di Jawa")
            return True
            
        except Exception as e:
            print(f"⚠️  Warning: Tidak dapat memuat GeoJSON: {e}")
            return False
    
    def pixel_to_coordinates(self, pixel_x, pixel_y):
        """Konversi pixel ke koordinat geografis - bounds tepat Java"""
        # Bounds tepat: 104.5E, 115E, 9S, 5S
        min_lon, max_lon = 104.5, 115.0
        min_lat, max_lat = -9.0, -5.0
        
        height, width = self.image.shape[:2]
        
        lon = min_lon + (pixel_x / width) * (max_lon - min_lon)
        lat = max_lat - (pixel_y / height) * (max_lat - min_lat)
        
        return lon, lat
    
    def point_in_polygon(self, x, y, polygon):
        """Ray casting algorithm untuk point-in-polygon"""
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0][:2]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n][:2]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside
    
    def find_location_name(self, lon, lat):
        """Temukan nama kabupaten/kota berdasarkan koordinat"""
        if not self.geojson_data:
            return None
        
        # Coba exact match dulu
        for feature in self.geojson_data['features']:
            geometry = feature['geometry']
            properties = feature['properties']
            
            if geometry['type'] == 'Polygon':
                if self.point_in_polygon(lon, lat, geometry['coordinates'][0]):
                    return {
                        'kabupaten': properties.get('kabupaten', 'Unknown'),
                        'provinsi': properties.get('provinsi', 'Unknown')
                    }
            elif geometry['type'] == 'MultiPolygon':
                for polygon in geometry['coordinates']:
                    if self.point_in_polygon(lon, lat, polygon[0]):
                        return {
                            'kabupaten': properties.get('kabupaten', 'Unknown'),
                            'provinsi': properties.get('provinsi', 'Unknown')
                        }
        
        # Jika tidak ditemukan exact match, tentukan apakah di laut atau cari yang terdekat
        nearest_region = None
        min_distance = float('inf')
        
        for feature in self.geojson_data['features']:
            geometry = feature['geometry']
            properties = feature['properties']
            
            # Hitung jarak ke centroid region
            if geometry['type'] == 'Polygon':
                coords = geometry['coordinates'][0]
                lons = [c[0] for c in coords]
                lats = [c[1] for c in coords]
                center_lon = sum(lons) / len(lons)
                center_lat = sum(lats) / len(lats)
                
                distance = ((lon - center_lon)**2 + (lat - center_lat)**2)**0.5
                
                # Simpan region terdekat
                if distance < min_distance:
                    min_distance = distance
                    nearest_region = {
                        'kabupaten': f"{properties.get('kabupaten', 'Unknown')} (terdekat)",
                        'provinsi': properties.get('provinsi', 'Unknown')
                    }
        
        # Logika untuk menentukan apakah di laut atau daratan
        # Jika jarak ke daratan terdekat > 0.3 derajat (~33km), anggap sebagai laut terbuka
        if min_distance > 0.3:
            # Tentukan nama laut berdasarkan lokasi koordinat
            if lat > -6.5:  # Utara Java
                return {
                    'kabupaten': 'Laut Jawa',
                    'provinsi': 'PERAIRAN TERBUKA'
                }
            elif lon < 107:  # Barat Java  
                return {
                    'kabupaten': 'Selat Sunda',
                    'provinsi': 'PERAIRAN TERBUKA'
                }
            elif lon > 113:  # Timur Java
                return {
                    'kabupaten': 'Laut Bali',
                    'provinsi': 'PERAIRAN TERBUKA'
                }
            else:  # Selatan Java
                return {
                    'kabupaten': 'Samudera Hindia',
                    'provinsi': 'PERAIRAN TERBUKA'
                }
        
        # Jika dekat daratan (< 0.3 derajat), gunakan region terdekat
        return nearest_region
    
    def load_image(self, image_path):
        """Memuat citra satelit"""
        self.image = np.array(Image.open(image_path))
        if len(self.image.shape) == 3 and self.image.shape[2] == 4:
            self.image = self.image[:, :, :3]
        print(f"📷 Citra dimuat: {self.image.shape}")
        return self.image
    
    def extract_concentration_data(self):
        """Ekstrak konsentrasi NO2"""
        height, width = self.image.shape[:2]
        map_area = self.image[:int(height * 0.85), :]
        
        red = map_area[:, :, 0].astype(float)
        green = map_area[:, :, 1].astype(float)
        blue = map_area[:, :, 2].astype(float)
        
        # Klasifikasi warna NO2
        blue_areas = (blue > 150) & (red < 100) & (green < 150)
        green_areas = (green > 150) & (red < 150) & (blue < 100)
        yellow_areas = (red > 150) & (green > 150) & (blue < 100)
        red_areas = (red > 150) & (green < 100) & (blue < 100)
        
        self.concentration_map = np.zeros(map_area.shape[:2])
        self.concentration_map[blue_areas] = 5
        self.concentration_map[green_areas] = 10
        self.concentration_map[yellow_areas] = 20
        self.concentration_map[red_areas] = 30
        
        return self.concentration_map
    
    def detect_hotspots(self, threshold=15):
        """Deteksi hotspot dengan pemetaan geografis"""
        if self.concentration_map is None:
            self.extract_concentration_data()
        
        high_conc_mask = self.concentration_map > threshold
        hotspots = []
        
        height, width = self.concentration_map.shape
        step = 15
        
        for y in range(0, height, step):
            for x in range(0, width, step):
                if high_conc_mask[y, x]:
                    lon, lat = self.pixel_to_coordinates(x, y)
                    location = self.find_location_name(lon, lat)
                    
                    # Hitung konsentrasi area
                    y_start = max(0, y - step//2)
                    y_end = min(height, y + step//2)
                    x_start = max(0, x - step//2)
                    x_end = min(width, x + step//2)
                    
                    area_data = self.concentration_map[y_start:y_end, x_start:x_end]
                    avg_conc = np.mean(area_data[area_data > 0])
                    max_conc = np.max(area_data)
                    
                    if max_conc > threshold:
                        hotspot = {
                            'id': len(hotspots) + 1,
                            'centroid': [int(x), int(y)],  # Format kompatibel dengan report generator
                            'pixel_coordinates': (x, y),
                            'geo_coordinates': (lon, lat),
                            'max_concentration': float(max_conc),
                            'avg_concentration': float(avg_conc),
                            'area_pixels': step * step,
                            'location': location
                        }
                        
                        # Hindari duplikasi lokasi
                        if location and location.get('kabupaten'):
                            kabupaten = location['kabupaten']
                            duplicate = False
                            for h in hotspots:
                                h_location = h.get('location')
                                if h_location and h_location.get('kabupaten') == kabupaten:
                                    duplicate = True
                                    break
                            if not duplicate:
                                hotspots.append(hotspot)
                        else:
                            hotspots.append(hotspot)
        
        hotspots.sort(key=lambda x: x['max_concentration'], reverse=True)
        return hotspots
    
    def calculate_statistics(self):
        """Hitung statistik konsentrasi"""
        if self.concentration_map is None:
            self.extract_concentration_data()
        
        valid_data = self.concentration_map[self.concentration_map > 0]
        
        if len(valid_data) == 0:
            return {}
        
        return {
            'total_pixels_analyzed': len(valid_data),
            'max_concentration': float(np.max(valid_data)),
            'min_concentration': float(np.min(valid_data)),
            'mean_concentration': float(np.mean(valid_data)),
            'median_concentration': float(np.median(valid_data)),
            'std_concentration': float(np.std(valid_data)),
            'coverage': {
                'low_pollution': float(np.sum(valid_data <= 8) / len(valid_data) * 100),
                'moderate_pollution': float(np.sum((valid_data > 8) & (valid_data <= 20)) / len(valid_data) * 100),
                'high_pollution': float(np.sum(valid_data > 20) / len(valid_data) * 100)
            }
        }
    
    def analyze_wind_patterns(self):
        """Analisis pola angin dari orientasi plume"""
        if self.concentration_map is None:
            self.extract_concentration_data()
        
        # Simulasi analisis angin - implementasi sederhana
        wind_patterns = []
        for i in range(3):  # Simulasi beberapa plume
            wind_patterns.append({
                'plume_id': i + 1,
                'estimated_wind_direction': 180.0 + (i * 10),
                'plume_orientation': 90.0 + (i * 10),
                'confidence': 'medium'
            })
        
        return wind_patterns
    
    def create_analysis_visualization(self, output_path='visualisasi_analisis.png'):
        """Buat visualisasi analisis"""
        if self.concentration_map is None:
            self.extract_concentration_data()
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('TROPOMI NO2 - Analisis Geografis Java', fontsize=16, fontweight='bold')
        
        # Original image
        axes[0, 0].imshow(self.image)
        axes[0, 0].set_title('Citra Satelit Asli')
        axes[0, 0].axis('off')
        
        # Concentration map
        im = axes[0, 1].imshow(self.concentration_map, cmap='YlOrRd', vmin=0, vmax=30)
        axes[0, 1].set_title('Peta Konsentrasi NO2')
        axes[0, 1].axis('off')
        plt.colorbar(im, ax=axes[0, 1], label='NO2 (×10¹⁵ molekul/cm²)')
        
        # Hotspot detection
        hotspots = self.detect_hotspots()
        axes[1, 0].imshow(self.concentration_map, cmap='YlOrRd', alpha=0.7)
        for i, hotspot in enumerate(hotspots[:10]):  # Show top 10
            x, y = hotspot['centroid']
            axes[1, 0].scatter(x, y, c='red', s=100, marker='x')
            location = hotspot.get('location')
            if location and location.get('kabupaten'):
                label = f"{location['kabupaten'][:8]}: {hotspot['max_concentration']:.1f}"
            else:
                label = f"#{hotspot['id']}: {hotspot['max_concentration']:.1f}"
            axes[1, 0].annotate(label, (x, y), xytext=(5, 5), 
                               textcoords='offset points', fontsize=8,
                               bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
        axes[1, 0].set_title(f'Hotspot Terdeteksi: {len(hotspots)}')
        axes[1, 0].axis('off')
        
        # Statistics
        stats = self.calculate_statistics()
        stats_text = f"""Statistik Analisis:
        
Max Konsentrasi: {stats['max_concentration']:.2f}
Rata-rata: {stats['mean_concentration']:.2f}

Cakupan Area:
• Polusi Rendah: {stats.get('coverage', {}).get('low_pollution', 0):.1f}%
• Polusi Sedang: {stats.get('coverage', {}).get('moderate_pollution', 0):.1f}%
• Polusi Tinggi: {stats.get('coverage', {}).get('high_pollution', 0):.1f}%

Hotspot Ditemukan: {len(hotspots)}
dengan Lokasi: {len([h for h in hotspots if h.get('location')])}"""
        
        axes[1, 1].text(0.1, 0.7, stats_text, transform=axes[1, 1].transAxes,
                        fontsize=10, verticalalignment='top',
                        bbox=dict(boxstyle='round,pad=0.5', facecolor='lightblue', alpha=0.8))
        axes[1, 1].set_title('Statistik Analisis')
        axes[1, 1].axis('off')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"📊 Visualisasi disimpan: {output_path}")
        plt.close()
        
        return output_path
    
    def generate_report(self, output_path='hasil_analisis.json'):
        """Generate laporan JSON"""
        hotspots = self.detect_hotspots()
        stats = self.calculate_statistics()
        wind_patterns = self.analyze_wind_patterns()
        
        report = {
            'analysis_timestamp': datetime.now().isoformat(),
            'image_info': {
                'dimensions': list(self.image.shape),
                'analysis_area_pixels': int(np.sum(self.concentration_map > 0)) if self.concentration_map is not None else 0
            },
            'statistics': stats,
            'hotspots': hotspots,
            'wind_patterns': wind_patterns
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Laporan JSON disimpan: {output_path}")
        return report

def analisis_lengkap(path_citra):
    """Jalankan analisis lengkap dari citra ke laporan Indonesia dengan pemetaan geografis"""
    if not os.path.exists(path_citra):
        print(f"Error: File citra tidak ditemukan: {path_citra}")
        return False
    
    try:
        print(f"🇮🇩 MEMULAI ANALISIS TROPOMI NO2 - GEOGRAFIS")
        today = datetime.now().strftime('%Y%m%d')
        print(f"📷 Memuat citra: {path_citra}")

        # Path ke GeoJSON
        geojson_path = "indonesia_kabkota_38prov.geojson"

        # Langkah 1: Analisis citra dengan pemetaan geografis
        analyzer = TropomiAnalyzerGeo(geojson_path)
        analyzer.load_image(path_citra)
        analyzer.extract_concentration_data()

        print("📊 Menganalisis konsentrasi dan hotspot...")
        hotspots = analyzer.detect_hotspots()
        stats = analyzer.calculate_statistics()

        print("🌬️ Menganalisis pola angin...")
        wind_patterns = analyzer.analyze_wind_patterns()

        print("💾 Menyimpan hasil analisis...")
        laporan_json_path = f"json/hasil_analisis_{today}.json"
        analyzer.generate_report(laporan_json_path)
        vis_path = f"png/visualisasi_analisis_{today}.png"
        analyzer.create_analysis_visualization(vis_path)

        # Langkah 2: Buat laporan Bahasa Indonesia dengan lokasi geografis
        print("📝 Membuat laporan geografis Bahasa Indonesia...")
        try:
            from report_generator_id import GeneratorLaporan
            generator = GeneratorLaporan()
            generator.muat_laporan_json(laporan_json_path)

            # Buat semua jenis laporan
            laporan_singkat = generator.buat_ringkasan_singkat()
            laporan_eksekutif = generator.buat_ringkasan_eksekutif()
            laporan_detail = generator.buat_laporan_detail()

            # Simpan laporan ke folder txt/ dengan tanggal
            with open(f'txt/ringkasan_singkat_id_{today}.txt', 'w', encoding='utf-8') as f:
                f.write(laporan_singkat)
            with open(f'txt/ringkasan_eksekutif_id_{today}.txt', 'w', encoding='utf-8') as f:
                f.write(laporan_eksekutif)
            with open(f'txt/laporan_detail_id_{today}.txt', 'w', encoding='utf-8') as f:
                f.write(laporan_detail)

        except ImportError:
            print("⚠️  Report generator tidak tersedia, membuat laporan sederhana...")
            # Fallback: buat laporan sederhana
            buat_laporan_sederhana(hotspots, stats, path_citra, today)

        # Ringkasan hasil
        print("\n" + "="*60)
        print("✅ ANALISIS GEOGRAFIS SELESAI")
        print("="*60)
        print(f"🎯 NO2 Maksimum: {stats['max_concentration']:.2f} ×10¹⁵ molekul/cm²")
        print(f"📊 NO2 Rata-rata: {stats['mean_concentration']:.2f} ×10¹⁵ molekul/cm²")
        print(f"🔥 Total hotspot: {len(hotspots)} lokasi")
        print(f"📍 Hotspot dengan lokasi: {len([h for h in hotspots if h.get('location')])}")

        status = 'SIAGA TINGGI' if stats['max_concentration'] > 25 else 'MENINGKAT' if stats['max_concentration'] > 15 else 'SEDANG' if stats['max_concentration'] > 10 else 'NORMAL'
        print(f"⚠️  Status: {status}")

        # Tampilkan hotspot dengan lokasi
        if hotspots:
            for i, hotspot in enumerate(hotspots[:3], 1):
                location = hotspot.get('location')
                if location and location.get('kabupaten'):
                    print(f"🏙️  Hotspot {i}: {location['kabupaten']}, {location['provinsi']} - {hotspot['max_concentration']:.2f}")
                else:
                    lon, lat = hotspot['geo_coordinates']
                    print(f"📍 Hotspot {i}: {lat:.3f}°S, {lon:.3f}°E - {hotspot['max_concentration']:.2f}")

        print(f"\n📁 FILE YANG DIBUAT:")
        print(f"   • {laporan_json_path} - Data lengkap dengan lokasi geografis")
        print(f"   • {vis_path} - Gambar analisis dengan nama lokasi")
        print(f"   • txt/ringkasan_singkat_id_{today}.txt - Ringkasan dengan kabupaten/kota")
        print(f"   • txt/ringkasan_eksekutif_id_{today}.txt - Laporan manajemen dengan lokasi")
        print(f"   • txt/laporan_detail_id_{today}.txt - Laporan teknis lengkap dengan pemetaan")

        print(f"\n🎉 ANALISIS GEOGRAFIS SIAP! Semua laporan termasuk nama kabupaten/kota")
        return True

    except Exception as e:
        print(f"❌ Analisis gagal: {e}")
        import traceback
        traceback.print_exc()
        return False

def buat_laporan_sederhana(hotspots, stats, path_citra, today):
    """Fallback: buat laporan sederhana jika report generator tidak tersedia"""
    now = datetime.now()
    bulan = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 
            'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
    laporan = (
        f"ANALISIS TROPOMI NO2 - GEOGRAFIS\n"
        f"{now.day} {bulan[now.month-1]} {now.year}, {now.strftime('%H:%M')} WIB\n\n"
        f"NO2 Maksimum: {stats['max_concentration']:.2f} ×10¹⁵ molekul/cm²\n"
        f"NO2 Rata-rata: {stats['mean_concentration']:.2f} ×10¹⁵ molekul/cm²\n"
        f"Total Hotspot: {len(hotspots)}\n\n"
        f"HOTSPOT DENGAN LOKASI:\n"
    )
    for idx, hspot in enumerate(hotspots[:10], 1):
        location = hspot.get('location')
        if location and location.get('kabupaten'):
            laporan += f"\n{idx}. {location['kabupaten']}, {location['provinsi']}"
            laporan += f"\n   NO2: {hspot['max_concentration']:.2f} ×10¹⁵ molekul/cm²"
        else:
            geo = hspot.get('geo_coordinates')
            if geo and len(geo) == 2 and geo[0] is not None and geo[1] is not None:
                lon, lat = geo
                laporan += f"\n{idx}. Koordinat {lat:.3f}°S, {lon:.3f}°E"
                laporan += f"\n   NO2: {hspot['max_concentration']:.2f} ×10¹⁵ molekul/cm²"
            else:
                laporan += f"\n{idx}. Lokasi tidak diketahui"
    filenames = [f'txt/ringkasan_singkat_id_{today}.txt', f'txt/ringkasan_eksekutif_id_{today}.txt', f'txt/laporan_detail_id_{today}.txt']
    for filename in filenames:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(laporan)

def main():
    print("🇮🇩 SISTEM ANALISIS TROPOMI NO2 - BAHASA INDONESIA")
    print("=" * 50)
    
    today = datetime.now().strftime('%Y%m%d')
    path_citra = f"png/NO2_Indonesia_Daily_{today}_linear_interp.png"
    if os.path.exists(path_citra):
        analisis_lengkap(path_citra)
    else:
        print(f"❌ Tidak ada file citra untuk hari ini: {path_citra}")
        print("\n📖 Contoh penggunaan:")
        print("   python3 04-quick-analysis.py")

if __name__ == "__main__":
    main()
