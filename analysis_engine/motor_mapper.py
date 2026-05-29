"""
Motor Mapper - Convert Direction of Arrival to Motor Index

Maps compass angles (0-360°) to motor indices (0-3) for 4-motor belt.

Coordinate system:
  0°   = Front (Motor 0)
  90°  = Right (Motor 1)
  180° = Back  (Motor 2)
  270° = Left  (Motor 3)
"""

import numpy as np
from typing import Optional


class MotorMapper:
    """Map DOA angle to motor activation."""

    # Motor layout: 90° sectors
    # Motor 0 center: 0°   (Front)
    # Motor 1 center: 90°  (Right)
    # Motor 2 center: 180° (Back)
    # Motor 3 center: 270° (Left)
    MOTOR_CENTERS = {
        0: 0,    # Front
        1: 90,   # Right
        2: 180,  # Back
        3: 270,  # Left
    }
    
    MOTOR_SECTORS = {
        0: {'min': 315, 'max': 45, 'label': 'Front'},
        1: {'min': 45, 'max': 135, 'label': 'Right'},
        2: {'min': 135, 'max': 225, 'label': 'Back'},
        3: {'min': 225, 'max': 315, 'label': 'Left'},
    }

    @staticmethod
    def get_motor(doa_degrees: float, min_confidence: float = 0.3) -> Optional[int]:
        """
        Map DOA angle to motor index.
        
        Args:
            doa_degrees: Direction of arrival in degrees (0-360)
            min_confidence: Minimum confidence threshold (unused, for future expansion)
            
        Returns:
            Motor index (0-3) or None
        """
        if doa_degrees is None:
            return None
        
        # Normalize to 0-360
        doa_degrees = doa_degrees % 360
        
        # Find motor sector
        for motor_idx, sector in MotorMapper.MOTOR_SECTORS.items():
            if MotorMapper._is_in_sector(doa_degrees, sector['min'], sector['max']):
                return motor_idx
        
        # Default fallback (should not reach here)
        return 0

    @staticmethod
    def _is_in_sector(angle: float, min_angle: float, max_angle: float) -> bool:
        """Check if angle is within sector (handles wrap-around at 0°)."""
        if min_angle > max_angle:  # Sector wraps around 0°
            return angle >= min_angle or angle < max_angle
        else:
            return min_angle <= angle < max_angle

    @staticmethod
    def get_sector_label(motor_idx: int) -> str:
        """Get human-readable label for motor."""
        return MotorMapper.MOTOR_SECTORS[motor_idx]['label']

    @staticmethod
    def get_all_motors() -> list:
        """Return all motor configurations."""
        return [
            {
                'motor': idx,
                'label': config['label'],
                'min_angle': config['min'],
                'max_angle': config['max'],
            }
            for idx, config in MotorMapper.MOTOR_SECTORS.items()
        ]

    @staticmethod
    def angle_to_motor_intensity(doa_degrees: float, spread: float = 45.0) -> dict:
        """
        Map DOA to motor activation intensities (0-1).
        
        Closer to motor center = higher intensity.
        Spread: how many degrees around center are activated (default 45° = half motor sector).
        
        Args:
            doa_degrees: Direction of arrival in degrees
            spread: Spread in degrees (intensity > 0 within this range)
            
        Returns:
            {motor_0: intensity, motor_1: intensity, motor_2: intensity, motor_3: intensity}
        """
        doa_degrees = doa_degrees % 360
        
        intensities = {}
        for motor_idx, center_angle in MotorMapper.MOTOR_CENTERS.items():
            # Angular distance to motor center
            distance = MotorMapper._angular_distance(doa_degrees, center_angle)
            
            # Intensity: linear falloff with spread
            # At distance=0: intensity=1.0
            # At distance=spread: intensity=0.0
            # Beyond spread: intensity=0.0
            intensity = max(0.0, 1.0 - (distance / spread))
            intensities[motor_idx] = intensity
        
        return intensities

    @staticmethod
    def _angular_distance(angle1: float, angle2: float) -> float:
        """
        Compute shortest angular distance between two angles.
        
        Examples:
            _angular_distance(10, 350) = 20
            _angular_distance(0, 180) = 180
            _angular_distance(45, 90) = 45
        """
        # Normalize to 0-360
        angle1 = angle1 % 360
        angle2 = angle2 % 360
        
        # Calculate both directions
        diff1 = abs(angle1 - angle2)
        diff2 = 360 - diff1
        
        # Return shorter distance
        return min(diff1, diff2)

    @staticmethod
    def get_config() -> dict:
        """Return configuration"""
        return {
            'num_motors': 4,
            'motor_sectors': MotorMapper.MOTOR_SECTORS,
        }
