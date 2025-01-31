import gc
import psutil
import os
import time
from typing import Dict
from contextlib import asynccontextmanager

class MemoryManager:
    MEMORY_THRESHOLD = 350  # Even lower threshold
    CRITICAL_THRESHOLD = 450  # Critical threshold for emergency cleanup
    
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
    def emergency_cleanup():
        """Emergency cleanup when memory is critical"""
        gc.collect()
        gc.collect()
        if hasattr(gc, 'collect_generations'):
            gc.collect_generations()
        
        # Try to release memory back to OS
        try:
            import ctypes
            ctypes.CDLL('libc.so.6').malloc_trim(0)
        except:
            pass

    @staticmethod
    def check_memory_threshold():
        """Check if memory usage is approaching threshold"""
        usage = MemoryManager.get_memory_usage()
        
        if usage['rss_mb'] > MemoryManager.CRITICAL_THRESHOLD:
            print(f"CRITICAL: Memory at {usage['rss_mb']:.2f} MB - forcing emergency cleanup")
            MemoryManager.emergency_cleanup()
            time.sleep(0.1)  # Give OS time to reclaim memory
            MemoryManager.emergency_cleanup()
            
        elif usage['rss_mb'] > MemoryManager.MEMORY_THRESHOLD:
            print(f"WARNING: Memory at {usage['rss_mb']:.2f} MB - running cleanup")
            MemoryManager.force_cleanup()

    @staticmethod
    def force_cleanup():
        """Standard cleanup"""
        gc.collect()
        if hasattr(gc, 'collect_generations'):
            gc.collect_generations()

@asynccontextmanager
async def research_memory_manager(researcher, check_interval=2):  # Reduced interval
    """Context manager with more frequent memory checks"""
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
        if hasattr(researcher, 'context'):
            researcher.context = None
        if hasattr(researcher, 'visited_urls'):
            researcher.visited_urls = None
        MemoryManager.emergency_cleanup()
        final_memory = MemoryManager.get_memory_usage()
        print(f"Final memory usage: {final_memory['rss_mb']:.2f} MB") 