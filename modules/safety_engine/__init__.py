"""
BharatRx Medication Safety Engine
Author: Sidharth

Usage from anywhere in the project:

    from modules.safety_engine import analyse
    report = analyse(patient_dict, prescription_list)
"""

from .engine import analyse

__all__ = ["analyse"]
