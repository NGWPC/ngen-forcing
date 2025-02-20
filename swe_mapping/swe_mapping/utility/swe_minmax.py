import numpy as np

# Initialize global variables
_global_min = float('inf')  
_global_max = float('-inf')

def get_minmax(current_data):
    """
    Updates the global min/max with current data,
    returns the current global values
    """
    global _global_min, _global_max
    
    current_min = np.nanmin(current_data)
    current_max = np.nanmax(current_data)
    
    _global_min = min(_global_min, current_min)
    _global_max = max(_global_max, current_max)
    
    return _global_min, _global_max

def reset_minmax():
    """
    Reset the global min/max values
    """
    global _global_min, _global_max
    _global_min = float('inf')
    _global_max = float('-inf')

