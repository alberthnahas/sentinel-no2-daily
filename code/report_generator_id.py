#!/usr/bin/env python3
"""
Generator Laporan Teks TROPOMI NO2 - Bahasa Indonesia
Mengubah hasil analisis JSON menjadi laporan teks terformat untuk penggunaan copy-paste
"""

import json
import sys
from datetime import datetime
from pathlib import Path

class GeneratorLaporan:
    def __init__(self):
        self.data = None
        
    def muat_laporan_json(self, path_json):
        """Memuat data analisis dari file JSON"""
        try:
            with open(path_json, 'r') as f:
                self.data = json.load(f)
            return True
        except Exception as e:
            print(f"Error memuat JSON: {e}")
            return False
    
    def format_waktu(self, timestamp_str):
        """Mengubah timestamp ISO ke format yang dapat dibaca"""
        try:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            bulan_indonesia = [
                "Januari", "Februari", "Maret", "April", "Mei", "Juni",
                "Juli", "Agustus", "September", "Oktober", "November", "Desember"
            ]
            return f"{dt.day} {bulan_indonesia[dt.month-1]} {dt.year} pukul {dt.strftime('%H:%M:%S')} WIB"
        except:
            return timestamp_str
    
    def dapatkan_ringkasan_angin(self):
        """Meringkas pola angin"""
        if not self.data.get('wind_patterns'):
            return "Tidak terdeteksi pola angin yang signifikan"
        
        arah_angin = [wp['estimated_wind_direction'] for wp in self.data['wind_patterns']]
        if not arah_angin:
            return "Data arah angin tidak tersedia"
        
        rata_rata_arah = sum(arah_angin) / len(arah_angin)
        
        # Konversi ke arah mata angin
        if rata_rata_arah < 22.5 or rata_rata_arah >= 337.5:
            mata_angin = "Utara"
        elif rata_rata_arah < 67.5:
            mata_angin = "Timur Laut"
        elif rata_rata_arah < 112.5:
            mata_angin = "Timur"
        elif rata_rata_arah < 157.5:
            mata_angin = "Tenggara"
        elif rata_rata_arah < 202.5:
            mata_angin = "Selatan"
        elif rata_rata_arah < 247.5:
            mata_angin = "Barat Daya"
        elif rata_rata_arah < 292.5:
            mata_angin = "Barat"
        else:
            mata_angin = "Barat Laut"
        
        return f"Arah angin dominan: {mata_angin} ({rata_rata_arah:.1f}°) berdasarkan analisis {len(arah_angin)} plume"
    
    def buat_ringkasan_eksekutif(self):
        """Menghasilkan teks ringkasan eksekutif"""
        stats = self.data.get('statistics', {})
        hotspots = self.data.get('hotspots', [])
        
        konsentrasi_maks = stats.get('max_concentration', 0)
        konsentrasi_rata = stats.get('mean_concentration', 0)
        polusi_tinggi_persen = stats.get('coverage', {}).get('high_pollution', 0)
        
        # Identifikasi hotspot berdasarkan lokasi
        hotspots_with_location = [h for h in hotspots if h.get('location') and h.get('location', {}).get('kabupaten')]
        hotspot_locations = []
        if hotspots_with_location:
            for hotspot in hotspots_with_location[:5]:
                location = hotspot['location']
                hotspot_locations.append(f"{location['kabupaten']}")
        
        ringkasan = f"""ANALISIS TROPOMI NO2 - RINGKASAN EKSEKUTIF

Tanggal Analisis: {self.format_waktu(self.data.get('analysis_timestamp', ''))}
Area Focus: Pulau Jawa
Dimensi Citra: {' x '.join(map(str, self.data.get('image_info', {}).get('dimensions', [])[:2]))} piksel

TEMUAN UTAMA:
• Konsentrasi NO2 maksimum yang terdeteksi: {konsentrasi_maks:.2f} ×10¹⁵ molekul/cm²
• Rata-rata konsentrasi regional: {konsentrasi_rata:.2f} ×10¹⁵ molekul/cm²
• Cakupan polusi tinggi: {polusi_tinggi_persen:.2f}% dari area yang dianalisis
• Total hotspot polusi yang diidentifikasi: {len(hotspots)}
• Hotspot dengan nama lokasi: {len(hotspots_with_location)}

HOTSPOT UTAMA:
{', '.join(hotspot_locations[:3]) if hotspot_locations else 'Area laut/tidak teridentifikasi'}

PENILAIAN POLUSI:
Analisis menunjukkan konsentrasi NO2 yang {'signifikan' if konsentrasi_maks > 15 else 'sedang' if konsentrasi_maks > 10 else 'rendah'} di wilayah studi. {'Beberapa hotspot mengindikasikan adanya sumber emisi aktif yang memerlukan perhatian.' if len(hotspots) > 5 else 'Aktivitas hotspot terbatas menunjukkan kondisi atmosfer yang relatif bersih.' if len(hotspots) < 3 else 'Terdeteksi aktivitas hotspot sedang.'}

TRANSPORT ATMOSFERIK:
{self.dapatkan_ringkasan_angin()}
"""
        return ringkasan
    
    def buat_laporan_detail(self):
        """Menghasilkan laporan detail yang komprehensif"""
        stats = self.data.get('statistics', {})
        hotspots = self.data.get('hotspots', [])
        cakupan = stats.get('coverage', {})
        
        laporan = f"""ANALISIS DATA SATELIT TROPOMI NO2
LAPORAN TEKNIS DETAIL

═══════════════════════════════════════════════════════════════════════

METADATA ANALISIS
═══════════════════════════════════════════════════════════════════════
Waktu Analisis: {self.format_waktu(self.data.get('analysis_timestamp', ''))}
Dimensi Citra Sumber: {' × '.join(map(str, self.data.get('image_info', {}).get('dimensions', [])[:2]))} piksel
Total Piksel yang Dianalisis: {stats.get('total_pixels_analyzed', 0):,}
Cakupan Analisis: {self.data.get('image_info', {}).get('analysis_area_pixels', 0):,} piksel

RINGKASAN STATISTIK
═══════════════════════════════════════════════════════════════════════
Statistik Konsentrasi NO2 (×10¹⁵ molekul/cm²):
  • Maksimum:    {stats.get('max_concentration', 0):.3f}
  • Minimum:     {stats.get('min_concentration', 0):.3f}
  • Rata-rata:   {stats.get('mean_concentration', 0):.3f}
  • Median:      {stats.get('median_concentration', 0):.3f}
  • Deviasi Std: {stats.get('std_concentration', 0):.3f}

ANALISIS CAKUPAN SPASIAL
═══════════════════════════════════════════════════════════════════════
Distribusi Tingkat Polusi:
  • Polusi Rendah (2-8 unit):    {cakupan.get('low_pollution', 0):.2f}%
  • Polusi Sedang (8-15 unit):   {cakupan.get('moderate_pollution', 0):.2f}%
  • Polusi Tinggi (>15 unit):    {cakupan.get('high_pollution', 0):.2f}%

ANALISIS HOTSPOT
═══════════════════════════════════════════════════════════════════════
Total Hotspot yang Terdeteksi: {len(hotspots)}

10 Hotspot Polusi Teratas (berdasarkan konsentrasi):"""

        # Tambahkan hotspot teratas dengan prioritas nama lokasi
        for i, hotspot in enumerate(hotspots[:10], 1):
            location = hotspot.get('location')
            geo_coords = hotspot.get('geo_coordinates', [0, 0])
            
            # Prioritaskan nama kabupaten/kota, fallback ke koordinat
            if location and location.get('kabupaten'):
                lokasi_text = f"{location['kabupaten']}, {location['provinsi']}"
                # Format koordinat tanpa negatif untuk selatan
                lat_abs = abs(geo_coords[1])
                koordinat_text = f"Koordinat: {lat_abs:.3f}°S, {geo_coords[0]:.3f}°E"
            else:
                # Format koordinat tanpa negatif untuk selatan  
                lat_abs = abs(geo_coords[1])
                lokasi_text = f"Area {lat_abs:.3f}°S, {geo_coords[0]:.3f}°E"
                koordinat_text = f"Pixel: ({hotspot.get('centroid', [0, 0])[0]}, {hotspot.get('centroid', [0, 0])[1]})"
            
            laporan += f"""
  {i:2d}. {lokasi_text}
      Konsentrasi Maks: {hotspot.get('max_concentration', 0):.2f} ×10¹⁵ molekul/cm²
      Rata-rata: {hotspot.get('avg_concentration', 0):.2f} ×10¹⁵ molekul/cm²
      {koordinat_text}
      Area: {hotspot.get('area_pixels', 0)} piksel"""

        # Bagian analisis angin
        pola_angin = self.data.get('wind_patterns', [])
        laporan += f"""

ANALISIS TRANSPORT ATMOSFERIK
═══════════════════════════════════════════════════════════════════════
{self.dapatkan_ringkasan_angin()}

Plume yang Terdeteksi: {len(pola_angin)}"""

        if pola_angin:
            laporan += "\nAnalisis Angin per Plume:"
            for wp in pola_angin[:5]:  # Tampilkan 5 plume teratas
                laporan += f"""
  Plume {wp.get('plume_id', 'Tidak diketahui')}: {wp.get('estimated_wind_direction', 0):.1f}° (kepercayaan {wp.get('confidence', 'tidak diketahui')})"""

        laporan += f"""

PENILAIAN LINGKUNGAN
═══════════════════════════════════════════════════════════════════════
Status Kualitas Udara: {'BURUK - Terdeteksi tingkat NO2 tinggi' if stats.get('max_concentration', 0) > 20 else 'SEDANG - NO2 meningkat di area terlokalisasi' if stats.get('max_concentration', 0) > 15 else 'CUKUP - Tingkat NO2 dalam rentang yang dapat diterima' if stats.get('max_concentration', 0) > 10 else 'BAIK - Konsentrasi NO2 rendah diamati'}

Penilaian Sumber Emisi:
• {'Beberapa sumber emisi signifikan teridentifikasi' if len(hotspots) > 8 else 'Beberapa sumber emisi terlokalisasi terdeteksi' if len(hotspots) > 4 else 'Aktivitas sumber emisi terbatas' if len(hotspots) > 1 else 'Aktivitas sumber emisi minimal'}
• {'Transport polusi regional terlihat jelas' if len(pola_angin) > 3 else 'Pola polusi lokal teramati'}

REKOMENDASI
═══════════════════════════════════════════════════════════════════════"""

        # Buat rekomendasi berdasarkan temuan
        if stats.get('max_concentration', 0) > 20:
            laporan += "\n• Disarankan pemantauan segera pada area berkonsentrasi tinggi"
            laporan += "\n• Investigasi sumber emisi pada hotspot yang teridentifikasi"
        elif stats.get('max_concentration', 0) > 15:
            laporan += "\n• Lanjutkan pemantauan pada area berkonsentrasi meningkat"
            laporan += "\n• Disarankan penilaian sumber emisi"
        else:
            laporan += "\n• Pertahankan jadwal pemantauan rutin"
            laporan += "\n• Lanjutkan surveilans atmosfer dasar"

        if len(hotspots) > 8:
            laporan += "\n• Disarankan validasi ground-truth multi-titik"
            laporan += "\n• Direkomendasikan pembaruan inventori emisi komprehensif"

        laporan += f"""

═══════════════════════════════════════════════════════════════════════
Laporan dibuat oleh Sistem Analisis Otomatis TROPOMI NO2
Analisis diselesaikan pada: {datetime.now().strftime("%d %B %Y pukul %H:%M:%S")}
═══════════════════════════════════════════════════════════════════════"""

        return laporan
    
    def buat_ringkasan_singkat(self):
        """Menghasilkan ringkasan singkat yang mudah untuk copy-paste"""
        stats = self.data.get('statistics', {})
        hotspots = self.data.get('hotspots', [])
        
        # Identifikasi hotspot dengan lokasi
        hotspots_with_location = [h for h in hotspots if h.get('location') and h.get('location', {}).get('kabupaten')]
        top_locations = []
        if hotspots_with_location:
            for hotspot in hotspots_with_location[:3]:
                location = hotspot['location']
                top_locations.append(f"{location['kabupaten']}")
        
        ringkasan = f"""Ringkasan Analisis TROPOMI NO2 - {self.format_waktu(self.data.get('analysis_timestamp', '')).split(' pukul')[0]}

NO2 Maks: {stats.get('max_concentration', 0):.2f} ×10¹⁵ molekul/cm²
NO2 Rata-rata: {stats.get('mean_concentration', 0):.2f} ×10¹⁵ molekul/cm²
Hotspot: {len(hotspots)} lokasi ({len(hotspots_with_location)} dengan nama)
Cakupan Polusi Tinggi: {stats.get('coverage', {}).get('high_pollution', 0):.2f}%

Status: {'SIAGA TINGGI' if stats.get('max_concentration', 0) > 25 else 'MENINGKAT' if stats.get('max_concentration', 0) > 15 else 'SEDANG' if stats.get('max_concentration', 0) > 10 else 'NORMAL'}
Lokasi Utama: {', '.join(top_locations) if top_locations else 'Area laut/tidak teridentifikasi'}
{self.dapatkan_ringkasan_angin().split(':')[1].strip() if ':' in self.dapatkan_ringkasan_angin() else 'Pola angin: Bervariasi'}"""
        
        return ringkasan

