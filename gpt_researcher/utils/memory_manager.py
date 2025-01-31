import gc
import psutil
import os
from typing import Dict
from contextlib import asynccontextmanager

class MemoryManager:
    @staticmethod
    def get_memory_usage() -> Dict[str, float]:
        """Get current memory usage of the process."""
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        return {
            'rss_mb': mem_info.rss / 1024 / 1024,  # RSS in MB
            'vms_mb': mem_info.vms / 1024 / 1024,  # VMS in MB
            'percent': process.memory_percent()
        }

    @staticmethod
    def cleanup():
        """Force garbage collection."""
        gc.collect()

@asynccontextmanager
async def research_memory_manager(researcher):
    """Context manager for handling research memory cleanup."""
    try:
        initial_memory = MemoryManager.get_memory_usage()
        print(f"Initial memory usage: {initial_memory['rss_mb']:.2f} MB")
        yield researcher
    finally:
        # Clear memory-intensive attributes
        if hasattr(researcher, 'context'):
            researcher.context.clear()
        if hasattr(researcher, 'visited_urls'):
            researcher.visited_urls.clear()
        MemoryManager.cleanup()
        final_memory = MemoryManager.get_memory_usage()
        print(f"Final memory usage: {final_memory['rss_mb']:.2f} MB") 