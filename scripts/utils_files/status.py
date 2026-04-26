from enum import Enum

class Status(str, Enum):
    PROCESSING = "PROCESSING"  
    SUCCESS = "SUCCESS"        
    FAILED = "FAILED"