def main():
    generator = GeneratorLaporan()
    
    # Dapatkan path file JSON
    if len(sys.argv) > 1:
        path_json = sys.argv[1]
    else:
        path_json = input("Masukkan path ke file JSON analisis: ").strip()
    
    if not path_json:
        print("Tidak ada file JSON yang ditentukan")
        return
    
    # Muat data
    if not generator.muat_laporan_json(path_json):
        return
    
    # Tanya user jenis laporan yang diinginkan
    print("\nPilih jenis laporan:")
    print("1. Ringkasan Eksekutif (singkat)")
    print("2. Laporan Teknis Detail (komprehensif)")
    print("3. Ringkasan Singkat (mudah copy-paste)")
    print("4. Semua laporan")
    
    pilihan = input("Masukkan pilihan (1-4): ").strip()
    
    nama_dasar = Path(path_json).stem
    
    if pilihan in ['1', '4']:
        laporan_eksekutif = generator.buat_ringkasan_eksekutif()
        file_eksekutif = f"{nama_dasar}_ringkasan_eksekutif.txt"
        with open(file_eksekutif, 'w', encoding='utf-8') as f:
            f.write(laporan_eksekutif)
        print(f"Ringkasan eksekutif disimpan: {file_eksekutif}")
    
    if pilihan in ['2', '4']:
        laporan_detail = generator.buat_laporan_detail()
        file_detail = f"{nama_dasar}_laporan_detail.txt"
        with open(file_detail, 'w', encoding='utf-8') as f:
            f.write(laporan_detail)
        print(f"Laporan detail disimpan: {file_detail}")
    
    if pilihan in ['3', '4']:
        laporan_singkat = generator.buat_ringkasan_singkat()
        file_singkat = f"{nama_dasar}_ringkasan_singkat.txt"
        with open(file_singkat, 'w', encoding='utf-8') as f:
            f.write(laporan_singkat)
        print(f"Ringkasan singkat disimpan: {file_singkat}")
    
    print("\nLaporan teks dalam Bahasa Indonesia telah dibuat dan siap untuk copy-paste!")

if __name__ == "__main__":
    main()
