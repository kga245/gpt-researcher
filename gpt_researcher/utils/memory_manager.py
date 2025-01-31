import gc
import psutil
import os
from typing import Dict
from contextlib import asynccontextmanager

class MemoryManager:
    MEMORY_THRESHOLD = 450  # MB - set lower than Heroku's 512MB limit

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
    def check_memory_threshold():
        """Check if memory usage is approaching threshold"""
        usage = MemoryManager.get_memory_usage()
        if usage['rss_mb'] > MemoryManager.MEMORY_THRESHOLD:
            print(f"Memory threshold exceeded: {usage['rss_mb']:.2f} MB")
            MemoryManager.force_cleanup()

    @staticmethod
    def force_cleanup():
        """Aggressive memory cleanup"""
        gc.collect()
        if hasattr(gc, 'collect_generations'):
            gc.collect_generations()
        
        # Clear Python's internal memory pools
        import ctypes
        ctypes.CDLL('libc.so.6').malloc_trim(0)

@asynccontextmanager
async def research_memory_manager(researcher, check_interval=5):
    """Context manager with periodic memory checks"""
    try:
        initial_memory = MemoryManager.get_memory_usage()
        print(f"Initial memory usage: {initial_memory['rss_mb']:.2f} MB")
        
        # Set up periodic memory check
        from asyncio import create_task, sleep
        
        async def periodic_check():
            while True:
                await sleep(check_interval)
                MemoryManager.check_memory_threshold()
        
        memory_check_task = create_task(periodic_check())
        
        yield researcher
    finally:
        memory_check_task.cancel()
        if hasattr(researcher, 'context') and isinstance(researcher.context, list):
            researcher.context.clear()
        if hasattr(researcher, 'visited_urls') and isinstance(researcher.visited_urls, set):
            researcher.visited_urls.clear()
        MemoryManager.force_cleanup()
        final_memory = MemoryManager.get_memory_usage()
        print(f"Final memory usage: {final_memory['rss_mb']:.2f} MB") 