import gc
import psutil
import os
from typing import Dict
from contextlib import asynccontextmanager
import time

class MemoryManager:
    MEMORY_THRESHOLD = 400  # Lowered from 450 to 400 MB

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
        """Check if memory usage is approaching threshold and force cleanup if needed"""
        usage = MemoryManager.get_memory_usage()
        if usage['rss_mb'] > MemoryManager.MEMORY_THRESHOLD:
            print(f"Memory threshold exceeded: {usage['rss_mb']:.2f} MB - forcing cleanup")
            MemoryManager.force_cleanup()
            # Second cleanup after a short delay if still high
            if MemoryManager.get_memory_usage()['rss_mb'] > MemoryManager.MEMORY_THRESHOLD:
                time.sleep(0.1)  # Brief pause
                MemoryManager.force_cleanup()

    @staticmethod
    def force_cleanup():
        """More aggressive memory cleanup"""
        gc.collect()
        gc.collect()  # Double collection
        if hasattr(gc, 'collect_generations'):
            gc.collect_generations()
        
        # Try to release memory back to the system
        import ctypes
        try:
            ctypes.CDLL('libc.so.6').malloc_trim(0)
        except:
            pass  # Ignore if not available

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