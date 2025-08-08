#!/usr/bin/env python3
"""
TROPOMI NO2 Satellite Image Analyzer
Free, open-source tool for automated analysis of atmospheric pollution data
"""

import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import json
from datetime import datetime

class TropomiAnalyzer:
    def __init__(self):
        self.image = None
        self.processed_image = None
        self.concentration_map = None
        self.results = {}
        
    def load_image(self, image_path):
        """Load and preprocess satellite image"""
        self.image = cv2.imread(image_path)
        if self.image is None:
            raise ValueError(f"Could not load image from {image_path}")
        
        # Convert BGR to RGB for matplotlib compatibility
        self.image = cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB)
        print(f"Loaded image: {self.image.shape}")
        return self.image
    
    def extract_concentration_data(self):
        """Extract NO2 concentration values from color-coded image"""
        # Create mask for data area (exclude legend and labels)
        height, width = self.image.shape[:2]
        
        # Focus on the main map area (exclude legend at bottom)
        map_area = self.image[:int(height * 0.85), :]
        
        # Convert to HSV for better color analysis
        hsv = cv2.cvtColor(map_area, cv2.COLOR_RGB2HSV)
        
        # Define color ranges for different concentration levels
        color_ranges = {
            'very_low': ([0, 0, 200], [180, 30, 255]),      # White/very light
            'low': ([100, 50, 150], [130, 255, 255]),       # Light blue
            'medium': ([60, 100, 100], [90, 255, 255]),     # Green
            'high': ([20, 100, 100], [40, 255, 255]),       # Yellow
            'very_high': ([0, 100, 100], [20, 255, 255])    # Red
        }
        
        concentration_values = {
            'very_low': 2,
            'low': 5,
            'medium': 10,
            'high': 20,
            'very_high': 30
        }
        
        # Create concentration map
        self.concentration_map = np.zeros(map_area.shape[:2], dtype=np.float32)
        
        for level, (lower, upper) in color_ranges.items():
            lower = np.array(lower)
            upper = np.array(upper)
            mask = cv2.inRange(hsv, lower, upper)
            self.concentration_map[mask > 0] = concentration_values[level]
        
        return self.concentration_map
    
    def detect_hotspots(self, threshold=15):
        """Detect pollution hotspots above threshold"""
        if self.concentration_map is None:
            self.extract_concentration_data()
        
        # Create binary mask for hotspots
        hotspot_mask = self.concentration_map > threshold
        
        # Find connected components (hotspot regions)
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            hotspot_mask.astype(np.uint8), connectivity=8
        )
        
        hotspots = []
        for i in range(1, num_labels):  # Skip background (label 0)
            area = stats[i, cv2.CC_STAT_AREA]
            if area > 10:  # Filter out tiny noise
                centroid_x, centroid_y = centroids[i]
                max_concentration = np.max(self.concentration_map[labels == i])
                
                hotspots.append({
                    'id': i,
                    'centroid': (int(centroid_x), int(centroid_y)),
                    'area_pixels': area,
                    'max_concentration': max_concentration,
                    'avg_concentration': np.mean(self.concentration_map[labels == i])
                })
        
        # Sort by concentration level
        hotspots.sort(key=lambda x: x['max_concentration'], reverse=True)
        return hotspots
    
    def calculate_statistics(self):
        """Calculate comprehensive statistics"""
        if self.concentration_map is None:
            self.extract_concentration_data()
        
        # Remove zero values (background/water)
        valid_data = self.concentration_map[self.concentration_map > 0]
        
        stats = {
            'total_pixels_analyzed': len(valid_data),
            'max_concentration': float(np.max(valid_data)) if len(valid_data) > 0 else 0,
            'min_concentration': float(np.min(valid_data)) if len(valid_data) > 0 else 0,
            'mean_concentration': float(np.mean(valid_data)) if len(valid_data) > 0 else 0,
            'median_concentration': float(np.median(valid_data)) if len(valid_data) > 0 else 0,
            'std_concentration': float(np.std(valid_data)) if len(valid_data) > 0 else 0,
        }
        
        # Calculate area coverage for different concentration levels
        total_area = np.sum(self.concentration_map > 0)
        if total_area > 0:
            stats['coverage'] = {
                'low_pollution': float(np.sum((self.concentration_map >= 2) & (self.concentration_map < 8)) / total_area * 100),
                'moderate_pollution': float(np.sum((self.concentration_map >= 8) & (self.concentration_map < 15)) / total_area * 100),
                'high_pollution': float(np.sum(self.concentration_map >= 15) / total_area * 100)
            }
        
        return stats
    
    def analyze_wind_patterns(self):
        """Analyze wind direction from plume orientation"""
        if self.concentration_map is None:
            self.extract_concentration_data()
        
        # Find high concentration areas
        high_conc_mask = self.concentration_map > 15
        
        if np.sum(high_conc_mask) == 0:
            return {"message": "No significant pollution plumes detected"}
        
        # Find contours of high concentration areas
        contours, _ = cv2.findContours(
            high_conc_mask.astype(np.uint8), 
            cv2.RETR_EXTERNAL, 
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        wind_analysis = []
        for i, contour in enumerate(contours):
            if cv2.contourArea(contour) > 50:  # Filter small contours
                # Fit ellipse to determine orientation
                if len(contour) >= 5:
                    ellipse = cv2.fitEllipse(contour)
                    angle = ellipse[2]  # Angle of major axis
                    
                    # Convert to wind direction (perpendicular to plume)
                    wind_direction = (angle + 90) % 360
                    
                    wind_analysis.append({
                        'plume_id': i + 1,
                        'estimated_wind_direction': wind_direction,
                        'plume_orientation': angle,
                        'confidence': 'medium' if cv2.contourArea(contour) > 100 else 'low'
                    })
        
        return wind_analysis
    
    def _convert_numpy_types(self, obj):
        """Convert NumPy types to Python native types for JSON serialization"""
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {key: self._convert_numpy_types(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_numpy_types(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(self._convert_numpy_types(item) for item in obj)
        else:
            return obj

    def generate_report(self, output_path='tropomi_analysis_report.json'):
        """Generate comprehensive analysis report"""
        if self.concentration_map is None:
            self.extract_concentration_data()
        
        report = {
            'analysis_timestamp': datetime.now().isoformat(),
            'image_info': {
                'dimensions': list(self.image.shape),
                'analysis_area_pixels': int(np.sum(self.concentration_map > 0))
            },
            'statistics': self.calculate_statistics(),
            'hotspots': self.detect_hotspots(),
            'wind_patterns': self.analyze_wind_patterns()
        }
        
        # Convert NumPy types for JSON serialization
        report = self._convert_numpy_types(report)
        
        # Save to JSON
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"Analysis report saved to: {output_path}")
        return report
    
    def create_analysis_visualization(self, output_path='tropomi_analysis.png'):
        """Create visualization with annotations"""
        if self.concentration_map is None:
            self.extract_concentration_data()
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('TROPOMI NO2 Automated Analysis Results', fontsize=16, fontweight='bold')
        
        # Original image
        axes[0, 0].imshow(self.image)
        axes[0, 0].set_title('Original Satellite Image')
        axes[0, 0].axis('off')
        
        # Concentration map
        im = axes[0, 1].imshow(self.concentration_map, cmap='YlOrRd', vmin=0, vmax=30)
        axes[0, 1].set_title('Extracted Concentration Map')
        axes[0, 1].axis('off')
        plt.colorbar(im, ax=axes[0, 1], label='NO2 (×10¹⁵ molec/cm²)')
        
        # Hotspot detection
        hotspots = self.detect_hotspots()
        axes[1, 0].imshow(self.concentration_map, cmap='YlOrRd', alpha=0.7)
        for hotspot in hotspots[:5]:  # Show top 5 hotspots
            x, y = hotspot['centroid']
            axes[1, 0].scatter(x, y, c='red', s=100, marker='x')
            axes[1, 0].annotate(f"#{hotspot['id']}: {hotspot['max_concentration']:.1f}", 
                              (x, y), xytext=(5, 5), textcoords='offset points',
                              bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
        axes[1, 0].set_title(f'Hotspots Detected: {len(hotspots)}')
        axes[1, 0].axis('off')
        
        # Statistics summary
        stats = self.calculate_statistics()
        stats_text = f"""
        Analysis Summary:
        
        Max Concentration: {stats['max_concentration']:.2f}
        Mean Concentration: {stats['mean_concentration']:.2f}
        
        Area Coverage:
        • Low Pollution: {stats.get('coverage', {}).get('low_pollution', 0):.1f}%
        • Moderate: {stats.get('coverage', {}).get('moderate_pollution', 0):.1f}%  
        • High: {stats.get('coverage', {}).get('high_pollution', 0):.1f}%
        
        Hotspots Found: {len(hotspots)}
        """
        axes[1, 1].text(0.1, 0.7, stats_text, transform=axes[1, 1].transAxes, 
                        fontsize=10, verticalalignment='top',
                        bbox=dict(boxstyle='round,pad=0.5', facecolor='lightblue', alpha=0.8))
        axes[1, 1].set_title('Analysis Statistics')
        axes[1, 1].axis('off')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Analysis visualization saved to: {output_path}")
        plt.close()
        
        return output_path

def main():
    """Example usage"""
    analyzer = TropomiAnalyzer()
    
    # Example with your image (adjust path as needed)
    try:
        # Load the satellite image
        image_path = input("Enter path to TROPOMI image (or press Enter for default): ").strip()
        if not image_path:
            print("Please provide the path to your TROPOMI satellite image")
            return
            
        analyzer.load_image(image_path)
        
        # Run complete analysis
        print("Running automated analysis...")
        report = analyzer.generate_report()
        
        # Create visualization
        analyzer.create_analysis_visualization()
        
        # Print summary
        print("\n" + "="*60)
        print("ANALYSIS COMPLETE")
        print("="*60)
        print(f"Max NO2 concentration: {report['statistics']['max_concentration']:.2f}")
        print(f"Mean concentration: {report['statistics']['mean_concentration']:.2f}")
        print(f"Hotspots detected: {len(report['hotspots'])}")
        
        if report['hotspots']:
            print("\nTop 3 Pollution Hotspots:")
            for i, hotspot in enumerate(report['hotspots'][:3]):
                print(f"  {i+1}. Location: {hotspot['centroid']}, "
                      f"Max: {hotspot['max_concentration']:.2f}")
        
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure the image path is correct and the file exists.")

if __name__ == "__main__":
    main()